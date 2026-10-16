"""코드 삭제 규칙의 Action 사용(AC-18, R-16): 잠금 → Deal 사용 → Action 사용 순으로 거절한다."""

import pytest

from app.domain.code.errors import CodeInUseError, CodeLockedError
from app.domain.code.values import CodeKind
from app.domain.common.errors import InvalidStateError
from tests.factories_catalog import make_code
from tests.support.expect import raises_with


def test_code_in_use_by_actions_message() -> None:
    error = CodeInUseError(2, "Action")

    assert str(error) == "사용 중인 코드는 삭제할 수 없습니다. (Action 2건)"
    assert error.usage == 2
    assert isinstance(error, InvalidStateError)


def test_code_in_use_by_deals_message_is_unchanged_by_default() -> None:
    assert str(CodeInUseError(3)) == "사용 중인 코드는 삭제할 수 없습니다. (Deal 3건)"


def test_a_code_used_only_by_actions_cannot_be_deleted() -> None:
    code = make_code(CodeKind.STATUS, key="introduction")

    with raises_with(CodeInUseError, "사용 중인 코드는 삭제할 수 없습니다. (Action 4건)"):
        code.ensure_deletable(0, 4)


def test_deal_usage_is_reported_before_action_usage() -> None:
    code = make_code(CodeKind.STATUS, key="introduction")

    with raises_with(CodeInUseError, "사용 중인 코드는 삭제할 수 없습니다. (Deal 1건)"):
        code.ensure_deletable(1, 9)


def test_lock_is_reported_before_any_usage() -> None:
    code = make_code(CodeKind.STATUS, key="prospecting")

    with pytest.raises(CodeLockedError):
        code.ensure_deletable(2, 3)


def test_ensure_deletable_checks_locked_then_deals_then_actions_and_passes_when_unused() -> None:
    code = make_code(CodeKind.STATUS, key="introduction")

    code.ensure_deletable(0, 0)
    code.ensure_deletable(0)  # action_usage의 기본값은 0이다
