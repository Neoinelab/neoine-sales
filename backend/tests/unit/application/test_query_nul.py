"""검색 조건 객체: 텍스트 조건에 NUL 문자가 있으면 InvalidValueError(DB 500 방지)."""

from typing import TYPE_CHECKING

import pytest

from app.application.ports.customer_repository import CustomerQuery
from app.application.ports.deal_action_repository import DealActionQuery
from app.application.ports.deal_repository import DealQuery
from app.application.ports.partner_repository import PartnerQuery
from app.domain.common.errors import InvalidValueError

if TYPE_CHECKING:
    from collections.abc import Callable

NUL = "a\x00b"


@pytest.mark.parametrize(
    "build",
    [
        pytest.param(lambda: CustomerQuery(keyword=NUL), id="customer-keyword"),
        pytest.param(lambda: PartnerQuery(keyword=NUL), id="partner-keyword"),
        pytest.param(lambda: DealQuery(keyword=NUL), id="deal-keyword"),
        pytest.param(lambda: DealQuery(owner=NUL), id="deal-owner"),
        pytest.param(lambda: DealQuery(vendor=NUL), id="deal-vendor"),
        pytest.param(lambda: DealActionQuery(keyword=NUL), id="action-keyword"),
        pytest.param(lambda: DealActionQuery(actor=NUL), id="action-actor"),
    ],
)
def test_query_rejects_nul_in_text_condition(build: Callable[[], object]) -> None:
    with pytest.raises(InvalidValueError):
        build()


def test_query_still_accepts_normal_text_conditions() -> None:
    assert CustomerQuery(keyword=" 네오인 ").keyword == "네오인"
    assert DealActionQuery(actor="kim", keyword="a\tb").keyword == "a\tb"
