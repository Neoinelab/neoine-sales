"""GetDealDeletionImpact: 삭제 영향 건수. 필터용 facets는 폐지되었다(Vendor)."""

import importlib
from dataclasses import fields
from typing import TYPE_CHECKING

import pytest

from app.application.deal_action.register_deal_action import RegisterDealAction
from app.application.ports.deal_repository import DealDeletionImpact
from app.domain.deal.errors import DealNotFoundError
from tests.factories import make_register_input
from tests.factories_deal import SALES, make_patch

if TYPE_CHECKING:
    from tests.unit.application.deal_env import DealEnv


def test_the_facets_use_case_is_gone() -> None:
    """필터용 facets 유스케이스는 폐지되어 가져올 수 없다."""
    # when·then: 폐지된 모듈을 가져온다 → 모듈 없음 오류다
    with pytest.raises(ModuleNotFoundError):
        importlib.import_module("app.application.deal.list_facets")


async def test_the_impact_counts_the_history_and_actions_that_would_be_deleted(
    env: DealEnv,
) -> None:
    """삭제 영향은 그 Deal의 이력·Action 건수다.

    테스트 코드: DD-047
    """
    # given: 등록·수정·Action 3건을 거친 Deal
    view = await env.new_deal()
    await env.update.execute(view.item.deal.id.value, make_patch(name="변경"), SALES)
    register = RegisterDealAction(env.uow_factory, env.clock, env.storage)
    for _ in range(3):
        env.clock.advance(60)
        await register.execute(view.item.deal.id.value, make_register_input(), SALES)

    # when: 삭제 영향을 읽는다
    impact = await env.impact.execute(view.item.deal.id.value)

    # 이력 = 등록 1 + 수정 1 + Action 등록마다 category=action 1건 x 3
    # then: 이력 5건(등록 1·수정 1·Action 3), Action 3건, 첨부·계약·Comment 0이다
    assert impact == DealDeletionImpact(
        history_count=1 + 1 + 3,
        action_count=3,
        attachment_count=0,
        license_contract_count=0,
        comment_count=0,
    )


async def test_a_new_deal_has_only_its_registration_entry(env: DealEnv) -> None:
    """새 Deal의 삭제 영향은 등록 이력 1건뿐이다.

    테스트 코드: DD-048
    """
    # given: 방금 등록한 Deal
    view = await env.new_deal()

    # when: 삭제 영향을 읽는다
    impact = await env.impact.execute(view.item.deal.id.value)

    # then: 이력 1건, 나머지 0이다
    assert impact == DealDeletionImpact(
        history_count=1,
        action_count=0,
        attachment_count=0,
        license_contract_count=0,
        comment_count=0,
    )


async def test_the_impact_of_another_deal_is_not_counted(env: DealEnv) -> None:
    """다른 Deal의 건수는 삭제 영향에 섞이지 않는다.

    테스트 코드: DD-048
    """
    # given: 이력이 늘어난 Deal과 새 Deal
    first = await env.new_deal()
    await env.new_deal()
    await env.update.execute(first.item.deal.id.value, make_patch(name="변경"), SALES)

    other = await env.new_deal()

    # when: 새 Deal의 삭제 영향을 읽는다
    history_count = (await env.impact.execute(other.item.deal.id.value)).history_count
    # then: 새 Deal의 이력은 1건이다
    assert history_count == 1


@pytest.mark.parametrize("code", ["20261016-ZZZZ", "not-a-code"])
async def test_the_impact_of_an_unknown_or_malformed_code_is_not_found(
    env: DealEnv, code: str
) -> None:
    """없는 Deal·형식이 틀린 code의 삭제 영향은 찾을 수 없음 오류다.

    테스트 코드: DD-049
    """
    # when·then: 없는 code, 형식이 틀린 code로 삭제 영향을 읽는다 → Deal을 찾을 수 없음 오류다
    with pytest.raises(DealNotFoundError):
        await env.impact.execute(code)


async def test_the_impact_counts_history_actions_attachments_contracts_and_comments_only(
    env: DealEnv,
) -> None:
    """삭제 영향은 이력·Action·첨부·계약·Comment 다섯 건수만 가진다.

    테스트 코드: DD-047
    """
    view = await env.new_deal()

    impact = await env.impact.execute(view.item.deal.id.value)

    # when: 결과 형식을 확인한다
    assert {f.name for f in fields(impact)} == {
        "history_count",
        "action_count",
        "attachment_count",
        "license_contract_count",
        "comment_count",
    }
    # then: 필드가 정확히 다섯 건수 이름이다
    assert not hasattr(impact, "partner_meeting_count")


async def test_the_impact_counts_the_comments_of_the_deal_but_not_of_other_deals(
    env: DealEnv,
) -> None:
    """삭제 영향의 comment_count는 그 Deal 소속 Comment(Deal Comment + Action Comment) 수다.

    테스트 코드: CM-039, DD-047
    """
    # given: Deal D(Deal Comment 1건, Action Comment 2건)와 Comment 1건이 있는 다른 Deal E
    from tests.factories import make_deal_action  # noqa: PLC0415
    from tests.factories_comment import make_comment  # noqa: PLC0415
    from tests.support.user_ids import ACTOR_ID  # noqa: PLC0415

    deal = await env.new_deal()
    other = await env.new_deal()
    code, other_code = deal.item.deal.id, other.item.deal.id
    action = make_deal_action(deal_code=code)
    await env.uow.deal_actions.add(action)
    for index, linked in enumerate((None, action.id, action.id)):
        await env.uow.deal_comments.add(
            make_comment(deal_code=code, action_id=linked, body=f"c{index}", author=ACTOR_ID)
        )
    await env.uow.deal_comments.add(make_comment(deal_code=other_code, author=ACTOR_ID))

    # when: 두 Deal의 삭제 영향을 읽는다
    impact = await env.impact.execute(code.value)
    other_impact = await env.impact.execute(other_code.value)

    # then: D는 3건, E는 1건이다
    assert (impact.comment_count, other_impact.comment_count) == (3, 1)
