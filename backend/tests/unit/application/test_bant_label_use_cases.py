"""BANT Label 유스케이스: 조회(AC-10), 생성(AC-11·12), 이름 변경(AC-12). 삭제는 별도 모듈.

쓰기 유스케이스는 같은 구분의 행을 잠그고(`list(category, for_update=True)`) 중복을 판단한다.
Label 사용 수는 P0에 Deal 연결이 없어 Fake deals에 주입한 값으로 검증한다.
"""

from typing import TYPE_CHECKING

import pytest

from app.application.bant.list_labels import ListBantLabels
from app.application.bant.register_label import RegisterBantLabel
from app.application.bant.rename_label import RenameBantLabel
from app.domain.bant.errors import BantLabelNotFoundError, DuplicateLabelNameError
from app.domain.bant.values import BantCategory, BantLabelId
from app.domain.common.errors import InvalidValueError
from tests.factories_auth import make_user
from tests.fakes.catalog_seed import DEFAULT_LABELS
from tests.support.catalog import label_by_name
from tests.support.ids import new_id

if TYPE_CHECKING:
    from app.application.ports.unit_of_work import UnitOfWorkFactory
    from app.domain.user.value_objects import UserId
    from tests.fakes.unit_of_work import FakeUnitOfWork, FixedClock

DEFAULT_ORDER = [(category, name) for category, names in DEFAULT_LABELS.items() for name in names]


async def _creator(uow: FakeUnitOfWork, login_id: str = "kim") -> UserId:
    user = make_user(login_id)
    await uow.users.add(user)
    return user.id


async def _names(uow: FakeUnitOfWork, category: BantCategory) -> list[str]:
    return [label.name for label in await uow.bant_labels.list(category)]


# --- ListBantLabels (AC-10) ---


async def test_list_labels_returns_the_23_defaults_in_seed_order(
    seeded: FakeUnitOfWork, uow_factory: UnitOfWorkFactory
) -> None:
    result = await ListBantLabels(uow_factory).execute()

    assert [(u.label.category.value, u.label.name) for u in result] == DEFAULT_ORDER
    assert len(result) == 23
    assert all(u.label.is_default and u.label.created_by_user_id is None for u in result)


async def test_list_labels_puts_custom_labels_after_defaults_sorted_by_name(
    seeded: FakeUnitOfWork, uow_factory: UnitOfWorkFactory, clock: FixedClock
) -> None:
    creator = await _creator(seeded)
    register = RegisterBantLabel(uow_factory, clock)
    for name in ("나중에", "가장 먼저", "Zeta", "alpha"):
        await register.execute(BantCategory.NEED, name, creator)

    result = await ListBantLabels(uow_factory).execute()

    need = [u.label.name for u in result if u.label.category is BantCategory.NEED]
    assert need == [*DEFAULT_LABELS["need"], "alpha", "Zeta", "가장 먼저", "나중에"]


async def test_list_labels_reports_usage_counts_per_label(
    seeded: FakeUnitOfWork, uow_factory: UnitOfWorkFactory
) -> None:
    used = await label_by_name(seeded, BantCategory.BUDGET, "예산 없음")
    seeded.deals.bant_label_counts = {used.id: 4}

    result = await ListBantLabels(uow_factory).execute()

    assert {u.label.id: u.usage_count for u in result}[used.id] == 4
    assert sum(u.usage_count for u in result) == 4


# --- RegisterBantLabel (AC-11·12) ---


async def test_register_label_records_the_creator_and_is_not_default(
    seeded: FakeUnitOfWork, uow_factory: UnitOfWorkFactory, clock: FixedClock
) -> None:
    creator = await _creator(seeded)

    result = await RegisterBantLabel(uow_factory, clock).execute(
        BantCategory.TIMELINE, "분기 내 구매", creator
    )

    stored = await seeded.bant_labels.get(result.label.id)
    assert (stored.category, stored.name) == (BantCategory.TIMELINE, "분기 내 구매")
    assert stored.is_default is False
    assert stored.default_order is None
    assert stored.created_by_user_id == creator
    assert stored.created_at == clock.now()
    assert result.usage_count == 0


async def test_register_label_trims_the_name(
    seeded: FakeUnitOfWork, uow_factory: UnitOfWorkFactory, clock: FixedClock
) -> None:
    creator = await _creator(seeded)

    result = await RegisterBantLabel(uow_factory, clock).execute(
        BantCategory.NEED, "  규제 대응  ", creator
    )

    assert result.label.name == "규제 대응"


@pytest.mark.parametrize("name", ["ceo 보고 완료", "CEO 보고 완료", " CEO 보고 완료 "])
async def test_register_label_with_a_duplicate_name_in_the_category_conflicts(
    seeded: FakeUnitOfWork, uow_factory: UnitOfWorkFactory, clock: FixedClock, name: str
) -> None:
    creator = await _creator(seeded)
    before = await _names(seeded, BantCategory.AUTHORITY)

    with pytest.raises(DuplicateLabelNameError):
        await RegisterBantLabel(uow_factory, clock).execute(BantCategory.AUTHORITY, name, creator)

    assert await _names(seeded, BantCategory.AUTHORITY) == before


async def test_register_label_allows_the_same_name_in_another_category(
    seeded: FakeUnitOfWork, uow_factory: UnitOfWorkFactory, clock: FixedClock
) -> None:
    creator = await _creator(seeded)

    result = await RegisterBantLabel(uow_factory, clock).execute(
        BantCategory.BUDGET,
        "모름",
        creator,  # authority·need에는 있지만 budget에는 없다
    )

    assert result.label.name == "모름"


@pytest.mark.parametrize("name", ["", "   ", "가" * 51], ids=["empty", "blank", "51-chars"])
async def test_register_label_with_an_invalid_name_stores_nothing(
    seeded: FakeUnitOfWork, uow_factory: UnitOfWorkFactory, clock: FixedClock, name: str
) -> None:
    creator = await _creator(seeded)
    before = len(await seeded.bant_labels.list())

    with pytest.raises(InvalidValueError):
        await RegisterBantLabel(uow_factory, clock).execute(BantCategory.NEED, name, creator)

    assert len(await seeded.bant_labels.list()) == before


async def test_register_label_accepts_a_50_code_point_name(
    seeded: FakeUnitOfWork, uow_factory: UnitOfWorkFactory, clock: FixedClock
) -> None:
    creator = await _creator(seeded)

    result = await RegisterBantLabel(uow_factory, clock).execute(
        BantCategory.NEED, "😀" * 50, creator
    )

    assert result.label.name == "😀" * 50


# --- RenameBantLabel (AC-12) ---


async def test_rename_label_changes_the_name_and_keeps_the_rest(
    seeded: FakeUnitOfWork, uow_factory: UnitOfWorkFactory, clock: FixedClock
) -> None:
    label = await label_by_name(seeded, BantCategory.BUDGET, "예산 없음")
    clock.advance(60)

    result = await RenameBantLabel(uow_factory, clock).execute(label.id, "  예산 미확보  ")

    stored = await seeded.bant_labels.get(label.id)
    assert result.label.name == stored.name == "예산 미확보"
    assert stored.is_default is True
    assert stored.default_order == label.default_order
    assert stored.updated_at == clock.now()


async def test_rename_label_to_the_same_name_in_another_case_is_allowed(
    seeded: FakeUnitOfWork, uow_factory: UnitOfWorkFactory, clock: FixedClock
) -> None:
    label = await label_by_name(seeded, BantCategory.AUTHORITY, "CEO 보고 완료")

    result = await RenameBantLabel(uow_factory, clock).execute(label.id, "ceo 보고 완료")

    assert result.label.name == "ceo 보고 완료"


async def test_rename_label_to_another_labels_name_conflicts_and_keeps_the_name(
    seeded: FakeUnitOfWork, uow_factory: UnitOfWorkFactory, clock: FixedClock
) -> None:
    label = await label_by_name(seeded, BantCategory.AUTHORITY, "CEO 보고 완료")

    with pytest.raises(DuplicateLabelNameError):
        await RenameBantLabel(uow_factory, clock).execute(label.id, "ciso 보고 완료")

    assert (await seeded.bant_labels.get(label.id)).name == "CEO 보고 완료"


async def test_rename_label_to_a_name_that_exists_only_in_another_category_is_allowed(
    seeded: FakeUnitOfWork, uow_factory: UnitOfWorkFactory, clock: FixedClock
) -> None:
    label = await label_by_name(seeded, BantCategory.BUDGET, "미확인")

    result = await RenameBantLabel(uow_factory, clock).execute(label.id, "모름")

    assert result.label.name == "모름"


@pytest.mark.parametrize("name", ["", "   ", "가" * 51], ids=["empty", "blank", "51-chars"])
async def test_rename_label_with_an_invalid_name_keeps_the_name(
    seeded: FakeUnitOfWork, uow_factory: UnitOfWorkFactory, clock: FixedClock, name: str
) -> None:
    label = await label_by_name(seeded, BantCategory.BUDGET, "예산 없음")

    with pytest.raises(InvalidValueError):
        await RenameBantLabel(uow_factory, clock).execute(label.id, name)

    assert (await seeded.bant_labels.get(label.id)).name == "예산 없음"


async def test_rename_missing_label_raises_not_found(
    seeded: FakeUnitOfWork, uow_factory: UnitOfWorkFactory, clock: FixedClock
) -> None:
    with pytest.raises(BantLabelNotFoundError):
        await RenameBantLabel(uow_factory, clock).execute(BantLabelId(new_id()), "아무거나")
