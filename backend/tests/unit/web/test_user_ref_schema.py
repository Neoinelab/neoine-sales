"""P1 AC-02: 응답용 UserRef 스키마는 role(admin/sales/user)을 담고 아이디·이메일은 담지 않는다."""

import pytest
from pydantic import ValidationError

from app.domain.auth.principal import Role
from app.web.schemas.user_ref import UserRef
from tests.factories import later
from tests.factories_auth import make_resigned_user, make_user


@pytest.mark.parametrize("role", [Role.ADMIN, Role.SALES, Role.USER])
def test_from_domain_carries_the_role_value(role: Role) -> None:
    ref = UserRef.from_domain(make_user("hong", role).to_ref())

    assert ref.role == role.value


def test_from_domain_of_a_resigned_user_keeps_the_role_and_label() -> None:
    user = make_resigned_user("hong", Role.SALES)
    user.record_login(later(1), display_name="홍길동", email="hong@corp.test")

    dumped = UserRef.from_domain(user.to_ref()).model_dump()

    assert dumped["role"] == "sales"
    assert dumped["resigned"] is True
    assert dumped["label"] == "홍길동(퇴사)"


def test_serialized_fields_are_exactly_id_name_resigned_label_and_role() -> None:
    dumped = UserRef.from_domain(make_user("hong", Role.USER).to_ref()).model_dump(mode="json")

    assert set(dumped) == {"id", "name", "resigned", "label", "role"}
    assert "hong@corp.test" not in str(dumped)


def test_role_is_required() -> None:
    assert "role" in UserRef.model_json_schema()["required"]


def test_unknown_role_value_is_rejected() -> None:
    body = {"id": "u1", "name": "홍", "resigned": False, "label": "홍", "role": "boss"}

    with pytest.raises(ValidationError):
        UserRef.model_validate(body)
