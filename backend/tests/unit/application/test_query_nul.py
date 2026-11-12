"""검색 조건 객체: 텍스트 조건에 NUL 문자가 있으면 InvalidValueError(DB 500 방지)."""

from typing import TYPE_CHECKING

import pytest

from app.application.ports.contact_repository import ContactQuery
from app.application.ports.deal_action_repository import DealActionQuery
from app.application.ports.deal_repository import DealQuery
from app.domain.common.errors import InvalidValueError
from tests.factories import make_deal_code

if TYPE_CHECKING:
    from collections.abc import Callable

NUL = "a\x00b"


@pytest.mark.parametrize(
    "build",
    [
        pytest.param(lambda: ContactQuery(keyword=NUL), id="contact-keyword"),
        pytest.param(lambda: DealQuery(keyword=NUL), id="deal-keyword"),
        pytest.param(
            lambda: DealActionQuery(deal_code=make_deal_code(), keyword=NUL), id="action-keyword"
        ),
    ],
)
def test_query_rejects_nul_in_text_condition(build: Callable[[], object]) -> None:
    """텍스트 조건(고객·Deal·Action 검색어)에 NUL 문자가 있으면 InvalidValueError다."""
    # when·then: NUL이 든 검색어로 조건을 만들면 InvalidValueError다
    with pytest.raises(InvalidValueError):
        build()


def test_query_still_accepts_normal_text_conditions() -> None:
    """NUL이 없는 일반 텍스트 조건은 그대로 받는다."""
    # when·then: 공백은 지우고 탭 같은 일반 문자는 보존한다
    assert ContactQuery(keyword=" 네오인 ").keyword == "네오인"
    assert DealActionQuery(deal_code=make_deal_code(), keyword="a\tb").keyword == "a\tb"


def test_action_query_takes_a_user_id_not_a_free_text_actor() -> None:
    """Action 조회 조건의 담당자는 사용자 id이며 자유 텍스트 `actor`는 없다.

    테스트 코드: NA-036
    """
    # when: 담당자 조건 없이 조회 조건을 만든다
    query = DealActionQuery(deal_code=make_deal_code())
    # then: 자유 텍스트 actor 필드는 없고 actor_user_id는 비어 있다
    assert not hasattr(query, "actor")
    assert query.actor_user_id is None
    # when·then: 폐지된 actor 인자를 주면 TypeError다
    with pytest.raises(TypeError):
        DealActionQuery(deal_code=make_deal_code(), actor="kim")  # type: ignore[call-arg]
