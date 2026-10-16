"""연락처 일괄 조회 결과에 id가 빠졌을 때(R3 리뷰 Minor 2): KeyError 대신 정해진 도메인 오류.

Port `get_many`는 없는 id를 결과에서 뺀다. 그 빈 자리를 Deal 행을 조용히 빼지 않고
`ContactNotFoundError`(404 계열)로 알린다. Fake 저장소가 FK 모사로 삭제를 막으므로, 읽기 결과에서
특정 id를 빼는 식으로 "id가 빠진 결과"를 만든다.
"""

from typing import TYPE_CHECKING

import pytest

from app.application.ports.deal_repository import DealQuery
from app.domain.common.errors import NotFoundError
from app.domain.contact.errors import ContactNotFoundError
from tests.factories_deal import make_draft

if TYPE_CHECKING:
    from collections.abc import Collection, Mapping

    from app.domain.contact.entities import Contact
    from app.domain.contact.values import ContactId
    from tests.unit.application.deal_env import DealEnv


def _drop_from_get_many(env: DealEnv, monkeypatch: pytest.MonkeyPatch, gone: ContactId) -> None:
    original = env.uow.contacts.get_many

    async def get_many(contact_ids: Collection[ContactId]) -> Mapping[ContactId, Contact]:
        found = await original(contact_ids)
        return {cid: contact for cid, contact in found.items() if cid != gone}

    monkeypatch.setattr(env.uow.contacts, "get_many", get_many)


async def test_list_with_a_missing_customer_raises_contact_not_found(
    env: DealEnv, monkeypatch: pytest.MonkeyPatch
) -> None:
    view = await env.new_deal(customer=make_draft(company="한빛은행", name="정민수"))
    _drop_from_get_many(env, monkeypatch, view.item.deal.customer_id)

    with pytest.raises(ContactNotFoundError):
        await env.list.execute(DealQuery())


async def test_list_with_a_missing_partner_raises_contact_not_found(
    env: DealEnv, monkeypatch: pytest.MonkeyPatch
) -> None:
    view = await env.new_deal(
        customer=make_draft(company="한빛은행", name="정민수"),
        partner=make_draft(company="코어테크", name="민지훈"),
    )
    partner_id = view.item.deal.active_partner_id()
    assert partner_id is not None
    _drop_from_get_many(env, monkeypatch, partner_id)

    with pytest.raises(ContactNotFoundError):
        await env.list.execute(DealQuery())


async def test_the_error_is_a_not_found_so_that_it_maps_to_404(
    env: DealEnv, monkeypatch: pytest.MonkeyPatch
) -> None:
    view = await env.new_deal(customer=make_draft(company="한빛은행", name="정민수"))
    _drop_from_get_many(env, monkeypatch, view.item.deal.customer_id)

    with pytest.raises(NotFoundError):
        await env.list.execute(DealQuery())


async def test_the_detail_with_a_missing_customer_raises_contact_not_found(
    env: DealEnv, monkeypatch: pytest.MonkeyPatch
) -> None:
    view = await env.new_deal(customer=make_draft(company="한빛은행", name="정민수"))
    _drop_from_get_many(env, monkeypatch, view.item.deal.customer_id)

    with pytest.raises(ContactNotFoundError):
        await env.get.execute(view.item.deal.id.value)


async def test_a_gap_in_one_row_does_not_silently_drop_it_from_the_page(
    env: DealEnv, monkeypatch: pytest.MonkeyPatch
) -> None:
    broken = await env.new_deal(customer=make_draft(company="깨진사", name="깨진이", email=None))
    await env.new_deal(customer=make_draft(company="정상사", name="정상이", email=None))
    _drop_from_get_many(env, monkeypatch, broken.item.deal.customer_id)

    with pytest.raises(ContactNotFoundError):
        await env.list.execute(DealQuery())
