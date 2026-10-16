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
        pytest.param(lambda: DealQuery(vendor=NUL), id="deal-vendor"),
        pytest.param(
            lambda: DealActionQuery(deal_code=make_deal_code(), keyword=NUL), id="action-keyword"
        ),
    ],
)
def test_query_rejects_nul_in_text_condition(build: Callable[[], object]) -> None:
    with pytest.raises(InvalidValueError):
        build()


def test_query_still_accepts_normal_text_conditions() -> None:
    assert ContactQuery(keyword=" 네오인 ").keyword == "네오인"
    assert DealActionQuery(deal_code=make_deal_code(), keyword="a\tb").keyword == "a\tb"


def test_action_query_takes_a_user_id_not_a_free_text_actor() -> None:
    query = DealActionQuery(deal_code=make_deal_code())

    assert not hasattr(query, "actor")
    assert query.actor_user_id is None
    with pytest.raises(TypeError):
        DealActionQuery(deal_code=make_deal_code(), actor="kim")  # type: ignore[call-arg]
