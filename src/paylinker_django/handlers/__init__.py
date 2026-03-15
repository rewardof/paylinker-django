"""
Abstract handler bases for Django projects.

These classes implement paylinker's ``TransactionHandler`` and ``OrderValidator``
protocols using the ``ProviderTransaction`` model. Projects subclass them and
override the business-logic hooks (``validate_order``, ``on_payment_performed``,
etc.).
"""
from paylinker_django.handlers.click import DjangoClickOrderValidator
from paylinker_django.handlers.payme import DjangoPaymeTransactionHandler

__all__ = ["DjangoPaymeTransactionHandler", "DjangoClickOrderValidator"]
