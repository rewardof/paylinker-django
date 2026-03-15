"""
Abstract Click order validator backed by ProviderTransaction model.

Implements all 5 methods of paylinker's ``OrderValidator`` protocol.
Subclass and override the business-logic hooks::

    from paylinker_django.handlers import DjangoClickOrderValidator
    from paylinker.providers.click.webhook import OrderCheckResult
    from paylinker.providers.click.enums import ClickErrorCode

    class MyClickValidator(DjangoClickOrderValidator):
        def validate_order(self, merchant_trans_id, amount):
            try:
                order = Order.objects.get(pk=merchant_trans_id)
            except Order.DoesNotExist:
                return OrderCheckResult.fail(ClickErrorCode.ORDER_NOT_FOUND, "Not found")
            if float(order.amount) != amount:
                return OrderCheckResult.fail(ClickErrorCode.INCORRECT_AMOUNT, "Bad amount")
            return OrderCheckResult.ok()

        def on_payment_completed(self, provider_tx):
            order = Order.objects.get(pk=provider_tx.order_id)
            order.mark_paid()

        def on_payment_cancelled(self, provider_tx):
            order = Order.objects.get(pk=provider_tx.order_id)
            order.cancel()
"""
from __future__ import annotations

import logging

from django.db import transaction

from paylinker.providers.click.webhook import OrderCheckResult

from paylinker_django.models import ProviderTransaction

logger = logging.getLogger("paylinker_django.click")


class DjangoClickOrderValidator:
    """Base Click validator that manages ``ProviderTransaction`` lifecycle.

    Subclass and implement:

    - ``validate_order(merchant_trans_id, amount)`` → ``OrderCheckResult``
    - ``on_payment_completed(provider_tx)`` — called after complete
    - ``on_payment_cancelled(provider_tx)`` — called after cancel
    """

    # --- Abstract hooks (subclass must implement) ---

    def validate_order(self, merchant_trans_id: str, amount: float) -> OrderCheckResult:
        """Validate that the order exists and amount matches.

        Return ``OrderCheckResult.ok()`` or ``OrderCheckResult.fail(code, note)``.
        """
        raise NotImplementedError

    def on_payment_completed(self, provider_tx: ProviderTransaction) -> None:
        """Called when payment is confirmed (complete phase successful).

        Use this to update your Order, create Payment records, etc.
        """
        raise NotImplementedError

    def on_payment_cancelled(self, provider_tx: ProviderTransaction) -> None:
        """Called when Click sends a cancellation.

        Override to handle cancellation in your business logic.
        """
        pass

    # --- Protocol implementation ---

    def check_order(self, merchant_trans_id: str, amount: float) -> OrderCheckResult:
        return self.validate_order(merchant_trans_id, amount)

    def check_duplicate(self, click_trans_id: int) -> int | None:
        existing = ProviderTransaction.objects.filter(
            provider=ProviderTransaction.Provider.CLICK,
            external_id=str(click_trans_id),
        ).first()
        if existing:
            return existing.pk
        return None

    @transaction.atomic
    def on_prepare(self, click_trans_id: int, merchant_trans_id: str, amount: float) -> int:
        provider_tx = ProviderTransaction.objects.create(
            provider=ProviderTransaction.Provider.CLICK,
            external_id=str(click_trans_id),
            order_id=merchant_trans_id,
            state=0,  # Prepared
            amount=int(amount),
        )

        logger.info(
            "on_prepare: order=%s click_trans_id=%d prepare_id=%d",
            merchant_trans_id, click_trans_id, provider_tx.pk,
        )

        return provider_tx.pk

    @transaction.atomic
    def on_complete(
        self,
        click_trans_id: int,
        merchant_trans_id: str,
        merchant_prepare_id: int,
        amount: float,
    ) -> int | None:
        try:
            provider_tx = ProviderTransaction.objects.select_for_update().get(pk=merchant_prepare_id)
        except ProviderTransaction.DoesNotExist:
            logger.error("on_complete: ProviderTransaction %d not found", merchant_prepare_id)
            return None

        if provider_tx.state == 1:
            # Already completed — idempotent
            return provider_tx.pk

        provider_tx.state = 1  # Completed
        provider_tx.save(update_fields=["state", "updated_at"])

        self.on_payment_completed(provider_tx)

        logger.info("on_complete: click_trans_id=%d order=%s", click_trans_id, merchant_trans_id)

        return provider_tx.pk

    def on_cancelled(
        self,
        click_trans_id: int,
        merchant_trans_id: str,
        merchant_prepare_id: int,
    ) -> None:
        try:
            provider_tx = ProviderTransaction.objects.select_for_update().get(pk=merchant_prepare_id)
        except ProviderTransaction.DoesNotExist:
            logger.warning("on_cancelled: ProviderTransaction %d not found", merchant_prepare_id)
            return

        provider_tx.state = -1  # Cancelled
        provider_tx.save(update_fields=["state", "updated_at"])

        self.on_payment_cancelled(provider_tx)

        logger.info("on_cancelled: click_trans_id=%d order=%s", click_trans_id, merchant_trans_id)
