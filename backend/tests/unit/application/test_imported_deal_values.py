"""외부에서 가져온 값 없는 Deal의 조회·부분 수정·CSV 계약."""

from dataclasses import replace
from typing import TYPE_CHECKING

import pytest

from app.application.ports.deal_repository import DealQuery
from app.domain.common.errors import InvalidValueError
from app.infra.db.deal_mapping import new_row, to_entity
from app.web.schemas.deal_response import DealDetailResponse
from tests.factories import make_deal
from tests.factories_contact import make_contact_details, make_contact_input
from tests.factories_deal import SALES, make_patch

if TYPE_CHECKING:
    from tests.unit.application.deal_env import DealEnv


def test_nullable_stored_deal_round_trips() -> None:
    """가져온 Deal의 알 수 없는 수량·금액은 저장소 왕복에서 NULL로 남는다."""
    # given: 직접 DB에서 가져온 수량·금액이 없는 행
    row = new_row(make_deal())
    row.users = None
    row.revenue_amount = None
    # when: 도메인으로 읽고 다시 저장 행으로 변환한다
    restored = new_row(to_entity(row, [], []))
    # then: 알 수 없는 값을 0이나 1로 바꾸지 않는다
    assert restored.users is None
    assert restored.revenue_amount is None


async def test_imported_values_survive_partial_update_and_response(env: DealEnv) -> None:
    """가져온 Deal의 이름만 수정해도 NULL 금액·수량을 유지하며 응답할 수 있다."""
    # given: 수량·금액이 알려지지 않은 기존 Deal
    view = await env.new_deal()
    deal = view.item.deal
    deal.details = replace(deal.details, users=None, revenue_amount=None)
    await env.uow.deals.update(deal)
    # when: 이름만 수정하고 HTTP 응답으로 변환한다
    updated = await env.update.execute(deal.id.value, make_patch(name="SK AX-EPM"), SALES)
    response = DealDetailResponse.from_view(updated)
    # then: 이름만 바뀌고 값 없는 필드는 null이다
    assert response.name == "SK AX-EPM"
    assert response.users is None
    assert response.revenue_amount is None


async def test_imported_amount_exports_empty_cell(env: DealEnv) -> None:
    """가져온 Deal의 매출금액 NULL은 CSV에서 빈 칸이다."""
    # given: 수량·금액이 알려지지 않은 기존 Deal
    view = await env.new_deal()
    deal = view.item.deal
    deal.details = replace(deal.details, users=None, revenue_amount=None)
    await env.uow.deals.update(deal)
    # when: CSV 데이터로 내보낸다
    exported = await env.export.execute(DealQuery())
    # then: 매출금액 칸이 빈 문자열이다
    assert exported.rows[0][8] == ""


def test_company_spaces_are_preserved() -> None:
    """회사명은 내부 공백을 유지하며 입력할 수 있다."""
    # when: 공백이 있는 회사명으로 연락처를 만든다
    details = make_contact_input(company="SK AX").to_details()
    # then: 원래 회사명이 유지된다
    assert details.company == "SK AX"


def test_unnamed_stored_contact_is_readable_but_input_requires_name() -> None:
    """담당자 없는 가져오기 연락처는 읽되 일반 등록의 필수 이름은 유지한다."""
    # when: 담당자 없는 저장된 상세를 복원한다
    details = make_contact_details(name="")
    # then: 이름은 빈 값이며 일반 입력에서는 계속 거절한다
    assert details.name == ""
    with pytest.raises(InvalidValueError, match="담당자명을 입력하세요"):
        make_contact_input(name="").to_details()
