"""DeleteDeal(Q6): 없음 404 -> 권한 403 -> code 확인 422 순서, CASCADE 삭제, 운영 로그."""

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
from tests.factories_deal import SALES, draft_of, make_draft, make_patch
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
        """Owner 영업이 code를 정확히 입력하면 Deal이 사라진다.

        테스트 코드: DD-050
        """
        # given: Owner가 만든 Deal
        view = await env.new_deal()
        code = view.item.deal.id.value

        # when: Owner가 Deal code로 확인해 삭제한다
        await env.delete.execute(code, code, SALES)

        # then: 상세가 찾을 수 없음이고 저장소에 Deal이 없다
        with raises_with(DealNotFoundError, NOT_FOUND):
            await env.get.execute(code)
        assert env.uow.deals._items == {}

    async def test_an_admin_deletes_a_deal_of_another_owner(self, env: DealEnv) -> None:
        """admin은 다른 Owner의 Deal도 지운다.

        테스트 코드: DD-051
        """
        # given: 다른 Owner의 Deal과 admin
        boss = await seed_user(env.uow_factory, "boss", Role.ADMIN)
        view = await env.new_deal()
        code = view.item.deal.id.value

        # when: admin이 삭제한다
        await env.delete.execute(code, code, Actor(user_id=boss.id, role=Role.ADMIN))

        # then: 저장소에 Deal이 없다
        assert env.uow.deals._items == {}

    async def test_history_actions_and_links_go_with_the_deal_but_contacts_and_users_stay(
        self, env: DealEnv
    ) -> None:
        """삭제하면 이력·Action이 함께 지워지고 연락처·사용자는 남는다.

        테스트 코드: DD-057
        """
        # given: 이력·Action·파트너 링크가 있는 Deal
        view = await _deal_with_dependents(env)
        code = view.item.deal.id.value
        contacts = set(env.uow.contacts._items)
        users = set(env.uow.users._items)

        # when: 삭제한다
        await env.delete.execute(code, code, SALES)

        # then: 이력·Action이 없고 고객·파트너 연락처와 사용자는 그대로다
        assert env.uow.deal_history._items == {}
        assert env.uow.deal_actions._items == {}
        assert set(env.uow.contacts._items) == contacts
        assert {c.kind for c in env.uow.contacts._items.values()} == {
            ContactKind.CUSTOMER,
            ContactKind.PARTNER,
        }
        assert set(env.uow.users._items) == users

    async def test_other_deals_are_untouched(self, env: DealEnv) -> None:
        """삭제해도 다른 Deal과 그 이력은 그대로다.

        테스트 코드: DD-058
        """
        # given: Deal 두 건
        first = await env.new_deal()
        second = await env.new_deal()

        # when: 첫 Deal을 삭제한다
        await env.delete.execute(first.item.deal.id.value, first.item.deal.id.value, SALES)

        # then: 둘째 Deal만 남고 그 등록 이력도 남는다
        assert list(env.uow.deals._items) == [second.item.deal.id]
        assert len(env.uow.deal_history._items) == 1  # 남은 Deal의 등록 이력

    async def test_deleting_a_deal_keeps_partner_meetings(self, env: DealEnv) -> None:
        """Deal을 삭제해도 파트너 미팅 기록은 남는다.

        테스트 코드: DD-057
        """
        # given: Deal 두 건과 파트너 미팅 기록 두 건
        from tests.factories_partner_meeting import make_meeting  # noqa: PLC0415
        from tests.support.user_ids import ACTOR_ID  # noqa: PLC0415

        doomed = await env.new_deal()
        await env.new_deal()
        async with env.uow_factory() as uow:
            first = make_meeting(author=ACTOR_ID)
            second = make_meeting(author=ACTOR_ID, content="두 번째")
            await uow.partner_meetings.add(first)
            await uow.partner_meetings.add(second)
            await uow.commit()

        # when: Deal 하나를 삭제한다
        await env.delete.execute(doomed.item.deal.id.value, doomed.item.deal.id.value, SALES)

        # then: 미팅 기록 두 건이 그대로 읽힌다
        async with env.uow_factory() as uow:
            assert (await uow.partner_meetings.get(first.id)).id == first.id
            assert (await uow.partner_meetings.get(second.id)).id == second.id

    async def test_the_deletion_is_committed(self, env: DealEnv) -> None:
        """삭제는 한 번 커밋된다.

        테스트 코드: DD-050
        """
        # given: Deal 하나
        view = await env.new_deal()
        commits = env.uow.commits

        # when: 삭제한다
        await env.delete.execute(view.item.deal.id.value, view.item.deal.id.value, SALES)

        # then: 커밋 횟수가 1 늘었다
        assert env.uow.commits == commits + 1

    async def test_the_remaining_contacts_can_be_used_to_register_the_deal_again(
        self, env: DealEnv
    ) -> None:
        """삭제해도 남은 고객·파트너 연락처를 골라 같은 값으로 Deal을 다시 등록할 수 있다.

        테스트 코드: DD-057
        """
        # given: 고객·파트너 연락처가 연결된 Deal
        view = await env.new_deal(partner=make_draft(company="코어테크", name="민지훈"))
        code = view.item.deal.id.value
        customer = env.uow.contacts._items[view.item.deal.customer_id]
        partner_id = view.item.deal.active_partner_id()
        assert partner_id is not None
        partner = env.uow.contacts._items[partner_id]
        await env.delete.execute(code, code, SALES)

        # when: 남은 연락처를 그대로 골라 Deal을 다시 등록한다
        again = await env.new_deal(customer=draft_of(customer), partner=draft_of(partner))

        # then: 같은 연락처를 쓰는 새 Deal이 등록된다
        assert again.item.deal.customer_id == customer.id
        assert again.item.deal.active_partner_id() == partner.id


class TestOrderOfChecks:
    async def test_an_unknown_deal_is_not_found_before_anything_else(self, env: DealEnv) -> None:
        """없는 Deal은 권한·확인 code보다 먼저 찾을 수 없음 오류다.

        테스트 코드: DD-056
        """
        # given: 읽기 전용 요청자
        viewer = Actor(user_id=SALES.user_id, role=Role.USER)

        # when·then: 없는 Deal을 틀린 확인 code로 삭제한다 → Deal을 찾을 수 없음 오류다
        with raises_with(DealNotFoundError, NOT_FOUND):
            await env.delete.execute("20261016-ZZZZ", "wrong", viewer)

    async def test_a_malformed_code_is_not_found(self, env: DealEnv) -> None:
        """형식이 틀린 code는 찾을 수 없음 오류다.

        테스트 코드: DD-056
        """
        # when·then: 형식이 틀린 code로 삭제한다 → Deal을 찾을 수 없음 오류다
        with raises_with(DealNotFoundError, NOT_FOUND):
            await env.delete.execute("bad", "bad", SALES)

    async def test_another_sales_user_is_forbidden_even_with_a_wrong_confirmation(
        self, env: DealEnv
    ) -> None:
        """다른 영업은 확인 code가 틀려도 삭제 권한 오류가 먼저이고 Deal은 남는다.

        테스트 코드: DD-052
        """
        # given: 다른 Owner의 Deal과 다른 영업
        view = await env.new_deal()
        park = await seed_user(env.uow_factory, "park", Role.SALES)

        # when: 틀린 확인 code로 삭제한다
        with raises_with(DealDeleteForbiddenError, FORBIDDEN):
            await env.delete.execute(
                view.item.deal.id.value, "wrong", Actor(user_id=park.id, role=Role.SALES)
            )

        # then: '본인 Deal 또는 admin만' 오류이고 Deal은 남는다
        assert len(env.uow.deals._items) == 1

    async def test_a_read_only_user_is_forbidden(self, env: DealEnv) -> None:
        """읽기 전용 user는 Owner 아이디가 같아도 삭제할 수 없다.

        테스트 코드: DD-053
        """
        # given: user 역할 요청자
        view = await env.new_deal()
        viewer = await seed_user(env.uow_factory, "viewer", Role.USER)
        code = view.item.deal.id.value

        # when·then: 정확한 확인 code로 삭제한다 → 삭제 권한 오류다
        with raises_with(DealDeleteForbiddenError, FORBIDDEN):
            await env.delete.execute(code, code, Actor(user_id=viewer.id, role=Role.USER))

    @pytest.mark.parametrize("typed", ["", "wrong", "20260101-9999"])
    async def test_a_wrong_confirmation_is_rejected_and_nothing_is_deleted(
        self, env: DealEnv, typed: str
    ) -> None:
        """확인 code가 다르면 거절되고 Deal·이력·Action이 남으며 커밋하지 않는다.

        테스트 코드: DD-054
        """
        # given: 이력·Action이 있는 Deal
        view = await _deal_with_dependents(env)
        commits = env.uow.commits

        # when: 틀린 확인 code로 삭제한다
        with raises_with(DealCodeMismatchError, MISMATCH):
            await env.delete.execute(view.item.deal.id.value, typed, SALES)

        # then: 'Deal code가 일치하지 않습니다.' 오류이고 Deal·이력·Action이 남고 커밋 없음
        assert len(env.uow.deals._items) == 1
        assert len(env.uow.deal_history._items) == 2
        assert len(env.uow.deal_actions._items) == 1
        assert env.uow.commits == commits

    async def test_the_confirmation_is_compared_exactly(self, env: DealEnv) -> None:
        """확인 code는 앞뒤 공백·글자 차이까지 정확히 비교한다.

        테스트 코드: DD-054
        """
        # given: Deal 하나
        view = await env.new_deal()
        code = view.item.deal.id.value

        for typed in (f" {code}", f"{code} ", f"{code}X", code[:-1]):
            with pytest.raises(InvalidValueError):
                # when: 앞뒤 공백, 글자 추가·누락 code로 삭제한다
                await env.delete.execute(code, typed, SALES)

        # then: 모두 값 오류이고 Deal은 남는다
        assert len(env.uow.deals._items) == 1


class TestOperationLog:
    async def test_one_info_line_with_code_user_and_time_is_written_after_the_commit(
        self, env: DealEnv, caplog: pytest.LogCaptureFixture
    ) -> None:
        """삭제하면 커밋 뒤 code·사용자·시각이 든 INFO 로그 한 줄이 남는다.

        테스트 코드: DD-059
        """
        # given: Deal 하나이고 시간이 60초 지났다
        view = await env.new_deal()
        code = view.item.deal.id.value
        env.clock.advance(60)
        caplog.set_level(logging.INFO)

        # when: 삭제한다
        await env.delete.execute(code, code, SALES)

        # then: 'deal deleted code=… by=… at=…' INFO 한 줄이고 시각이 서버 시각이다
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
        """거절된 삭제는 운영 로그를 남기지 않는다.

        테스트 코드: DD-059
        """
        # given: Deal 하나
        view = await env.new_deal()
        caplog.set_level(logging.INFO)

        # when: 틀린 확인 code로 삭제한다
        with pytest.raises(DealCodeMismatchError):
            await env.delete.execute(view.item.deal.id.value, "wrong", SALES)

        # then: 'deal deleted' 로그가 없다
        assert not [r for r in caplog.records if r.getMessage().startswith("deal deleted")]


async def test_deleting_a_deal_removes_all_of_its_comments_but_not_other_deals(
    env: DealEnv,
) -> None:
    """Deal을 지우면 그 Deal 소속 Comment(Deal Comment·Action Comment)가 모두 지워지고 다른 Deal의
    Comment는 그대로다.

    테스트 코드: CM-039
    """
    # given: Deal D(Deal Comment 1건·Action Comment 2건)와 Comment 1건이 있는 다른 Deal E
    from tests.factories_comment import make_comment  # noqa: PLC0415
    from tests.support.user_ids import ACTOR_ID  # noqa: PLC0415

    deal = await env.new_deal()
    other = await env.new_deal()
    code = deal.item.deal.id
    action = make_deal_action(deal_code=code)
    await env.uow.deal_actions.add(action)
    for linked in (None, action.id, action.id):
        await env.uow.deal_comments.add(
            make_comment(deal_code=code, action_id=linked, author=ACTOR_ID)
        )
    kept = make_comment(deal_code=other.item.deal.id, author=ACTOR_ID)
    await env.uow.deal_comments.add(kept)

    # when: Owner가 D를 지운다
    await env.delete.execute(code.value, code.value, SALES)

    # then: D의 Comment 3건은 없어지고 E의 Comment만 남는다
    assert [c.id for c in env.uow.deal_comments._items.values()] == [kept.id]
