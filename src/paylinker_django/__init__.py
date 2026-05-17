"""Django integration for the paylinker payment SDK.

Quick start::

    # settings.py
    INSTALLED_APPS = [..., "paylinker_django"]

    PAYLINKER = {
        "PAYME": {"merchant_id": "...", "merchant_key": "..."},
        "CLICK": {"merchant_id": 12345, "service_id": 67890, "secret_key": "..."},
        "PAYME_HANDLER": "myapp.handlers.MyPaymeHandler",
        "CLICK_HANDLER": "myapp.handlers.MyClickHandler",
    }

    # urls.py
    path("payments/", include("paylinker_django.urls"))
"""

from __future__ import annotations

__version__ = "0.1.2"

__all__ = [
    "__version__",
    "DjangoClickOrderValidator",
    "DjangoPaymeTransactionHandler",
]


def __getattr__(name: str) -> object:
    # Lazy re-exports so importing the top-level package doesn't trigger
    # Django ORM imports before the app registry is ready.
    if name == "DjangoClickOrderValidator":
        from paylinker_django.handlers.click import DjangoClickOrderValidator

        return DjangoClickOrderValidator
    if name == "DjangoPaymeTransactionHandler":
        from paylinker_django.handlers.payme import DjangoPaymeTransactionHandler

        return DjangoPaymeTransactionHandler
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")