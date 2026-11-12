"""BANT Label 삭제 유스케이스와 Label 생성자의 퇴사 처리.

Label 사용 수는 P0에 Deal 연결이 없어 Fake deals에 주입한 값으로 검증한다.
"""

from typing import TYPE_CHECKING

import pytest

from app.application.bant.delete_label import DeleteBantLabel
from app.application.bant.list_labels import ListBantLabels
from app.application.user.delete_user import DeleteOutcome
from app.domain.auth.principal import Role
from app.domain.bant.errors import BantLabelNotFoundError, LabelInUseError
from app.domain.bant.values import BantCategory, BantLabelId
from tests.factories_catalog import make_label
from tests.factories_deal import SALES
from tests.support.auth_seed import seed_user
from tests.support.catalog import label_by_name
from tests.support.ids import new_id

if TYPE_CHECKING:
    from app.application.ports.unit_of_work import UnitOfWorkFactory
    from tests.fakes.admin_stack import AdminStack
    from tests.fakes.unit_of_work import FakeUnitOfWork
    from tests.unit.application.deal_env import DealEnv


async def _names(uow: FakeUnitOfWork, category: BantCategory) -> list[str]:
    return [label.name for label in await uow.bant_labels.list(category)]


async def test_delete_label_in_use_raises_with_the_count_and_keeps_the_row(
    seeded: FakeUnitOfWork, uow_factory: UnitOfWorkFactory
) -> None:
    """사용 중인 Label을 지우면 실제 Deal 수가 든 오류이고 Label은 남는다.

    테스트 코드: CL-020
    """
    # given: '예산 없음'을 Deal 3건이 선택했다고 집계된다
    label = await label_by_name(seeded, BantCategory.BUDGET, "예산 없음")
    seeded.deals.bant_label_counts = {label.id: 3}

    # when: Label을 삭제한다
    with pytest.raises(LabelInUseError) as raised:
        await DeleteBantLabel(uow_factory).execute(label.id)

    # then: '(Deal 3건)' 문구의 사용 중 오류이고 Label 행은 그대로다
    assert str(raised.value) == "사용 중인 Label은 삭제할 수 없습니다. (Deal 3건)"
    assert await seeded.bant_labels.get(label.id) == label


async def test_delete_unused_label_removes_only_that_label(
    seeded: FakeUnitOfWork, uow_factory: UnitOfWorkFactory
) -> None:
    """쓰이지 않는 Label은 기본 Label이어도 삭제되고 그 Label만 사라진다.

    테스트 코드: CL-019
    """
    # given: 쓰이지 않는 기본 Label '예산 없음'이 있다
    label = await label_by_name(seeded, BantCategory.BUDGET, "예산 없음")
    expected = [n for n in await _names(seeded, BantCategory.BUDGET) if n != "예산 없음"]

    # when: Label을 삭제한다
    await DeleteBantLabel(uow_factory).execute(label.id)

    # then: budget 목록에서 그 Label만 빠지고 전체는 22개다
    assert await _names(seeded, BantCategory.BUDGET) == expected
    assert len(await seeded.bant_labels.list()) == 22


async def test_delete_label_ignores_usage_of_other_labels(
    seeded: FakeUnitOfWork, uow_factory: UnitOfWorkFactory
) -> None:
    """다른 Label의 사용은 삭제 판정에 영향을 주지 않는다.

    테스트 코드: CL-019
    """
    # given: 같은 구분의 다른 Label '미확인'을 Deal 5건이 선택했다고 집계된다
    other = await label_by_name(seeded, BantCategory.BUDGET, "미확인")
    label = await label_by_name(seeded, BantCategory.BUDGET, "예산 없음")
    seeded.deals.bant_label_counts = {other.id: 5}

    # when: 쓰이지 않는 '예산 없음'을 삭제한다
    await DeleteBantLabel(uow_factory).execute(label.id)

    # then: 삭제되어 조회하면 없음 오류다
    with pytest.raises(BantLabelNotFoundError):
        await seeded.bant_labels.get(label.id)


async def test_label_becomes_deletable_after_the_deals_that_chose_it_are_deleted(
    env: DealEnv,
) -> None:
    """Label을 선택한 Deal이 모두 지워지면 Label을 삭제할 수 있다.

    테스트 코드: CL-022
    """
    # given: '풀 예산 확보'를 선택한 Deal이 있었고 그 Deal을 삭제했다
    label = await label_by_name(env.uow, BantCategory.BUDGET, "풀 예산 확보")
    view = await env.new_deal(bant={BantCategory.BUDGET: label.id})
    code = view.item.deal.id.value
    await env.delete.execute(code, code, SALES)

    # when: Label을 삭제한다
    await DeleteBantLabel(env.uow_factory).execute(label.id)

    # then: 목록에서 Label이 사라진다
    names = [u.label.name for u in await ListBantLabels(env.uow_factory).execute()]
    assert "풀 예산 확보" not in names


async def test_delete_missing_label_raises_not_found(
    seeded: FakeUnitOfWork, uow_factory: UnitOfWorkFactory
) -> None:
    """없는 Label을 삭제하면 찾을 수 없음 오류다.

    테스트 코드: CL-023
    """
    # when·then: 없는 id를 삭제한다 → Label을 찾을 수 없음 오류다
    with pytest.raises(BantLabelNotFoundError):
        await DeleteBantLabel(uow_factory).execute(BantLabelId(new_id()))


async def test_delete_user_who_created_a_label_resigns_instead_of_deleting(
    admin: AdminStack, uow_factory: UnitOfWorkFactory
) -> None:
    """Label을 만든 사용자는 삭제하면 물리 삭제 대신 퇴사 처리된다.

    테스트 코드: US-058
    """
    # given: KIM이 만든 need Label이 있다
    root = await seed_user(uow_factory, "root", Role.ADMIN)
    creator = await seed_user(uow_factory, "kim", Role.SALES)
    async with uow_factory() as uow:
        await uow.bant_labels.add(make_label(BantCategory.NEED, created_by=creator.id))
        await uow.commit()

    # when: admin이 KIM을 삭제한다
    outcome = await admin.delete_user.execute(user_id=creator.id, actor=root.to_principal())

    # then: 결과가 퇴사 처리이고 사용자 행이 비활성으로 남는다
    assert outcome is DeleteOutcome.RESIGNED
    async with uow_factory() as uow:
        assert not (await uow.users.get(creator.id)).is_active


async def test_delete_user_without_created_labels_deletes_even_when_default_labels_exist(
    admin: AdminStack, uow_factory: UnitOfWorkFactory, seeded: FakeUnitOfWork
) -> None:
    """기본 Label은 만든 사람이 없으므로 만든 Label이 없는 사용자는 그대로 삭제된다."""
    # given: admin과 Label을 만들지 않은 사용자가 있다
    root = await seed_user(uow_factory, "root", Role.ADMIN)
    other = await seed_user(uow_factory, "lee", Role.SALES)

    # when: admin이 그 사용자를 삭제한다
    outcome = await admin.delete_user.execute(user_id=other.id, actor=root.to_principal())

    # then: 결과가 물리 삭제다
    assert outcome is DeleteOutcome.DELETED
