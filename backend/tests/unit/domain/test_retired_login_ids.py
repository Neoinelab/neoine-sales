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
    assert is_retired_dev_login_id(LoginId(raw)) is True


@pytest.mark.parametrize(
    "raw", ["dev", "devops", "xdev-admin", "adev-user", "kim", "dev-qa", "dev-admin2", "dev-ops"]
)
def test_other_ids_including_other_dev_prefixed_ids_are_not_reserved(raw: str) -> None:
    assert is_retired_dev_login_id(LoginId(raw)) is False


@pytest.mark.parametrize("raw", ["dev-admin", "dev-sales", "dev-user", "DEV-ADMIN"])
def test_reserved_ids_are_rejected_for_registration(raw: str) -> None:
    with pytest.raises(InvalidValueError) as caught:
        ensure_not_reserved_login_id(LoginId(raw))

    assert str(caught.value) == f"개발 로그인 전용 아이디는 등록할 수 없습니다: {raw.lower()}"


@pytest.mark.parametrize("raw", ["devops", "kim", "dev-qa", "dev-admin2", "dev-ops"])
def test_other_ids_pass_the_registration_check(raw: str) -> None:
    ensure_not_reserved_login_id(LoginId(raw))
