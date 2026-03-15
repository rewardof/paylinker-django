"""
Provider-specific transaction tracking.

This model stores the provider's own transaction lifecycle state, which
is independent of any business-level Order or Payment model. It uses a
plain ``order_id`` string field (not a FK) so it works with any project's
domain models.

Payme states: 1 (created) → 2 (performed) | -1 (cancelled before) | -2 (cancelled after)
Click phases: prepare (state=0) → complete (state=1) | cancelled (state=-1)
"""
from __future__ import annotations

from django.db import models


class ProviderTransaction(models.Model):
    class Provider(models.TextChoices):
        PAYME = "payme", "Payme"
        CLICK = "click", "Click"

    provider = models.CharField(max_length=20, choices=Provider.choices, db_index=True)

    # Provider's transaction ID (payme_id or click_trans_id).
    external_id = models.CharField(max_length=255, db_index=True)

    # Merchant's order reference — intentionally a plain string, not a FK,
    # so this model stays decoupled from any specific Order model.
    order_id = models.CharField(max_length=255, db_index=True)

    # Provider-specific state code.
    state = models.IntegerField(default=0)

    # Amount in provider's smallest unit (tiyin for Payme, UZS for Click).
    amount = models.BigIntegerField(default=0)

    # Provider timestamps (milliseconds for Payme, unused for Click).
    provider_create_time = models.BigIntegerField(null=True, blank=True)
    provider_perform_time = models.BigIntegerField(null=True, blank=True)
    provider_cancel_time = models.BigIntegerField(null=True, blank=True)
    cancel_reason = models.IntegerField(null=True, blank=True)

    # Payme account data (e.g., {"order_id": "..."}).
    account_data = models.JSONField(default=dict, blank=True)

    created_at = models.DateTimeField(auto_now_add=True, db_index=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "paylinker_provider_transactions"
        verbose_name = "Provider Transaction"
        verbose_name_plural = "Provider Transactions"
        ordering = ["-created_at"]
        constraints = [
            models.UniqueConstraint(
                fields=["provider", "external_id"],
                name="paylinker_unique_provider_external_id",
            ),
        ]
        indexes = [
            models.Index(fields=["order_id", "provider"]),
        ]

    def __str__(self) -> str:
        return f"ProviderTx {self.provider}:{self.external_id} (state={self.state})"
