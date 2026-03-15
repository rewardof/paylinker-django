"""
URL patterns for paylinker-django webhooks.

Include in your project's urls.py::

    urlpatterns = [
        path("payments/", include("paylinker_django.urls")),
    ]

This provides:
    - POST /payments/webhooks/payme/
    - POST /payments/webhooks/click/
"""
from django.urls import path

from paylinker_django import views

app_name = "paylinker"

urlpatterns = [
    path("webhooks/payme/", views.payme_webhook, name="payme-webhook"),
    path("webhooks/click/", views.click_webhook, name="click-webhook"),
]
