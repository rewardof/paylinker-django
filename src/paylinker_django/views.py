"""
Payment provider webhook views.

These views parse the HTTP request and delegate to paylinker handlers.
Handler classes are resolved from ``PAYLINKER`` settings::

    PAYLINKER = {
        "PAYME_HANDLER": "apps.payments.handlers.MyPaymeHandler",
        "CLICK_HANDLER": "apps.payments.handlers.MyClickHandler",
        ...
    }

The handler instances and paylinker handler objects are cached after first use.
"""
from __future__ import annotations

import json
import logging
from functools import lru_cache
from typing import Any

from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_POST

from paylinker import ClickWebhookHandler, PaymeRpcHandler

from paylinker_django.conf import get_click_config, get_handler_class, get_payme_config

logger = logging.getLogger("paylinker_django.views")


@lru_cache(maxsize=1)
def _get_payme_rpc_handler() -> PaymeRpcHandler:
    config = get_payme_config()
    if config is None:
        raise RuntimeError("Payme is not configured. Set PAYLINKER['PAYME'] in settings.")
    handler_cls = get_handler_class("payme")
    if handler_cls is None:
        raise RuntimeError("Set PAYLINKER['PAYME_HANDLER'] to your handler class path.")
    return PaymeRpcHandler(config, handler_cls())


@lru_cache(maxsize=1)
def _get_click_webhook_handler() -> ClickWebhookHandler:
    config = get_click_config()
    if config is None:
        raise RuntimeError("Click is not configured. Set PAYLINKER['CLICK'] in settings.")
    handler_cls = get_handler_class("click")
    if handler_cls is None:
        raise RuntimeError("Set PAYLINKER['CLICK_HANDLER'] to your handler class path.")
    return ClickWebhookHandler(config, handler_cls())


@csrf_exempt
@require_POST
def payme_webhook(request: Any) -> JsonResponse:
    """Payme JSON-RPC 2.0 endpoint.

    Payme requires ALL responses to be HTTP 200. Errors are communicated
    inside the JSON-RPC response body.
    """
    try:
        body = json.loads(request.body)
    except (json.JSONDecodeError, ValueError):
        return JsonResponse(
            {"jsonrpc": "2.0", "id": None, "error": {"code": -32700, "message": "Parse error"}},
            status=200,
        )

    authorization = request.headers.get("Authorization", "")

    try:
        handler = _get_payme_rpc_handler()
        response = handler.handle(body, authorization)
        return JsonResponse(response, status=200)
    except Exception:
        logger.exception("Payme webhook processing error")
        return JsonResponse(
            {"jsonrpc": "2.0", "id": body.get("id"), "error": {"code": -32603, "message": "Internal error"}},
            status=200,
        )


@csrf_exempt
@require_POST
def click_webhook(request: Any) -> JsonResponse:
    """Click SHOP-API endpoint.

    Click sends prepare (action=0) and complete (action=1) requests
    as either form-encoded or JSON data.
    """
    if request.content_type and "json" in request.content_type:
        try:
            payload = json.loads(request.body)
        except (json.JSONDecodeError, ValueError):
            return JsonResponse({"error": -8, "error_note": "Invalid JSON"})
    else:
        payload: dict[str, Any] = {}
        for key, value in request.POST.items():
            try:
                payload[key] = float(value) if "." in value else int(value)
            except (ValueError, TypeError):
                payload[key] = value

    try:
        handler = _get_click_webhook_handler()
        response = handler.handle(payload)
        return JsonResponse(response)
    except Exception:
        logger.exception("Click webhook processing error")
        return JsonResponse({"error": -9, "error_note": "Internal error"})
