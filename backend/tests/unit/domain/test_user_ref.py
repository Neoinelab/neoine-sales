"""AC8: 사용자 표기(label)는 UserRef 한 곳에서 만든다. 퇴사자는 `이름(퇴사)`."""

import dataclasses

import pytest

from app.domain.auth.principal import Role
from app.domain.user.value_objects import UserId, UserRef
from tests.factories import later
from tests.factories_auth import make_resigned_user, make_user
from tests.support.ids import new_id


def test_label_is_the_name_for_an_active_user() -> None:
    """재직자의 라벨은 이름이다

    테스트 코드: US-069
    """
    # given: 재직 UserRef
    ref = UserRef(id=UserId(new_id()), name="홍길동", resigned=False, role=Role.SALES)

    # when: 라벨을 읽는다
    label = ref.label
    # then: 라벨이 이름과 같다
    assert label == "홍길동"


def test_label_adds_resigned_suffix_for_a_resigned_user() -> None:
    """퇴사자의 라벨은 이름 뒤에 (퇴사)가 붙는다

    테스트 코드: US-070
    """
    # given: 퇴사 UserRef
    ref = UserRef(id=UserId(new_id()), name="홍길동", resigned=True, role=Role.SALES)

    # when: 라벨을 읽는다
    label = ref.label
    # then: 이름(퇴사)다
    assert label == "홍길동(퇴사)"


def test_user_ref_of_an_active_user_uses_display_name() -> None:
    """사용자 참조의 이름은 표시 이름이다

    테스트 코드: US-069
    """
    # given: 표시 이름이 있는 hong
    user = make_user("hong")
    user.record_login(later(1), display_name="홍길동", email=None, phone=None)

    # when: 참조로 바꾼다
    ref = user.to_ref()

    # then: 이름이 표시 이름이고 재직이다
    assert (ref.id, ref.name, ref.resigned) == (user.id, "홍길동", False)
    assert ref.label == "홍길동"


def test_user_ref_has_only_id_name_resigned_and_role_fields_and_no_login_id() -> None:
    """사용자 참조에는 아이디 필드가 없다

    테스트 코드: US-069
    """
    # when: 필드를 읽는다 (전제: hong 참조)
    names = {f.name for f in dataclasses.fields(UserRef)}
    # then: id·name·resigned·role뿐이다
    ref = make_user("hong").to_ref()

    assert names == {"id", "name", "resigned", "role"}
    assert not hasattr(ref, "login_id")


@pytest.mark.parametrize("role", [Role.ADMIN, Role.SALES, Role.USER])
def test_user_ref_carries_the_role_of_the_user(role: Role) -> None:
    """사용자 참조는 사용자의 역할을 가진다

    테스트 코드: US-069
    """
    # when: 참조로 바꾼다 (전제: 역할별 사용자)
    ref = make_user("hong", role).to_ref()

    # then: 역할이 같다
    assert ref.role is role


def test_user_ref_of_a_resigned_user_still_carries_the_role() -> None:
    """퇴사자의 참조도 자기 역할을 가진다

    테스트 코드: US-070
    """
    # when: 참조로 바꾼다 (전제: 퇴사한 sales)
    ref = make_resigned_user("hong", Role.SALES).to_ref()

    # then: 퇴사 표시와 sales 역할이다
    assert (ref.resigned, ref.role) == (True, Role.SALES)


def test_user_ref_name_falls_back_to_login_id_without_display_name() -> None:
    """표시 이름이 없으면 참조의 이름은 아이디다

    테스트 코드: US-069
    """
    # when: 참조로 바꾼다 (전제: 표시 이름이 없는 hong)
    ref = make_user("hong").to_ref()

    # then: 이름·라벨이 아이디다
    assert ref.name == "hong"
    assert ref.label == "hong"


def test_user_ref_of_a_resigned_user_is_flagged_and_labelled() -> None:
    """퇴사자의 참조는 퇴사 표시와 (퇴사) 라벨을 가진다

    테스트 코드: US-070
    """
    # given: 퇴사한 홍길동
    user = make_user("hong")
    user.record_login(later(1), display_name="홍길동", email=None, phone=None)
    user.resign(later(2))

    # when: 참조로 바꾼다
    ref = user.to_ref()

    # then: 퇴사 표시이고 라벨이 홍길동(퇴사)다
    assert ref.resigned is True
    assert ref.label == "홍길동(퇴사)"


def test_user_ref_is_immutable() -> None:
    """사용자 참조는 바꿀 수 없다"""
    # given: hong 참조
    ref = make_user("hong").to_ref()

    # when: 이름을 바꾸려 한다
    with pytest.raises(AttributeError):
        ref.name = "다른 이름"  # type: ignore[misc]
    # then: 속성 오류다
