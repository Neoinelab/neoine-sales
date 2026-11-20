"""DealQuery.owner_name(DL-R39) 정규화·검증: 트림·공백뿐·NUL·길이·owner_user_id와의 배타."""

import pytest

from app.application.ports.deal_repository import DealQuery
from app.domain.common.errors import InvalidValueError
from tests.support.user_ids import uid

EXCLUSIVE = "담당자는 사용자 id와 이름 중 하나로만 지정하세요."


def test_owner_name_is_trimmed_and_wildcard_characters_are_kept() -> None:
    """앞뒤 공백은 지우고 안쪽 글자(%·_·공백)는 그대로 둔다.

    테스트 코드: DL-133
    """
    # when: 앞뒤 공백이 있는 값으로 만든다
    query = DealQuery(owner_name="  김_영% 업  ")
    # then: 앞뒤만 지운 값이다
    assert query.owner_name == "김_영% 업"


@pytest.mark.parametrize("blank", ["", " ", "   \t "])
def test_blank_owner_name_means_no_condition(blank: str) -> None:
    """공백뿐인 값은 조건이 없다(None).

    테스트 코드: DL-133
    """
    # when: 공백뿐인 값으로 만든다
    query = DealQuery(owner_name=blank)
    # then: 조건 없음이다
    assert query.owner_name is None


def test_owner_name_defaults_to_none() -> None:
    """지정하지 않으면 조건이 없다.

    테스트 코드: DL-133
    """
    # when·then: 기본값
    assert DealQuery().owner_name is None


def test_owner_name_of_100_characters_is_accepted_and_101_is_invalid() -> None:
    """트림 후 100자는 되고 101자는 InvalidValueError다.

    테스트 코드: DL-133
    """
    # when: 100자로 만든다
    ok = DealQuery(owner_name="가" * 100)
    # then: 그대로다
    assert ok.owner_name == "가" * 100
    # when·then: 101자는 거절한다
    with pytest.raises(InvalidValueError):
        DealQuery(owner_name="가" * 101)


def test_owner_name_with_nul_is_invalid_with_the_fixed_message() -> None:
    """NUL 문자가 있으면 고정 문구의 InvalidValueError다.

    테스트 코드: DL-133
    """
    # when·then: NUL이 든 값을 거절한다
    with pytest.raises(InvalidValueError) as caught:
        DealQuery(owner_name="a\x00b")
    assert str(caught.value) == "담당자에는 NUL 문자를 쓸 수 없습니다"


def test_owner_name_together_with_owner_user_id_is_invalid() -> None:
    """owner_name과 owner_user_id를 함께 주면 InvalidValueError다.

    테스트 코드: DL-134
    """
    # when·then: 둘을 함께 만들면 고정 문구로 거절한다
    with pytest.raises(InvalidValueError) as caught:
        DealQuery(owner_name="영업", owner_user_id=uid("park"))
    assert str(caught.value) == EXCLUSIVE


def test_blank_owner_name_with_owner_user_id_is_not_a_simultaneous_specification() -> None:
    """공백뿐인 owner_name은 조건이 없으므로 owner_user_id와 함께여도 오류가 아니다.

    테스트 코드: DL-134
    """
    # when: 공백뿐인 이름과 id를 함께 만든다
    park = uid("park")
    query = DealQuery(owner_name="   ", owner_user_id=park)
    # then: id 조건만 남는다
    assert (query.owner_name, query.owner_user_id) == (None, park)
