"""BANT Label 삭제 유스케이스(AC-14)와 Label 생성자의 퇴사 처리(AC-15).

Label 사용 수는 P0에 Deal 연결이 없어 Fake deals에 주입한 값으로 검증한다.
"""

from typing import TYPE_CHECKING
from uuid import uuid4

import pytest

from app.application.bant.delete_label import DeleteBantLabel
from app.application.user.delete_user import DeleteOutcome
from app.domain.auth.principal import Role
from app.domain.bant.errors import BantLabelNotFoundError, LabelInUseError
from app.domain.bant.values import BantCategory, BantLabelId
from tests.factories_catalog import make_label
from tests.support.auth_seed import seed_user
from tests.support.catalog import label_by_name

if TYPE_CHECKING:
    from app.application.ports.unit_of_work import UnitOfWorkFactory
    from tests.fakes.admin_stack import AdminStack
    from tests.fakes.unit_of_work import FakeUnitOfWork


async def _names(uow: FakeUnitOfWork, category: BantCategory) -> list[str]:
    return [label.name for label in await uow.bant_labels.list(category)]


async def test_delete_label_in_use_raises_with_the_count_and_keeps_the_row(
    seeded: FakeUnitOfWork, uow_factory: UnitOfWorkFactory
) -> None:
    label = await label_by_name(seeded, BantCategory.BUDGET, "예산 없음")
    seeded.deals.bant_label_counts = {label.id: 3}

    with pytest.raises(LabelInUseError) as raised:
        await DeleteBantLabel(uow_factory).execute(label.id)

    assert str(raised.value) == "사용 중인 Label은 삭제할 수 없습니다. (Deal 3건)"
    assert await seeded.bant_labels.get(label.id) == label


async def test_delete_unused_label_removes_only_that_label(
    seeded: FakeUnitOfWork, uow_factory: UnitOfWorkFactory
) -> None:
    label = await label_by_name(seeded, BantCategory.BUDGET, "예산 없음")
    expected = [n for n in await _names(seeded, BantCategory.BUDGET) if n != "예산 없음"]

    await DeleteBantLabel(uow_factory).execute(label.id)

    assert await _names(seeded, BantCategory.BUDGET) == expected
    assert len(await seeded.bant_labels.list()) == 22


async def test_delete_label_ignores_usage_of_other_labels(
    seeded: FakeUnitOfWork, uow_factory: UnitOfWorkFactory
) -> None:
    other = await label_by_name(seeded, BantCategory.BUDGET, "미확인")
    label = await label_by_name(seeded, BantCategory.BUDGET, "예산 없음")
    seeded.deals.bant_label_counts = {other.id: 5}

    await DeleteBantLabel(uow_factory).execute(label.id)

    with pytest.raises(BantLabelNotFoundError):
        await seeded.bant_labels.get(label.id)


async def test_delete_missing_label_raises_not_found(
    seeded: FakeUnitOfWork, uow_factory: UnitOfWorkFactory
) -> None:
    with pytest.raises(BantLabelNotFoundError):
        await DeleteBantLabel(uow_factory).execute(BantLabelId(uuid4()))


async def test_delete_user_who_created_a_label_resigns_instead_of_deleting(
    admin: AdminStack, uow_factory: UnitOfWorkFactory
) -> None:
    """AC-15: Label 생성자는 users를 FK로 참조하므로 '연결 있음'이다."""
    root = await seed_user(uow_factory, "root", Role.ADMIN)
    creator = await seed_user(uow_factory, "kim", Role.SALES)
    async with uow_factory() as uow:
        await uow.bant_labels.add(make_label(BantCategory.NEED, created_by=creator.id))
        await uow.commit()

    outcome = await admin.delete_user.execute(user_id=creator.id, actor=root.to_principal())

    assert outcome is DeleteOutcome.RESIGNED
    async with uow_factory() as uow:
        assert not (await uow.users.get(creator.id)).is_active


async def test_delete_user_without_created_labels_deletes_even_when_default_labels_exist(
    admin: AdminStack, uow_factory: UnitOfWorkFactory, seeded: FakeUnitOfWork
) -> None:
    """기본 Label은 생성자가 없다(null). 만든 Label이 없는 사용자는 그대로 삭제된다."""
    root = await seed_user(uow_factory, "root", Role.ADMIN)
    other = await seed_user(uow_factory, "lee", Role.SALES)

    outcome = await admin.delete_user.execute(user_id=other.id, actor=root.to_principal())

    assert outcome is DeleteOutcome.DELETED
