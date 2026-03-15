"""Minimal Django settings for running paylinker-django tests."""

SECRET_KEY = "test-secret-key-not-for-production"

INSTALLED_APPS = [
    "django.contrib.contenttypes",
    "django.contrib.auth",
    "paylinker_django",
]

DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.sqlite3",
        "NAME": ":memory:",
    }
}

DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

PAYLINKER = {
    "PAYME": {
        "merchant_id": "test_merchant",
        "merchant_key": "test_key_123",
    },
    "CLICK": {
        "merchant_id": 12345,
        "service_id": 67890,
        "secret_key": "test_secret",
    },
    "ACCOUNT_FIELD": "order_id",
}
