"""사용자를 FK로 참조하는 행을 하나씩 만드는 도우미(퇴사/물리 삭제 분기와 has_links 검증용).

Fake와 SQL UoW 어느 쪽에나 쓴다. 참조 대상 사용자 외에 필요한 보조 사용자·고객·Deal은 함께 만든다.
LINK_KINDS가 users를 가리키는 FK 종류의 전부여야 한다(스키마 점검 테스트가 FK 집합과 대조한다).
"""

from typing import TYPE_CHECKING, Final
from uuid import uuid4

from app.domain.deal.stage import DealStage, StageChanger
from tests.factories import (
    NOW,
    later,
    make_customer,
    make_deal,
    make_deal_action,
)
from tests.factories_auth import make_directory_settings, make_user

if TYPE_CHECKING:
    from app.application.ports.unit_of_work import UnitOfWork, UnitOfWorkFactory
    from app.domain.deal.entities import Deal
    from app.domain.user.entities import User
    from app.domain.user.value_objects import UserId

LINK_KINDS: Final = (
    "deal_owner",  # deals.owner_user_id
    "deal_registrant",  # deals.registered_by_user_id
    "action_actor",  # deal_actions.actor_user_id
    "stage_changer",  # deal_stage_changes.changed_by_user_id
    "created_user",  # users.created_by_user_id (다른 사용자의 등록자)
    "directory_settings",  # directory_settings.updated_by_user_id
)


# LINK_KINDS 각각이 가리키는 (테이블, 컬럼). 세션 FK는 삭제 때 행을 먼저 지우므로 연결이 아니다.
LINK_COLUMNS: Final = {
    "deal_owner": ("deals", "owner_user_id"),
    "deal_registrant": ("deals", "registered_by_user_id"),
    "action_actor": ("deal_actions", "actor_user_id"),
    "stage_changer": ("deal_stage_changes", "changed_by_user_id"),
    "created_user": ("users", "created_by_user_id"),
    "directory_settings": ("directory_settings", "updated_by_user_id"),
}
SESSION_COLUMN: Final = ("auth_sessions", "user_id")
EXPECTED_USER_FKS: Final = frozenset({*LINK_COLUMNS.values(), SESSION_COLUMN})


async def _helper_user(uow: UnitOfWork) -> User:
    helper = make_user(f"h{uuid4().hex[:12]}", now=NOW)
    await uow.users.add(helper)
    return helper


async def _deal(uow: UnitOfWork, *, owner: UserId, registered_by: UserId | None = None) -> Deal:
    customer = make_customer()
    await uow.customers.add(customer)
    deal = make_deal(
        code=f"LK-{uuid4().hex[:8]}",
        customer_id=customer.id,
        owner_user_id=owner,
        registered_by_user_id=registered_by,
    )
    await uow.deals.add(deal)
    return deal


async def link_user(uow_factory: UnitOfWorkFactory, user: User, kind: str) -> None:
    """user를 `kind` 방식으로 참조하는 행을 하나 만들고 commit한다."""
    async with uow_factory() as uow:
        await _create_link(uow, user, kind)
        await uow.commit()


async def _create_link(uow: UnitOfWork, user: User, kind: str) -> None:
    if kind == "deal_owner":
        await _deal(uow, owner=user.id)
    elif kind == "deal_registrant":
        helper = await _helper_user(uow)
        await _deal(uow, owner=helper.id, registered_by=user.id)
    elif kind == "action_actor":
        helper = await _helper_user(uow)
        deal = await _deal(uow, owner=helper.id)
        await uow.deal_actions.add(make_deal_action(deal_id=deal.id, actor_user_id=user.id))
    elif kind == "stage_changer":
        helper = await _helper_user(uow)
        deal = await _deal(uow, owner=helper.id)
        change = deal.change_stage(
            DealStage.INTRODUCTION,
            reason=None,
            changed_by=StageChanger(user_id=user.id),
            now=later(5),
        )
        await uow.deals.update(deal)
        await uow.deal_stage_changes.add(change)
    elif kind == "created_user":
        await uow.users.add(make_user(f"c{uuid4().hex[:12]}", created_by_user_id=user.id))
    elif kind == "directory_settings":
        # 이미 설정이 있는 환경(e2e admin 앱)에서는 현재 revision으로 갱신한다.
        stored = await uow.directory_settings.get()
        await uow.directory_settings.save(
            make_directory_settings(),
            expected_revision=None if stored is None else stored.revision,
            updated_by=user.id,
            now=NOW,
        )
    else:
        raise AssertionError(kind)
