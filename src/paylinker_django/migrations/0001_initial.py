from django.db import migrations, models


class Migration(migrations.Migration):

    initial = True

    dependencies = []

    operations = [
        migrations.CreateModel(
            name="ProviderTransaction",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("provider", models.CharField(choices=[("payme", "Payme"), ("click", "Click")], db_index=True, max_length=20)),
                ("external_id", models.CharField(db_index=True, max_length=255)),
                ("order_id", models.CharField(db_index=True, max_length=255)),
                ("state", models.IntegerField(default=0)),
                ("amount", models.BigIntegerField(default=0)),
                ("provider_create_time", models.BigIntegerField(blank=True, null=True)),
                ("provider_perform_time", models.BigIntegerField(blank=True, null=True)),
                ("provider_cancel_time", models.BigIntegerField(blank=True, null=True)),
                ("cancel_reason", models.IntegerField(blank=True, null=True)),
                ("account_data", models.JSONField(blank=True, default=dict)),
                ("created_at", models.DateTimeField(auto_now_add=True, db_index=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
            ],
            options={
                "verbose_name": "Provider Transaction",
                "verbose_name_plural": "Provider Transactions",
                "db_table": "paylinker_provider_transactions",
                "ordering": ["-created_at"],
                "indexes": [
                    models.Index(fields=["order_id", "provider"], name="paylinker_pr_order_i_idx"),
                ],
                "constraints": [
                    models.UniqueConstraint(fields=("provider", "external_id"), name="paylinker_unique_provider_external_id"),
                ],
            },
        ),
    ]
