"""DeleteDeal(AC-27, Q6): 없음 404 -> 권한 403 -> code 확인 422 순서, CASCADE 삭제, 운영 로그."""

import logging
import re
from datetime import datetime
from typing import TYPE_CHECKING

import pytest

from app.application.deal.inputs import Actor
from app.domain.auth.principal import Role
from app.domain.common.errors import InvalidValueError
from app.domain.contact.values import ContactKind
from app.domain.deal.errors import (
    DealCodeMismatchError,
    DealDeleteForbiddenError,
    DealNotFoundError,
)
from tests.factories import make_deal_action
from tests.factories_deal import SALES, make_draft, make_patch
from tests.support.auth_seed import seed_user
from tests.support.expect import raises_with

if TYPE_CHECKING:
    from app.application.deal.dto import DealView
    from tests.unit.application.deal_env import DealEnv

NOT_FOUND = "Deal을 찾을 수 없습니다."
FORBIDDEN = "본인 Deal 또는 admin만 삭제할 수 있습니다."
MISMATCH = "Deal code가 일치하지 않습니다."


async def _deal_with_dependents(env: DealEnv) -> DealView:
    view = await env.new_deal(partner=make_draft(company="코어테크", name="민지훈"))
    await env.update.execute(view.item.deal.id.value, make_patch(name="B"), SALES)  # 이력 +1
    await env.uow.deal_actions.add(make_deal_action(deal_code=view.item.deal.id))
    return view


class TestDelete:
    async def test_the_owner_deletes_with_the_matching_code(self, env: DealEnv) -> None:
        view = await env.new_deal()
        code = view.item.deal.id.value

        await env.delete.execute(code, code, SALES)

        with raises_with(DealNotFoundError, NOT_FOUND):
            await env.get.execute(code)
        assert env.uow.deals._items == {}

    async def test_an_admin_deletes_a_deal_of_another_owner(self, env: DealEnv) -> None:
        boss = await seed_user(env.uow_factory, "boss", Role.ADMIN)
        view = await env.new_deal()
        code = view.item.deal.id.value

        await env.delete.execute(code, code, Actor(user_id=boss.id, role=Role.ADMIN))

        assert env.uow.deals._items == {}

    async def test_history_actions_and_links_go_with_the_deal_but_contacts_and_users_stay(
        self, env: DealEnv
    ) -> None:
        view = await _deal_with_dependents(env)
        code = view.item.deal.id.value
        contacts = set(env.uow.contacts._items)
        users = set(env.uow.users._items)

        await env.delete.execute(code, code, SALES)

        assert env.uow.deal_history._items == {}
        assert env.uow.deal_actions._items == {}
        assert set(env.uow.contacts._items) == contacts
        assert {c.kind for c in env.uow.contacts._items.values()} == {
            ContactKind.CUSTOMER,
            ContactKind.PARTNER,
        }
        assert set(env.uow.users._items) == users

    async def test_other_deals_are_untouched(self, env: DealEnv) -> None:
        first = await env.new_deal()
        second = await env.new_deal()

        await env.delete.execute(first.item.deal.id.value, first.item.deal.id.value, SALES)

        assert list(env.uow.deals._items) == [second.item.deal.id]
        assert len(env.uow.deal_history._items) == 1  # 남은 Deal의 등록 이력

    async def test_partner_meetings_of_the_deal_go_with_it_and_other_deals_keep_theirs(
        self, env: DealEnv
    ) -> None:
        from tests.factories_partner_meeting import make_meeting  # noqa: PLC0415
        from tests.support.user_ids import ACTOR_ID  # noqa: PLC0415

        doomed = await env.new_deal()
        kept = await env.new_deal()
        async with env.uow_factory() as uow:
            await uow.partner_meetings.add(
                make_meeting(deal_code=doomed.item.deal.id, author=ACTOR_ID)
            )
            survivor = make_meeting(deal_code=kept.item.deal.id, author=ACTOR_ID)
            await uow.partner_meetings.add(survivor)
            await uow.commit()

        await env.delete.execute(doomed.item.deal.id.value, doomed.item.deal.id.value, SALES)

        async with env.uow_factory() as uow:
            assert (await uow.partner_meetings.get(survivor.id)).meeting.id == survivor.id
            assert uow.partner_meetings.count_of_deal(doomed.item.deal.id) == 0  # type: ignore[attr-defined]

    async def test_the_deletion_is_committed(self, env: DealEnv) -> None:
        view = await env.new_deal()
        commits = env.uow.commits

        await env.delete.execute(view.item.deal.id.value, view.item.deal.id.value, SALES)

        assert env.uow.commits == commits + 1


class TestOrderOfChecks:
    async def test_an_unknown_deal_is_not_found_before_anything_else(self, env: DealEnv) -> None:
        viewer = Actor(user_id=SALES.user_id, role=Role.USER)

        with raises_with(DealNotFoundError, NOT_FOUND):
            await env.delete.execute("20261016-ZZZZ", "wrong", viewer)

    async def test_a_malformed_code_is_not_found(self, env: DealEnv) -> None:
        with raises_with(DealNotFoundError, NOT_FOUND):
            await env.delete.execute("bad", "bad", SALES)

    async def test_another_sales_user_is_forbidden_even_with_a_wrong_confirmation(
        self, env: DealEnv
    ) -> None:
        view = await env.new_deal()
        park = await seed_user(env.uow_factory, "park", Role.SALES)

        with raises_with(DealDeleteForbiddenError, FORBIDDEN):
            await env.delete.execute(
                view.item.deal.id.value, "wrong", Actor(user_id=park.id, role=Role.SALES)
            )

        assert len(env.uow.deals._items) == 1

    async def test_a_read_only_user_is_forbidden(self, env: DealEnv) -> None:
        view = await env.new_deal()
        viewer = await seed_user(env.uow_factory, "viewer", Role.USER)
        code = view.item.deal.id.value

        with raises_with(DealDeleteForbiddenError, FORBIDDEN):
            await env.delete.execute(code, code, Actor(user_id=viewer.id, role=Role.USER))

    @pytest.mark.parametrize("typed", ["", "wrong", "20260101-9999"])
    async def test_a_wrong_confirmation_is_rejected_and_nothing_is_deleted(
        self, env: DealEnv, typed: str
    ) -> None:
        view = await _deal_with_dependents(env)
        commits = env.uow.commits

        with raises_with(DealCodeMismatchError, MISMATCH):
            await env.delete.execute(view.item.deal.id.value, typed, SALES)

        assert len(env.uow.deals._items) == 1
        assert len(env.uow.deal_history._items) == 2
        assert len(env.uow.deal_actions._items) == 1
        assert env.uow.commits == commits

    async def test_the_confirmation_is_compared_exactly(self, env: DealEnv) -> None:
        view = await env.new_deal()
        code = view.item.deal.id.value

        for typed in (f" {code}", f"{code} ", f"{code}X", code[:-1]):
            with pytest.raises(InvalidValueError):
                await env.delete.execute(code, typed, SALES)

        assert len(env.uow.deals._items) == 1


class TestOperationLog:
    async def test_one_info_line_with_code_user_and_time_is_written_after_the_commit(
        self, env: DealEnv, caplog: pytest.LogCaptureFixture
    ) -> None:
        view = await env.new_deal()
        code = view.item.deal.id.value
        env.clock.advance(60)
        caplog.set_level(logging.INFO)

        await env.delete.execute(code, code, SALES)

        lines = [r for r in caplog.records if r.getMessage().startswith("deal deleted")]
        assert len(lines) == 1
        assert lines[0].levelno == logging.INFO
        match = re.fullmatch(
            rf"deal deleted code={code} by={SALES.user_id} at=(?P<at>\S+)", lines[0].getMessage()
        )
        assert match is not None, lines[0].getMessage()
        assert datetime.fromisoformat(match["at"]) == env.clock.now()

    async def test_nothing_is_logged_when_the_deletion_is_refused(
        self, env: DealEnv, caplog: pytest.LogCaptureFixture
    ) -> None:
        view = await env.new_deal()
        caplog.set_level(logging.INFO)

        with pytest.raises(DealCodeMismatchError):
            await env.delete.execute(view.item.deal.id.value, "wrong", SALES)

        assert not [r for r in caplog.records if r.getMessage().startswith("deal deleted")]
