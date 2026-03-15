"""
Abstract Payme transaction handler backed by ProviderTransaction model.

Implements all 6 methods of paylinker's ``TransactionHandler`` protocol.
Subclass and override the business-logic hooks::

    from paylinker_django.handlers import DjangoPaymeTransactionHandler

    class MyPaymeHandler(DjangoPaymeTransactionHandler):
        def validate_order(self, order_id, amount_tiyin):
            order = Order.objects.get(pk=order_id)
            if order.is_terminal:
                raise PaymeError(-31099, "Завершён", "Yakunlangan", "Terminal")
            if int(order.amount * 100) != amount_tiyin:
                raise PaymeError(-31001, "Неверная сумма", "Noto'g'ri summa", "Wrong amount")

        def on_payment_performed(self, provider_tx):
            order = Order.objects.get(pk=provider_tx.order_id)
            order.mark_paid()

        def on_payment_cancelled(self, provider_tx, reason, was_performed):
            if was_performed:
                order = Order.objects.get(pk=provider_tx.order_id)
                order.refund()
"""
from __future__ import annotations

import logging
import time

from django.db import transaction

from paylinker.providers.payme.enums import PaymeTransactionState
from paylinker.providers.payme.rpc_handler import PaymeError
from paylinker.providers.payme.schemas import (
    CancelTransactionResult,
    CheckPerformResult,
    CheckTransactionResult,
    CreateTransactionResult,
    PerformTransactionResult,
    StatementTransaction,
)

from paylinker_django.conf import paylinker_settings
from paylinker_django.models import ProviderTransaction

logger = logging.getLogger("paylinker_django.payme")


class DjangoPaymeTransactionHandler:
    """Base Payme handler that manages ``ProviderTransaction`` lifecycle.

    Subclass and implement the three abstract hooks:

    - ``validate_order(order_id, amount_tiyin)`` — raise ``PaymeError`` on failure
    - ``on_payment_performed(provider_tx)`` — called after state → PERFORMED
    - ``on_payment_cancelled(provider_tx, reason, was_performed)`` — called after cancel
    """

    # Override in subclass if account field differs from settings.
    account_field: str | None = None

    def _get_account_field(self) -> str:
        return self.account_field or paylinker_settings.ACCOUNT_FIELD

    # --- Abstract hooks (subclass must implement) ---

    def validate_order(self, order_id: str, amount_tiyin: int) -> None:
        """Validate that the order exists and amount matches.

        Raise ``PaymeError`` on any validation failure.
        """
        raise NotImplementedError

    def on_payment_performed(self, provider_tx: ProviderTransaction) -> None:
        """Called when payment is confirmed (state → PERFORMED).

        Use this to update your Order, create Payment records, etc.
        """
        raise NotImplementedError

    def on_payment_cancelled(
        self,
        provider_tx: ProviderTransaction,
        reason: int,
        was_performed: bool,
    ) -> None:
        """Called when payment is cancelled.

        ``was_performed`` indicates whether the payment was already confirmed
        before cancellation (refund scenario).
        """
        pass

    # --- Protocol implementation ---

    def _extract_order_id(self, account: dict[str, str]) -> str:
        field = self._get_account_field()
        order_id = account.get(field, "")
        if not order_id:
            raise PaymeError(
                code=-31050,
                message_ru="Заказ не найден",
                message_uz="Buyurtma topilmadi",
                message_en="Order not found",
                data=field,
            )
        return order_id

    def check_perform(self, amount: int, account: dict[str, str]) -> CheckPerformResult:
        order_id = self._extract_order_id(account)
        self.validate_order(order_id, amount)
        return CheckPerformResult(allow=True)

    @transaction.atomic
    def create_transaction(
        self, payme_id: str, payme_time: int, amount: int, account: dict[str, str]
    ) -> CreateTransactionResult:
        # Idempotency: check for existing transaction
        existing = ProviderTransaction.objects.filter(
            provider=ProviderTransaction.Provider.PAYME, external_id=payme_id,
        ).first()

        if existing:
            if existing.state == PaymeTransactionState.CREATED:
                return CreateTransactionResult(
                    create_time=existing.provider_create_time,
                    transaction=str(existing.pk),
                    state=existing.state,
                )
            raise PaymeError(
                code=-31008,
                message_ru="Невозможно создать транзакцию",
                message_uz="Tranzaksiya yaratib bo'lmaydi",
                message_en="Transaction cannot be created",
            )

        order_id = self._extract_order_id(account)
        self.validate_order(order_id, amount)

        provider_tx = ProviderTransaction.objects.create(
            provider=ProviderTransaction.Provider.PAYME,
            external_id=payme_id,
            order_id=order_id,
            state=PaymeTransactionState.CREATED,
            amount=amount,
            provider_create_time=payme_time,
            account_data=account,
        )

        logger.info("CreateTransaction: order=%s payme_id=%s", order_id, payme_id)

        return CreateTransactionResult(
            create_time=payme_time,
            transaction=str(provider_tx.pk),
            state=PaymeTransactionState.CREATED,
        )

    @transaction.atomic
    def perform_transaction(self, payme_id: str) -> PerformTransactionResult:
        provider_tx = self._get_transaction(payme_id)

        if provider_tx.state == PaymeTransactionState.PERFORMED:
            return PerformTransactionResult(
                transaction=str(provider_tx.pk),
                perform_time=provider_tx.provider_perform_time,
                state=PaymeTransactionState.PERFORMED,
            )

        if provider_tx.state != PaymeTransactionState.CREATED:
            raise PaymeError(
                code=-31008,
                message_ru="Невозможно выполнить",
                message_uz="Bajarib bo'lmaydi",
                message_en="Transaction cannot be performed",
            )

        now_ms = int(time.time() * 1000)
        provider_tx.state = PaymeTransactionState.PERFORMED
        provider_tx.provider_perform_time = now_ms
        provider_tx.save(update_fields=["state", "provider_perform_time", "updated_at"])

        self.on_payment_performed(provider_tx)

        logger.info("PerformTransaction: payme_id=%s", payme_id)

        return PerformTransactionResult(
            transaction=str(provider_tx.pk),
            perform_time=now_ms,
            state=PaymeTransactionState.PERFORMED,
        )

    @transaction.atomic
    def cancel_transaction(self, payme_id: str, reason: int) -> CancelTransactionResult:
        provider_tx = self._get_transaction(payme_id)

        # Already cancelled — idempotent
        if provider_tx.state in (
            PaymeTransactionState.CANCELLED_BEFORE_PERFORM,
            PaymeTransactionState.CANCELLED_AFTER_PERFORM,
        ):
            return CancelTransactionResult(
                transaction=str(provider_tx.pk),
                cancel_time=provider_tx.provider_cancel_time,
                state=provider_tx.state,
            )

        now_ms = int(time.time() * 1000)

        if provider_tx.state == PaymeTransactionState.CREATED:
            new_state = PaymeTransactionState.CANCELLED_BEFORE_PERFORM
            was_performed = False
        elif provider_tx.state == PaymeTransactionState.PERFORMED:
            new_state = PaymeTransactionState.CANCELLED_AFTER_PERFORM
            was_performed = True
        else:
            raise PaymeError(
                code=-31008,
                message_ru="Невозможно отменить",
                message_uz="Bekor qilib bo'lmaydi",
                message_en="Transaction cannot be cancelled",
            )

        provider_tx.state = new_state
        provider_tx.provider_cancel_time = now_ms
        provider_tx.cancel_reason = reason
        provider_tx.save(update_fields=["state", "provider_cancel_time", "cancel_reason", "updated_at"])

        self.on_payment_cancelled(provider_tx, reason, was_performed)

        logger.info("CancelTransaction: payme_id=%s reason=%d state=%d", payme_id, reason, new_state)

        return CancelTransactionResult(
            transaction=str(provider_tx.pk),
            cancel_time=now_ms,
            state=new_state,
        )

    def check_transaction(self, payme_id: str) -> CheckTransactionResult:
        provider_tx = self._get_transaction(payme_id)
        return CheckTransactionResult(
            create_time=provider_tx.provider_create_time,
            perform_time=provider_tx.provider_perform_time or 0,
            cancel_time=provider_tx.provider_cancel_time or 0,
            transaction=str(provider_tx.pk),
            state=provider_tx.state,
            reason=provider_tx.cancel_reason,
        )

    def get_statement(self, from_time: int, to_time: int) -> list[StatementTransaction]:
        txs = ProviderTransaction.objects.filter(
            provider=ProviderTransaction.Provider.PAYME,
            provider_create_time__gte=from_time,
            provider_create_time__lte=to_time,
        ).order_by("provider_create_time")

        return [
            StatementTransaction(
                id=tx.external_id,
                time=tx.provider_create_time,
                amount=tx.amount,
                account=tx.account_data,
                create_time=tx.provider_create_time,
                perform_time=tx.provider_perform_time or 0,
                cancel_time=tx.provider_cancel_time or 0,
                transaction=str(tx.pk),
                state=tx.state,
                reason=tx.cancel_reason,
            )
            for tx in txs
        ]

    # --- Helpers ---

    @staticmethod
    def _get_transaction(payme_id: str) -> ProviderTransaction:
        try:
            return ProviderTransaction.objects.select_for_update().get(
                provider=ProviderTransaction.Provider.PAYME, external_id=payme_id,
            )
        except ProviderTransaction.DoesNotExist:
            raise PaymeError(
                code=-31003,
                message_ru="Транзакция не найдена",
                message_uz="Tranzaksiya topilmadi",
                message_en="Transaction not found",
            )
