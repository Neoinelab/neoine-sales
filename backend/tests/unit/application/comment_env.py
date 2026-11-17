"""Deal Comment 유스케이스 단위 테스트의 공용 환경: Action 환경 위에 Comment 유스케이스를 얹는다.

이 모듈은 Comment 유스케이스를 모듈 수준에서 가져온다. 그래서 `conftest.py`의 `comment_env`
fixture가 사용 시점에 가져온다(구현이 없어도 다른 테스트의 수집이 막히지 않는다).

요청자·Deal·Action은 `action_env`와 같다: sales KIM·PARK, admin BOSS, user VIEWER. Deal D 하나가
있고 **D의 Owner는 KIM**이다(문서의 공통 Given, CM-R26). KIM의 Action A(Next Action 있음, 수행일 =
시계의 업무 날짜)를 `comment_env.action`으로 쓴다.
"""

from dataclasses import dataclass
from typing import TYPE_CHECKING

from app.application.deal_comment.count_unread_deal_comments import CountUnreadDealComments
from app.application.deal_comment.mark_deal_comments_read import MarkDealCommentsRead

from app.application.deal_comment.delete_deal_comment import DeleteDealComment
from app.application.deal_comment.get_deal_comment import GetDealComment
from app.application.deal_comment.inputs import DealCommentInput
from app.application.deal_comment.list_deal_comments import ListDealComments
from app.application.deal_comment.write_deal_comment import WriteDealComment

if TYPE_CHECKING:
    import builtins
    from datetime import datetime

    from app.application.deal.inputs import Actor
    from app.domain.deal_action.entities import DealAction
    from app.domain.deal_action.value_objects import DealActionId
    from app.domain.deal_comment.entities import DealComment
    from app.domain.deal_comment.values import DealCommentId
    from tests.fakes.unit_of_work import FakeUnitOfWork, FixedClock
    from tests.unit.application.action_env import ActionEnv

NOT_FOUND = "Comment를 찾을 수 없습니다."
DELETE_FORBIDDEN = "본인 Comment 또는 admin만 삭제할 수 있습니다."
BLANK = "Comment를 입력하세요."
NUL = "Comment에는 NUL 문자를 쓸 수 없습니다"
ACTION_NOT_IN_DEAL = "선택한 Action이 이 Deal에 없습니다."
DEAL_NOT_FOUND = "Deal을 찾을 수 없습니다."
DEAL_TARGET = "Comment"
READ_FORBIDDEN = "Deal Owner만 Comment를 읽음 처리할 수 있습니다."


@dataclass
class CommentEnv:
    actions: ActionEnv
    action: DealAction
    write: WriteDealComment
    list: ListDealComments
    get: GetDealComment
    delete: DeleteDealComment
    mark_read: MarkDealCommentsRead
    counts: CountUnreadDealComments

    @property
    def uow(self) -> FakeUnitOfWork:
        return self.actions.env.uow

    @property
    def clock(self) -> FixedClock:
        return self.actions.env.clock

    @property
    def code(self) -> str:
        return self.actions.code

    async def say(
        self,
        actor: Actor,
        body: str,
        *,
        action_id: DealActionId | None = None,
        code: str | None = None,
        advance: int = 60,
    ) -> DealComment:
        """Comment를 쓴다(기본은 시계가 60초 흐른 뒤라 작성 시각이 서로 다르다)."""
        self.clock.advance(advance)
        return await self.write.execute(
            code or self.code, DealCommentInput(body=body, action_id=action_id), actor
        )

    async def stored(self, code: str | None = None) -> builtins.list[DealComment]:
        """저장된 그 Deal 소속 Comment 전부(오래된 순으로 다시 늘어놓는다)."""
        from app.domain.deal.code import DealCode  # noqa: PLC0415

        found = await self.uow.deal_comments.list_for_deal(DealCode(code or self.code))
        return sorted(found, key=lambda c: (c.created_at, c.id))

    async def set_owner(self, actor: Actor, code: str | None = None) -> None:
        """그 Deal의 Owner를 actor로 바꾼다(저장소에 직접, 이력 없음)."""
        from dataclasses import replace  # noqa: PLC0415

        from app.domain.deal.code import DealCode  # noqa: PLC0415

        deal = await self.uow.deals.get(DealCode(code or self.code))
        deal.details = replace(deal.details, owner_user_id=actor.user_id)
        await self.uow.deals.update(deal)

    async def read_at(self, comment_id: DealCommentId) -> datetime | None:
        """저장된 Comment의 read_at."""
        return (await self.uow.deal_comments.get(comment_id)).read_at

    async def rows(self, code: str | None = None) -> builtins.list[tuple[str, str, str, str]]:
        """등록 이력을 뺀 이력을 오래된 순서의 (category, target, before, after)로."""
        return await self.actions.rows(code)

    async def comment_rows(
        self, code: str | None = None
    ) -> builtins.list[tuple[str, str, str, str]]:
        """이력 중 구분이 comment인 것만 오래된 순서로."""
        return [row for row in await self.rows(code) if row[0] == "comment"]

    async def other_deal(self) -> tuple[str, DealAction]:
        """다른 Deal E와 그 Action B를 만든다. (E의 code, B)."""
        from tests.unit.application.action_env import KIM  # noqa: PLC0415

        view = await self.actions.env.new_deal()
        code = view.item.deal.id.value
        return code, await self.actions.act(KIM, code=code)


async def build_comment_env(actions: ActionEnv) -> CommentEnv:
    from tests.unit.application.action_env import KIM  # noqa: PLC0415

    action = await actions.act(KIM)  # Action A: Next Action이 있는 KIM의 Action
    env = actions.env
    built = CommentEnv(
        actions=actions,
        action=action,
        write=WriteDealComment(env.uow_factory, env.clock),
        list=ListDealComments(env.uow_factory),
        get=GetDealComment(env.uow_factory),
        delete=DeleteDealComment(env.uow_factory, env.clock),
        mark_read=MarkDealCommentsRead(env.uow_factory, env.clock),
        counts=CountUnreadDealComments(env.uow_factory),
    )
    await built.set_owner(KIM)  # 공통 Given: D의 Owner는 KIM
    env.uow.commits = 0
    return built
