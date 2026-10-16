"""ListDealHistory(AC-25): 최신순, 구분 필터, 각 항목에 변경자 참조. 없는 Deal은 404."""

from typing import TYPE_CHECKING

import pytest
from app.domain.deal.history import HistoryCategory

from app.application.deal.inputs import Actor
from app.domain.auth.principal import Role
from app.domain.deal.errors import DealNotFoundError
from tests.factories_deal import SALES, make_patch
from tests.support.auth_seed import seed_user
from tests.support.expect import raises_with

if TYPE_CHECKING:
    from tests.unit.application.deal_env import DealEnv


async def test_entries_are_listed_newest_first(env: DealEnv) -> None:
    view = await env.new_deal()
    code = view.item.deal.id.value
    for name in ("B", "C"):
        env.clock.advance(60)
        await env.update.execute(code, make_patch(name=name), SALES)

    entries = await env.history.execute(code, None)

    assert [e.entry.draft.after for e in entries] == ["C", "B", "Deal 등록"]
    times = [e.entry.changed_at for e in entries]
    assert times == sorted(times, reverse=True)


async def test_entries_of_the_same_moment_show_the_later_record_first(env: DealEnv) -> None:
    view = await env.new_deal()
    code = view.item.deal.id.value
    await env.update.execute(code, make_patch(name="B", vendor="Oracle"), SALES)  # 같은 시각 두 건

    entries = await env.history.execute(code, None)

    assert [e.entry.draft.target for e in entries] == ["Vendor", "Deal Name", "Deal 등록"]


async def test_the_category_filter_keeps_only_that_category(env: DealEnv) -> None:
    view = await env.new_deal()
    code = view.item.deal.id.value
    await env.update.execute(code, make_patch(name="B", status_key="introduction"), SALES)

    others = await env.history.execute(code, HistoryCategory("other"))
    created = await env.history.execute(code, HistoryCategory("created"))
    status = await env.history.execute(code, HistoryCategory("status"))

    assert [e.entry.draft.target for e in others] == ["Deal Name"]
    assert [e.entry.draft.target for e in created] == ["Deal 등록"]
    assert [(e.entry.draft.before, e.entry.draft.after) for e in status] == [
        ("기회발굴", "제품소개")
    ]
    assert await env.history.execute(code, HistoryCategory("partner")) == []


async def test_each_entry_carries_its_author(env: DealEnv) -> None:
    boss = await seed_user(env.uow_factory, "boss", Role.ADMIN)
    view = await env.new_deal()
    code = view.item.deal.id.value

    await env.update.execute(code, make_patch(name="B"), Actor(user_id=boss.id, role=Role.ADMIN))

    entries = await env.history.execute(code, None)

    assert [(e.by.id, e.by.name, e.by.role) for e in entries] == [
        (boss.id, "boss", Role.ADMIN),
        (SALES.user_id, "owner", Role.SALES),
    ]


async def test_the_author_of_a_resigned_user_is_still_shown(env: DealEnv) -> None:
    view = await env.new_deal()
    async with env.uow_factory() as uow:
        user = await uow.users.get(SALES.user_id)
        user.resign(env.clock.now())
        await uow.users.update(user)
        await uow.commit()

    (entry,) = await env.history.execute(view.item.deal.id.value, None)

    assert entry.by.resigned is True


@pytest.mark.parametrize("code", ["20261016-ZZZZ", "bad", ""])
async def test_an_unknown_deal_is_not_found(env: DealEnv, code: str) -> None:
    with raises_with(DealNotFoundError, "Deal을 찾을 수 없습니다."):
        await env.history.execute(code, None)
