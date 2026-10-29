"""사용자 삭제 때 대체 로그인용 비밀번호 해시도 지운다(AC13).

해시 행은 사용자 물리 삭제를 막는 '연결'이 아니다. 물리 삭제도 퇴사 처리도 해시를 남기지 않는다.
"""

from typing import TYPE_CHECKING

import pytest

from app.application.user.delete_user import DeleteOutcome
from app.domain.auth.principal import Role
from tests.support.auth_seed import seed_password_hash, seed_user
from tests.support.user_links import LINK_KINDS, link_user

if TYPE_CHECKING:
    from app.application.ports.unit_of_work import UnitOfWorkFactory
    from tests.fakes.admin_stack import AdminStack


async def test_a_user_with_only_a_password_hash_is_deleted_physically_and_the_hash_goes(
    admin: AdminStack, uow_factory: UnitOfWorkFactory
) -> None:
    root = await seed_user(uow_factory, "root", Role.ADMIN)
    target = await seed_user(uow_factory, "kim", Role.SALES)
    await seed_password_hash(uow_factory, target, "pw-kim")

    outcome = await admin.delete_user.execute(user_id=target.id, actor=root.to_principal())

    assert outcome is DeleteOutcome.DELETED  # 해시는 연결로 세지 않는다
    async with uow_factory() as uow:
        assert await uow.password_hashes.get(target.id) is None


@pytest.mark.parametrize("kind", LINK_KINDS)
async def test_resigning_a_linked_user_removes_the_password_hash_too(
    admin: AdminStack, uow_factory: UnitOfWorkFactory, kind: str
) -> None:
    root = await seed_user(uow_factory, "root", Role.ADMIN)
    target = await seed_user(uow_factory, "kim", Role.SALES)
    await link_user(uow_factory, target, kind)
    await seed_password_hash(uow_factory, target, "pw-kim")

    outcome = await admin.delete_user.execute(user_id=target.id, actor=root.to_principal())

    assert outcome is DeleteOutcome.RESIGNED
    async with uow_factory() as uow:
        assert (await uow.users.get(target.id)).deleted_at is not None  # 행은 남는다
        assert await uow.password_hashes.get(target.id) is None


async def test_deleting_one_user_keeps_other_users_password_hashes(
    admin: AdminStack, uow_factory: UnitOfWorkFactory
) -> None:
    root = await seed_user(uow_factory, "root", Role.ADMIN)
    target = await seed_user(uow_factory, "kim", Role.SALES)
    lee = await seed_user(uow_factory, "lee", Role.SALES)
    await seed_password_hash(uow_factory, target, "pw-kim")
    await seed_password_hash(uow_factory, lee, "pw-lee")

    await admin.delete_user.execute(user_id=target.id, actor=root.to_principal())

    async with uow_factory() as uow:
        assert await uow.password_hashes.get(lee.id) is not None
