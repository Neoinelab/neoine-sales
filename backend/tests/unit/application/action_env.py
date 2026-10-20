"""Action 유스케이스 단위 테스트의 공용 환경(P2): Deal 하나와 Action 유스케이스 묶음, 이력 읽기.

이 모듈은 Action 유스케이스를 모듈 수준에서 가져온다. 그래서 `conftest.py`의 `action_env`
fixture가 사용 시점에 가져온다(구현이 없어도 다른 테스트의 수집이 막히지 않는다).

요청자(Actor)는 role이 있는 값이다: 수정·삭제 권한이 담당자 본인(sales)과 admin으로 갈린다(Q8).
"""

from dataclasses import dataclass
from typing import TYPE_CHECKING, Any

from app.application.deal.inputs import Actor
from app.application.deal_action.delete_deal_action import DeleteDealAction
from app.application.deal_action.get_deal_action import GetDealAction
from app.application.deal_action.list_deal_actions import ListDealActions
from app.application.deal_action.register_deal_action import RegisterDealAction
from app.application.deal_action.update_deal_action import UpdateDealAction
from app.domain.auth.principal import Role
from tests.factories import make_deal_action_input, make_register_input
from tests.support.user_ids import uid

if TYPE_CHECKING:
    import builtins
    from datetime import datetime

    from app.application.deal.dto import DealView
    from app.domain.deal.history import DealHistoryEntry
    from app.domain.deal_action.entities import DealAction
    from app.domain.deal_action.value_objects import DealActionId
    from tests.unit.application.deal_env import DealEnv

KIM = Actor(user_id=uid("kim"), role=Role.SALES)
PARK = Actor(user_id=uid("park"), role=Role.SALES)
BOSS = Actor(user_id=uid("boss"), role=Role.ADMIN)
VIEWER = Actor(user_id=uid("viewer"), role=Role.USER)
EDIT_FORBIDDEN = "본인 Action 또는 admin만 수정할 수 있습니다."
DELETE_FORBIDDEN = "본인 Action 또는 admin만 삭제할 수 있습니다."
NOT_FOUND = "Action을 찾을 수 없습니다."
PROGRESS_REQUIRED = "진행사항을 입력하세요."
SUMMARY = "미팅 · 킥오프 미팅 / Next Action: 요구사항 문서 전달 (Due 2026-01-15)"
SUMMARY_WITH_MEMO = f"{SUMMARY} / Memo: 요구사항 정리"


@dataclass
class ActionEnv:
    env: DealEnv
    deal: DealView
    register: RegisterDealAction
    update: UpdateDealAction
    delete: DeleteDealAction
    list: ListDealActions
    get: GetDealAction

    @property
    def code(self) -> str:
        return self.deal.item.deal.id.value

    async def act(
        self,
        actor: Actor = KIM,
        *,
        code: str | None = None,
        status_changes: tuple[Any, ...] = (),
        advance: int = 60,
        **content: Any,  # noqa: ANN401
    ) -> DealAction:
        """Action을 등록한다(기본은 시계가 60초 흐른 뒤라 수행 시각이 서로 다르다)."""
        self.env.clock.advance(advance)
        return await self.register.execute(
            code or self.code, make_register_input(status_changes, **content), actor
        )

    def set_clock(self, moment: datetime) -> None:
        """서버 시계를 주어진 시각으로 맞춘다(앞으로도 뒤로도)."""
        self.env.clock.advance(int((moment - self.env.clock.now()).total_seconds()))

    async def entries(self, code: str | None = None) -> builtins.list[DealHistoryEntry]:
        """Deal 이력을 오래된 순서로."""
        from app.domain.deal.code import DealCode  # noqa: PLC0415

        found = await self.env.uow.deal_history.list(DealCode(code or self.code))
        return list(reversed(found))

    async def rows(self, code: str | None = None) -> builtins.list[tuple[str, str, str, str]]:
        """등록 이력을 뺀 이력을 오래된 순서의 (category, target, before, after)로."""
        entries = await self.entries(code)
        assert str(entries[0].draft.category) == "created"
        return [
            (str(e.draft.category), e.draft.target, e.draft.before, e.draft.after)
            for e in entries[1:]
        ]

    async def action_entries(self) -> builtins.list[DealHistoryEntry]:
        return [e for e in await self.entries() if str(e.draft.category) == "action"]

    async def stored(self, action_id: DealActionId) -> DealAction:
        return await self.env.uow.deal_actions.get(action_id)

    async def update_as(self, action_id: DealActionId, actor: Actor, **content: Any) -> DealAction:  # noqa: ANN401
        self.env.clock.advance(60)
        return await self.update.execute(action_id, make_deal_action_input(**content), actor)


def build_action_env(env: DealEnv, deal: DealView) -> ActionEnv:
    return ActionEnv(
        env=env,
        deal=deal,
        register=RegisterDealAction(env.uow_factory, env.clock),
        update=UpdateDealAction(env.uow_factory, env.clock),
        delete=DeleteDealAction(env.uow_factory, env.clock),
        list=ListDealActions(env.uow_factory),
        get=GetDealAction(env.uow_factory),
    )
