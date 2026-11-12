"""ListDealHistory: 최신순, 구분 필터, 각 항목에 변경자 참조. 없는 Deal은 404."""

from typing import TYPE_CHECKING

import pytest

from app.application.deal.inputs import Actor
from app.domain.auth.principal import Role
from app.domain.deal.errors import DealNotFoundError
from app.domain.deal.history import HistoryCategory
from tests.factories_deal import SALES, make_patch
from tests.support.auth_seed import seed_user
from tests.support.expect import raises_with

if TYPE_CHECKING:
    from tests.unit.application.deal_env import DealEnv


async def test_entries_are_listed_newest_first(env: DealEnv) -> None:
    """이력은 변경 시각 최신순으로 나온다.

    테스트 코드: DD-035
    """
    # given: 등록 뒤 시간을 두고 이름을 B, C로 바꾼 Deal
    view = await env.new_deal()
    code = view.item.deal.id.value
    for name in ("B", "C"):
        env.clock.advance(60)
        await env.update.execute(code, make_patch(name=name), SALES)

    # when: 이력을 읽는다
    entries = await env.history.execute(code, None)

    # then: C, B, Deal 등록 순서이고 시각이 내림차순이다
    assert [e.entry.draft.after for e in entries] == ["C", "B", "Deal 등록"]
    times = [e.entry.changed_at for e in entries]
    assert times == sorted(times, reverse=True)


async def test_entries_of_the_same_moment_show_the_later_record_first(env: DealEnv) -> None:
    """같은 시각의 이력은 나중에 기록한 것이 위에 나온다.

    테스트 코드: DD-035
    """
    # given: 한 번의 수정으로 Deal Name과 Vendor 이력이 같은 시각에 남았다
    view = await env.new_deal()
    code = view.item.deal.id.value
    oracle = await env.new_vendor("Oracle")
    await env.update.execute(
        code, make_patch(name="B", vendor_id=oracle.id), SALES
    )  # 같은 시각 두 건

    # when: 이력을 읽는다
    entries = await env.history.execute(code, None)

    # then: Vendor, Deal Name, Deal 등록 순서다
    assert [e.entry.draft.target for e in entries] == ["Vendor", "Deal Name", "Deal 등록"]


async def test_the_category_filter_keeps_only_that_category(env: DealEnv) -> None:
    """구분을 주면 그 구분의 이력만 돌려준다.

    테스트 코드: DD-036
    """
    # given: 이름과 Status를 함께 바꾼 Deal
    view = await env.new_deal()
    code = view.item.deal.id.value
    await env.update.execute(code, make_patch(name="B", status_key="introduction"), SALES)

    # when: other·created·status·partner 구분으로 각각 읽는다
    others = await env.history.execute(code, HistoryCategory("other"))
    # then: 각 구분의 항목만 나오고 이력이 없는 구분은 빈 목록이다
    created = await env.history.execute(code, HistoryCategory("created"))
    status = await env.history.execute(code, HistoryCategory("status"))

    assert [e.entry.draft.target for e in others] == ["Deal Name"]
    assert [e.entry.draft.target for e in created] == ["Deal 등록"]
    assert [(e.entry.draft.before, e.entry.draft.after) for e in status] == [
        ("기회발굴", "제품소개")
    ]
    assert await env.history.execute(code, HistoryCategory("partner")) == []


async def test_each_entry_carries_its_author(env: DealEnv) -> None:
    """이력 항목에는 변경자가 담긴다.

    테스트 코드: DD-037
    """
    # given: 영업 kim이 수정한 Deal
    boss = await seed_user(env.uow_factory, "boss", Role.ADMIN)
    view = await env.new_deal()
    code = view.item.deal.id.value

    await env.update.execute(code, make_patch(name="B"), Actor(user_id=boss.id, role=Role.ADMIN))

    # when: 이력을 읽는다
    entries = await env.history.execute(code, None)

    # then: 각 항목의 변경자가 요청자와 같다
    assert [(e.by.id, e.by.name, e.by.role) for e in entries] == [
        (boss.id, "boss", Role.ADMIN),
        (SALES.user_id, "owner", Role.SALES),
    ]


async def test_the_author_of_a_resigned_user_is_still_shown(env: DealEnv) -> None:
    """퇴사한 변경자도 퇴사 표기로 이력에 나온다.

    테스트 코드: DD-037
    """
    # given: 변경 뒤 퇴사한 사용자가 남긴 이력
    view = await env.new_deal()
    async with env.uow_factory() as uow:
        user = await uow.users.get(SALES.user_id)
        user.resign(env.clock.now())
        await uow.users.update(user)
        await uow.commit()

    # when: 이력을 읽는다
    (entry,) = await env.history.execute(view.item.deal.id.value, None)

    # then: 변경자가 퇴사 true이고 표기에 '(퇴사)'가 붙는다
    assert entry.by.resigned is True


@pytest.mark.parametrize("code", ["20261016-ZZZZ", "bad", ""])
async def test_an_unknown_deal_is_not_found(env: DealEnv, code: str) -> None:
    """없는 Deal·형식이 틀린 code의 이력은 찾을 수 없음 오류다.

    테스트 코드: DD-038
    """
    # when·then: 없는 code, 형식이 틀린 code로 이력을 읽는다 → Deal을 찾을 수 없음 오류다
    with raises_with(DealNotFoundError, "Deal을 찾을 수 없습니다."):
        await env.history.execute(code, None)
