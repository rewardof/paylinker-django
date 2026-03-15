from django.contrib import admin

from paylinker_django.models import ProviderTransaction


@admin.register(ProviderTransaction)
class ProviderTransactionAdmin(admin.ModelAdmin):
    list_display = ("pk", "provider", "external_id", "order_id", "state", "amount", "created_at")
    list_filter = ("provider", "state")
    search_fields = ("external_id", "order_id")
    readonly_fields = ("created_at", "updated_at")
    ordering = ("-created_at",)
