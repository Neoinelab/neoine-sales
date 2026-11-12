"""코드 삭제 규칙의 Action 사용(CD-042, CD-043): 잠금 → Deal 사용 → Action 사용 순으로 거절한다."""

import pytest

from app.domain.code.errors import CodeInUseError, CodeLockedError
from app.domain.code.values import CodeKind
from app.domain.common.errors import InvalidStateError
from tests.factories_catalog import make_code
from tests.support.expect import raises_with


def test_code_in_use_by_actions_message() -> None:
    """Action이 쓰는 코드의 오류 문구는 Action 수를 담는다."""
    # when: Action 2건으로 오류를 만든다
    error = CodeInUseError(2, "Action")

    # then: Action 2건 문구이고 상태 오류다
    assert str(error) == "사용 중인 코드는 삭제할 수 없습니다. (Action 2건)"
    assert error.usage == 2
    assert isinstance(error, InvalidStateError)


def test_code_in_use_by_deals_message_is_unchanged_by_default() -> None:
    """단위를 주지 않으면 Deal 수 문구다."""
    # when·then: 단위 없이 오류를 만들면 Deal 3건 문구다
    assert str(CodeInUseError(3)) == "사용 중인 코드는 삭제할 수 없습니다. (Deal 3건)"


def test_a_code_used_only_by_actions_cannot_be_deleted() -> None:
    """Deal은 안 쓰고 Action만 쓰는 코드는 삭제할 수 없다.

    테스트 코드: CD-042
    """
    # given: 일반 코드
    code = make_code(CodeKind.STATUS, key="introduction")

    # when: Deal 0건·Action 4건으로 삭제 가능한지 확인한다
    with raises_with(CodeInUseError, "사용 중인 코드는 삭제할 수 없습니다. (Action 4건)"):
        code.ensure_deletable(0, 4)

    # then: Action 4건 문구가 난다(위 with 블록)


def test_deal_usage_is_reported_before_action_usage() -> None:
    """Deal과 Action이 함께 쓰면 Deal 수 문구가 먼저다.

    테스트 코드: CD-043
    """
    # given: 일반 코드
    code = make_code(CodeKind.STATUS, key="introduction")

    # when: Deal 1건·Action 9건으로 삭제 가능한지 확인한다
    with raises_with(CodeInUseError, "사용 중인 코드는 삭제할 수 없습니다. (Deal 1건)"):
        code.ensure_deletable(1, 9)

    # then: Deal 1건 문구가 난다(위 with 블록)


def test_lock_is_reported_before_any_usage() -> None:
    """잠금은 어떤 사용보다 먼저 거절한다.

    테스트 코드: CD-038
    """
    # given: 잠금 코드
    code = make_code(CodeKind.STATUS, key="prospecting")

    # when: Deal·Action이 모두 쓰는 상태에서 삭제 가능한지 확인한다
    with pytest.raises(CodeLockedError):
        code.ensure_deletable(2, 3)

    # then: 잠금 오류가 난다(위 with 블록)


def test_ensure_deletable_checks_locked_then_deals_then_actions_and_passes_when_unused() -> None:
    """아무도 쓰지 않으면 통과하고 Action 수의 기본값은 0이다.

    테스트 코드: CD-044
    """
    # given: 일반 코드
    code = make_code(CodeKind.STATUS, key="introduction")

    # when: 사용 0으로 삭제 가능한지 확인한다
    code.ensure_deletable(0, 0)
    code.ensure_deletable(0)  # action_usage의 기본값은 0이다

    # then: 오류 없이 끝난다
