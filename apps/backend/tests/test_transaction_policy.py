"""Transaction state machine policy: settlement-controlled statuses must not be
reachable through the user-facing generic transition endpoint."""

from app.db.models.transaction import TransactionStatus
from app.services.transactions import _SYSTEM_ONLY_TARGETS, _VALID_TRANSITIONS


def test_every_status_has_transition_entry():
    assert set(_VALID_TRANSITIONS.keys()) == set(TransactionStatus)


def test_terminal_states_have_no_exits():
    assert _VALID_TRANSITIONS[TransactionStatus.COMPLETED] == set()
    assert _VALID_TRANSITIONS[TransactionStatus.CANCELLED] == set()


def test_money_statuses_are_system_only():
    for s in (
        TransactionStatus.SIGNED,
        TransactionStatus.ESCROW_PENDING,
        TransactionStatus.ESCROW_FUNDED,
        TransactionStatus.DISBURSEMENT_PENDING,
        TransactionStatus.COMPLETED,
    ):
        assert s in _SYSTEM_ONLY_TARGETS, f"{s} must not be settable via the generic endpoint"


def test_cancellation_remains_user_reachable():
    assert TransactionStatus.CANCELLED not in _SYSTEM_ONLY_TARGETS


def test_no_path_skips_escrow():
    # COMPLETED may only be entered from DISBURSEMENT_PENDING or DISPUTED resolution
    sources = {
        src for src, targets in _VALID_TRANSITIONS.items() if TransactionStatus.COMPLETED in targets
    }
    assert sources == {TransactionStatus.DISBURSEMENT_PENDING, TransactionStatus.DISPUTED}
