"""Won 이탈·발급 규칙(AC23·AC24·AC27): 발급 계약이 있으면 Won 이탈 불가, 발급·갱신은 Won에서만."""

import pytest

from app.domain.common.errors import InvalidStateError
from tests.factories import make_sync
from tests.factories_license_contract import make_contract
from tests.support.expect import raises_with

WON_EXIT_BLOCKED = (
    "발급된 라이선스 계약이 있는 Deal은 Won에서 다른 상태로 바꿀 수 없습니다. "
    "계약 정보가 잘못되었다면 관리자에게 계약 삭제를 요청하세요."
)
DEAL_NOT_WON = "Won인 Deal의 계약만 발급하거나 갱신할 수 있습니다."


@pytest.mark.parametrize("status", ["issued_new", "issued_renewal"])
def test_ensure_can_leave_won_with_issued_raises_blocked(status: str) -> None:
    from app.domain.license_contract.errors import WonExitBlockedError  # noqa: PLC0415
    from app.domain.license_contract.won import ensure_can_leave_won  # noqa: PLC0415

    with raises_with(WonExitBlockedError, WON_EXIT_BLOCKED):
        ensure_can_leave_won(make_contract(status=status))


def test_ensure_can_leave_won_without_issued_passes() -> None:
    from app.domain.license_contract.won import ensure_can_leave_won  # noqa: PLC0415

    ensure_can_leave_won(None)


@pytest.mark.parametrize(
    "state", [("prospecting", "pipeline"), ("lost", "lost"), ("poc_completed", "commit")]
)
def test_ensure_issuable_on_non_won_raises(state: tuple[str, str]) -> None:
    from app.domain.license_contract.errors import LicenseRequiresWonError  # noqa: PLC0415
    from app.domain.license_contract.won import ensure_issuable_on  # noqa: PLC0415

    with raises_with(LicenseRequiresWonError, DEAL_NOT_WON):
        ensure_issuable_on(make_sync(*state))


def test_ensure_issuable_on_won_passes() -> None:
    from app.domain.license_contract.won import ensure_issuable_on  # noqa: PLC0415

    ensure_issuable_on(make_sync("contract_completed", "won"))


@pytest.mark.parametrize(
    ("state", "expected"),
    [
        (("contract_completed", "won"), True),
        (("prospecting", "pipeline"), False),
        (("lost", "lost"), False),
        (("poc_completed", "commit"), False),
    ],
)
def test_is_won_matches_forecast_won(state: tuple[str, str], expected: bool) -> None:
    from app.domain.license_contract.won import is_won  # noqa: PLC0415

    assert is_won(make_sync(*state)) is expected


def test_both_errors_are_invalid_state_errors() -> None:
    from app.domain.license_contract.errors import (  # noqa: PLC0415
        LicenseRequiresWonError,
        WonExitBlockedError,
    )

    assert issubclass(WonExitBlockedError, InvalidStateError)
    assert issubclass(LicenseRequiresWonError, InvalidStateError)
