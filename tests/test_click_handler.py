"""Regression tests for DjangoClickOrderValidator."""
import pytest
from paylinker.providers.click.webhook import OrderCheckResult
from paylinker_django.handlers.click import DjangoClickOrderValidator
from paylinker_django.models import ProviderTransaction


class _Validator(DjangoClickOrderValidator):
    def __init__(self) -> None:
        self.completed_ids: list[int] = []

    def validate_order(self, merchant_trans_id: str, amount: float) -> OrderCheckResult:
        return OrderCheckResult.ok()

    def on_payment_completed(self, provider_tx: ProviderTransaction) -> None:
        self.completed_ids.append(provider_tx.pk)

    def on_payment_cancelled(self, provider_tx: ProviderTransaction) -> None:
        pass


@pytest.fixture
def validator():
    return _Validator()


@pytest.mark.django_db(transaction=True)
def test_prepare_then_complete_calls_on_payment_completed(validator):
    """check_duplicate must not block on_complete for a state=0 (prepared) record."""
    click_trans_id = 111
    prepare_id = validator.on_prepare(click_trans_id, "order-1", 10000.0)

    # Before complete: check_duplicate must return None (state=0 is not a duplicate)
    assert validator.check_duplicate(click_trans_id) is None

    confirm_id = validator.on_complete(click_trans_id, "order-1", prepare_id, 10000.0)
    assert confirm_id == prepare_id

    # After complete: check_duplicate must return the pk (state=1)
    assert validator.check_duplicate(click_trans_id) == prepare_id

    tx = ProviderTransaction.objects.get(pk=prepare_id)
    assert tx.state == 1
    assert prepare_id in validator.completed_ids


@pytest.mark.django_db(transaction=True)
def test_duplicate_prepare_is_idempotent(validator):
    """Resending Prepare for same click_trans_id must return same prepare_id, not raise."""
    click_trans_id = 222
    prepare_id_1 = validator.on_prepare(click_trans_id, "order-2", 5000.0)
    prepare_id_2 = validator.on_prepare(click_trans_id, "order-2", 5000.0)
    assert prepare_id_1 == prepare_id_2
    assert ProviderTransaction.objects.filter(external_id=str(click_trans_id)).count() == 1


@pytest.mark.django_db(transaction=True)
def test_already_completed_duplicate_is_detected(validator):
    """check_duplicate returns pk only after state=1."""
    click_trans_id = 333
    prepare_id = validator.on_prepare(click_trans_id, "order-3", 1000.0)
    validator.on_complete(click_trans_id, "order-3", prepare_id, 1000.0)

    assert validator.check_duplicate(click_trans_id) == prepare_id


@pytest.mark.django_db(transaction=True)
def test_complete_idempotent_if_already_state1(validator):
    """Calling on_complete twice must succeed without raising."""
    click_trans_id = 444
    prepare_id = validator.on_prepare(click_trans_id, "order-4", 2000.0)
    confirm_id_1 = validator.on_complete(click_trans_id, "order-4", prepare_id, 2000.0)
    confirm_id_2 = validator.on_complete(click_trans_id, "order-4", prepare_id, 2000.0)
    assert confirm_id_1 == confirm_id_2