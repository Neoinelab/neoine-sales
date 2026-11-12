"""응답용 UserRef 스키마는 role(admin/sales/user)을 담고 아이디·이메일은 담지 않는다."""

import pytest
from pydantic import ValidationError

from app.domain.auth.principal import Role
from app.web.schemas.user_ref import UserRef
from tests.factories import later
from tests.factories_auth import make_resigned_user, make_user


@pytest.mark.parametrize("role", [Role.ADMIN, Role.SALES, Role.USER])
def test_from_domain_carries_the_role_value(role: Role) -> None:
    """응답용 참조는 역할 값을 가진다"""
    # when: 응답 스키마로 바꾼다 (전제: 역할별 사용자)
    ref = UserRef.from_domain(make_user("hong", role).to_ref())

    # then: 역할 값이 같다
    assert ref.role == role.value


def test_from_domain_of_a_resigned_user_keeps_the_role_and_label() -> None:
    """퇴사자의 응답 참조는 역할과 (퇴사) 라벨을 가진다

    테스트 코드: US-070
    """
    # given: 퇴사한 sales
    user = make_resigned_user("hong", Role.SALES)
    user.record_login(later(1), display_name="홍길동", email="hong@corp.test")

    # when: 응답 스키마로 바꿔 직렬화한다
    dumped = UserRef.from_domain(user.to_ref()).model_dump()

    # then: 역할 sales, 퇴사 표시, 홍길동(퇴사) 라벨이다
    assert dumped["role"] == "sales"
    assert dumped["resigned"] is True
    assert dumped["label"] == "홍길동(퇴사)"


def test_serialized_fields_are_exactly_id_name_resigned_label_and_role() -> None:
    """직렬화된 참조는 id·name·resigned·label·role만 가진다

    테스트 코드: US-069
    """
    # when: 직렬화한다 (전제: user 역할 사용자)
    dumped = UserRef.from_domain(make_user("hong", Role.USER).to_ref()).model_dump(mode="json")

    # then: 키가 다섯 개뿐이고 이메일이 없다
    assert set(dumped) == {"id", "name", "resigned", "label", "role"}
    assert "hong@corp.test" not in str(dumped)


def test_role_is_required() -> None:
    """응답 참조 스키마에서 role은 필수다"""
    # when: 스키마를 읽는다
    actual = UserRef.model_json_schema()["required"]
    # then: required에 role이 있다
    assert "role" in actual


def test_unknown_role_value_is_rejected() -> None:
    """모르는 역할 값은 거절된다"""
    body = {"id": "u1", "name": "홍", "resigned": False, "label": "홍", "role": "boss"}

    # when: role이 boss인 본문을 검증한다
    with pytest.raises(ValidationError):
        UserRef.model_validate(body)
    # then: 검증 오류다
