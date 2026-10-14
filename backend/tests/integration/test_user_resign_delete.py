"""DeleteUser의 분기를 실제 PostgreSQL FK로 검증한다(AC3, T12·T13).

users를 가리키는 FK 종류마다 단독 연결만으로 퇴사 처리(행 보존)가 되고, 연결이 없으면 물리 삭제된다.
어느 경우에도 그 사용자의 세션 행은 지워진다.
"""

from typing import TYPE_CHECKING

import pytest

from app.application.auth.tokens import hash_token
from app.application.user.delete_user import DeleteOutcome
from app.domain.auth.principal import Role
from app.domain.user.errors import UserNotFoundError
from app.domain.user.value_objects import UserDeleteReason
from tests.factories import NOW
from tests.fakes.admin_stack import build_admin_stack
from tests.fakes.unit_of_work import FixedClock
from tests.support.auth_seed import seed_user
from tests.support.user_links import LINK_KINDS, link_user

if TYPE_CHECKING:
    from tests.integration.conftest import RealAuth

pytestmark = pytest.mark.integration


@pytest.mark.parametrize("kind", LINK_KINDS)
async def test_each_kind_of_reference_alone_turns_the_deletion_into_a_resignation(
    real_auth: RealAuth, kind: str
) -> None:
    admin = build_admin_stack(real_auth.stack, real_auth.uow_factory, FixedClock(NOW))
    root = await seed_user(real_auth.uow_factory, "root", Role.ADMIN)
    target = await seed_user(real_auth.uow_factory, "kim", Role.SALES)
    await link_user(real_auth.uow_factory, target, kind)
    token = (await real_auth.stack.issue.execute(target.to_principal())).token

    outcome = await admin.delete_user.execute(user_id=target.id, actor=root.to_principal())

    assert outcome is DeleteOutcome.RESIGNED
    async with real_auth.uow_factory() as uow:
        kept = await uow.users.get(target.id)
        assert kept.deleted_at == NOW
        assert kept.delete_reason is UserDeleteReason.RESIGNED
        assert await uow.sessions.get_by_token_hash(hash_token(token)) is None
        assert await uow.users.has_links(target.id)


async def test_a_user_without_any_reference_is_physically_deleted_with_the_sessions(
    real_auth: RealAuth,
) -> None:
    admin = build_admin_stack(real_auth.stack, real_auth.uow_factory, FixedClock(NOW))
    root = await seed_user(real_auth.uow_factory, "root", Role.ADMIN)
    target = await seed_user(real_auth.uow_factory, "kim", Role.SALES)
    token = (await real_auth.stack.issue.execute(target.to_principal())).token

    outcome = await admin.delete_user.execute(user_id=target.id, actor=root.to_principal())

    assert outcome is DeleteOutcome.DELETED
    async with real_auth.uow_factory() as uow:
        with pytest.raises(UserNotFoundError):
            await uow.users.get(target.id)
        assert await uow.sessions.get_by_token_hash(hash_token(token)) is None
