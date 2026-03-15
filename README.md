# paylinker-django

Django integration for [paylinker](https://github.com/tohirbek/paylinker) payment SDK.

Provides webhook views, provider transaction tracking, and abstract handler
bases for Click and Payme payment providers in Uzbekistan.

## Installation

```bash
pip install paylinker-django
```

## Quick Start

### 1. Add to INSTALLED_APPS

```python
INSTALLED_APPS = [
    ...
    "paylinker_django",
]
```

### 2. Configure settings

```python
PAYLINKER = {
    "PAYME": {
        "merchant_id": env("PAYME_MERCHANT_ID"),
        "merchant_key": env("PAYME_SECRET_KEY"),
        "test_key": env("PAYME_TEST_KEY", default=""),
        "is_test": env.bool("PAYME_IS_TEST", default=False),
    },
    "CLICK": {
        "merchant_id": int(env("CLICK_MERCHANT_ID")),
        "service_id": int(env("CLICK_SERVICE_ID")),
        "secret_key": env("CLICK_SECRET_KEY"),
    },
    "PAYME_HANDLER": "apps.payments.handlers.MyPaymeHandler",
    "CLICK_HANDLER": "apps.payments.handlers.MyClickHandler",
    "ACCOUNT_FIELD": "order_id",
}
```

### 3. Implement handlers

```python
# apps/payments/handlers.py
from paylinker.providers.click.enums import ClickErrorCode
from paylinker.providers.click.webhook import OrderCheckResult
from paylinker.providers.payme.rpc_handler import PaymeError
from paylinker_django.handlers import DjangoClickOrderValidator, DjangoPaymeTransactionHandler

from .models import Order


class MyPaymeHandler(DjangoPaymeTransactionHandler):
    def validate_order(self, order_id, amount_tiyin):
        try:
            order = Order.objects.get(pk=order_id)
        except Order.DoesNotExist:
            raise PaymeError(-31050, "Не найден", "Topilmadi", "Not found", "order_id")
        if order.is_paid:
            raise PaymeError(-31099, "Оплачен", "To'langan", "Already paid")
        if int(order.amount * 100) != amount_tiyin:
            raise PaymeError(-31001, "Неверная сумма", "Noto'g'ri summa", "Wrong amount")

    def on_payment_performed(self, provider_tx):
        order = Order.objects.get(pk=provider_tx.order_id)
        order.mark_paid()

    def on_payment_cancelled(self, provider_tx, reason, was_performed):
        if was_performed:
            order = Order.objects.get(pk=provider_tx.order_id)
            order.refund()


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
```

### 4. Include URLs

```python
# urls.py
from django.urls import include, path

urlpatterns = [
    path("payments/", include("paylinker_django.urls")),
]
```

This exposes:
- `POST /payments/webhooks/payme/` — Payme JSON-RPC endpoint
- `POST /payments/webhooks/click/` — Click SHOP-API endpoint

### 5. Run migrations

```bash
python manage.py migrate paylinker_django
```

## Architecture

```
paylinker          — Core SDK (framework-agnostic)
  ├── configs, providers, signing, schemas, HTTP clients
  └── handler protocols: TransactionHandler (Payme), OrderValidator (Click)

paylinker-django   — Django adapter (this package)
  ├── ProviderTransaction model   — tracks provider-specific state
  ├── DjangoPaymeTransactionHandler  — manages Payme lifecycle + model CRUD
  ├── DjangoClickOrderValidator      — manages Click lifecycle + model CRUD
  ├── Webhook views                  — parse HTTP → delegate to handlers
  └── Settings integration           — PAYLINKER dict in Django settings
```

Your project only implements business-logic hooks:
- `validate_order()` — order existence and amount verification
- `on_payment_performed()` / `on_payment_completed()` — post-payment actions
- `on_payment_cancelled()` — cancellation handling

## Generating payment URLs

```python
from paylinker_django.conf import get_payme_config, get_click_config
from paylinker import PaymeProvider, ClickProvider

# Payme
payme = PaymeProvider(get_payme_config())
url = payme.generate_payment_url(
    amount=100000,  # tiyin
    transaction_param=str(order.pk),
    account_field="order_id",
)

# Click
click = ClickProvider(get_click_config())
url = click.generate_payment_url(
    amount=1000.0,  # UZS
    transaction_param=str(order.pk),
)
```
