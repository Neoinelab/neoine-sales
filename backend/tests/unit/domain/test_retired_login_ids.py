"""폐지된 개발용 로그인 예약 아이디 규칙 (D4): dev-admin|dev-sales|dev-user만 등록 불가."""

import pytest

from app.domain.auth.credentials import LoginId
from app.domain.common.errors import InvalidValueError
from app.domain.user.retired_login_ids import (
    ensure_not_reserved_login_id,
    is_retired_dev_login_id,
)


@pytest.mark.parametrize(
    "raw", ["dev-admin", "dev-sales", "dev-user", "DEV-ADMIN", "  Dev-User ", "Dev-Sales"]
)
def test_the_three_retired_ids_are_reserved(raw: str) -> None:
    """폐지된 개발용 아이디 세 개는 대소문자·공백과 무관하게 예약 아이디다."""
    # when: 예약 판정을 한다
    result = is_retired_dev_login_id(LoginId(raw))
    # then: 참이다
    assert result is True


@pytest.mark.parametrize(
    "raw", ["dev", "devops", "xdev-admin", "adev-user", "kim", "dev-qa", "dev-admin2", "dev-ops"]
)
def test_other_ids_including_other_dev_prefixed_ids_are_not_reserved(raw: str) -> None:
    """다른 dev- 접두 아이디를 포함해 그 밖의 아이디는 예약이 아니다."""
    # when: 예약 판정을 한다
    result = is_retired_dev_login_id(LoginId(raw))
    # then: 거짓이다
    assert result is False


@pytest.mark.parametrize("raw", ["dev-admin", "dev-sales", "dev-user", "DEV-ADMIN"])
def test_reserved_ids_are_rejected_for_registration(raw: str) -> None:
    """예약 아이디는 등록 검사에서 거절되고 문구에 소문자 아이디가 들어간다."""
    # when·then: 예약 아이디를 검사하면 InvalidValueError다
    with pytest.raises(InvalidValueError) as caught:
        ensure_not_reserved_login_id(LoginId(raw))

    # then: 문구가 개발 로그인 전용 아이디 안내다
    assert str(caught.value) == f"개발 로그인 전용 아이디는 등록할 수 없습니다: {raw.lower()}"


@pytest.mark.parametrize("raw", ["devops", "kim", "dev-qa", "dev-admin2", "dev-ops"])
def test_other_ids_pass_the_registration_check(raw: str) -> None:
    """예약이 아닌 아이디는 등록 검사를 통과한다."""
    # when·then: 일반 아이디를 검사해도 오류가 없다
    ensure_not_reserved_login_id(LoginId(raw))
