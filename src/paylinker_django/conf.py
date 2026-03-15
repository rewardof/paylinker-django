"""
Settings access for paylinker-django.

All configuration lives under a single ``PAYLINKER`` dict in Django settings::

    PAYLINKER = {
        "PAYME": {
            "merchant_id": "...",
            "merchant_key": "...",
            "test_key": "",
            "is_test": False,
        },
        "CLICK": {
            "merchant_id": 12345,
            "service_id": 67890,
            "secret_key": "...",
        },
        "PAYME_HANDLER": "myapp.handlers.MyPaymeHandler",
        "CLICK_HANDLER": "myapp.handlers.MyClickHandler",
        "ACCOUNT_FIELD": "order_id",
    }
"""
from __future__ import annotations

from typing import Any

from django.conf import settings
from django.utils.module_loading import import_string

from paylinker import ClickConfig, PaymeConfig

DEFAULTS: dict[str, Any] = {
    "PAYME": {},
    "CLICK": {},
    "PAYME_HANDLER": None,
    "CLICK_HANDLER": None,
    "ACCOUNT_FIELD": "order_id",
}


class PaylinkerSettings:
    """Lazy accessor for the ``PAYLINKER`` settings dict with defaults."""

    def __getattr__(self, attr: str) -> Any:
        if attr not in DEFAULTS:
            raise AttributeError(f"Invalid paylinker setting: {attr!r}")
        user_settings = getattr(settings, "PAYLINKER", {})
        return user_settings.get(attr, DEFAULTS[attr])


paylinker_settings = PaylinkerSettings()


def get_payme_config() -> PaymeConfig | None:
    """Build a PaymeConfig from Django settings, or None if unconfigured."""
    conf: dict[str, Any] = paylinker_settings.PAYME
    if not conf.get("merchant_id") or not conf.get("merchant_key"):
        return None
    return PaymeConfig(
        merchant_id=str(conf["merchant_id"]),
        merchant_key=str(conf["merchant_key"]),
        test_key=str(conf.get("test_key", "")) or None,
        is_test=bool(conf.get("is_test", False)),
    )


def get_click_config() -> ClickConfig | None:
    """Build a ClickConfig from Django settings, or None if unconfigured."""
    conf: dict[str, Any] = paylinker_settings.CLICK
    if not conf.get("merchant_id") or not conf.get("secret_key"):
        return None
    kwargs: dict[str, Any] = {
        "merchant_id": int(conf["merchant_id"]),
        "service_id": int(conf.get("service_id", 0)),
        "secret_key": str(conf["secret_key"]),
    }
    if conf.get("merchant_user_id"):
        kwargs["merchant_user_id"] = int(conf["merchant_user_id"])
    if conf.get("merchant_api_secret"):
        kwargs["merchant_api_secret"] = str(conf["merchant_api_secret"])
    return ClickConfig(**kwargs)


def get_handler_class(provider: str) -> type | None:
    """Import the handler class for a provider from the dotted path in settings."""
    key = f"{provider.upper()}_HANDLER"
    dotted_path = getattr(paylinker_settings, key, None)
    if not dotted_path:
        return None
    return import_string(dotted_path)  # type: ignore[no-any-return]
