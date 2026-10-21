"""코드 등록·이름 변경 유스케이스 (AC-03·04·05).

쓰기 유스케이스는 같은 종류의 행을 잠그고(`list(for_update=True)`) 중복·key·order를 정한다.
"""

from typing import TYPE_CHECKING

import pytest

from app.application.code.register_code import RegisterCode
from app.application.code.rename_code import RenameCode
from app.domain.code.errors import CodeNotFoundError, DuplicateCodeNameError
from app.domain.code.values import CodeId, CodeKey, CodeKind, ForecastOutcome
from app.domain.common.errors import InvalidValueError
from tests.support.catalog import add_deals_with_status, code_by_key
from tests.support.ids import new_id

if TYPE_CHECKING:
    from app.application.ports.unit_of_work import UnitOfWorkFactory
    from tests.fakes.unit_of_work import FakeUnitOfWork, FixedClock


async def _count(uow: FakeUnitOfWork, kind: CodeKind) -> int:
    return len(await uow.codes.list(kind))


# --- RegisterCode ---


async def test_register_status_code_appends_with_next_order_and_generated_key(
    seeded: FakeUnitOfWork, uow_factory: UnitOfWorkFactory, clock: FixedClock
) -> None:
    result = await RegisterCode(uow_factory, clock).execute(
        kind=CodeKind.STATUS, name="Final Review", probability_hint=None
    )

    assert result.usage_count == 0
    assert result.code.key == CodeKey("final_review")
    assert result.code.order == 8
    assert result.code.outcome is ForecastOutcome.OPEN
    assert result.code.created_at == clock.now()
    stored = await seeded.codes.get(result.code.id)
    assert (stored.name, stored.kind, stored.order) == ("Final Review", CodeKind.STATUS, 8)
    assert (await seeded.codes.list(CodeKind.STATUS))[-1].id == result.code.id


async def test_register_forecast_code_keeps_the_probability_hint(
    seeded: FakeUnitOfWork, uow_factory: UnitOfWorkFactory, clock: FixedClock
) -> None:
    result = await RegisterCode(uow_factory, clock).execute(
        kind=CodeKind.FORECAST, name="Upside", probability_hint="10-20"
    )

    assert result.code.order == 7
    assert result.code.outcome is ForecastOutcome.OPEN
    assert (await seeded.codes.get(result.code.id)).probability_hint == "10-20"


async def test_register_code_trims_the_name(
    seeded: FakeUnitOfWork, uow_factory: UnitOfWorkFactory, clock: FixedClock
) -> None:
    result = await RegisterCode(uow_factory, clock).execute(
        kind=CodeKind.STATUS, name="  Final Review  ", probability_hint=None
    )

    assert result.code.name == "Final Review"


async def test_register_code_uses_max_order_plus_one_even_with_gaps(
    seeded: FakeUnitOfWork, uow_factory: UnitOfWorkFactory, clock: FixedClock
) -> None:
    middle = await code_by_key(seeded, CodeKind.STATUS, "introduction")
    await seeded.codes.delete(middle.id)  # order 2가 비어 있다

    result = await RegisterCode(uow_factory, clock).execute(
        kind=CodeKind.STATUS, name="Final Review", probability_hint=None
    )

    assert result.code.order == 8


async def test_register_code_without_ascii_name_gets_sequential_keys(
    seeded: FakeUnitOfWork, uow_factory: UnitOfWorkFactory, clock: FixedClock
) -> None:
    register = RegisterCode(uow_factory, clock)

    first = await register.execute(kind=CodeKind.STATUS, name="보류", probability_hint=None)
    second = await register.execute(kind=CodeKind.STATUS, name="검토 중", probability_hint=None)

    assert (first.code.key, second.code.key) == (CodeKey("code_1"), CodeKey("code_2"))


async def test_register_code_resolves_key_collision_within_the_kind(
    seeded: FakeUnitOfWork, uow_factory: UnitOfWorkFactory, clock: FixedClock
) -> None:
    result = await RegisterCode(uow_factory, clock).execute(
        kind=CodeKind.FORECAST, name="Best!", probability_hint=None
    )

    assert result.code.key == CodeKey("best_2")


async def test_register_code_key_only_collides_within_the_same_kind(
    seeded: FakeUnitOfWork, uow_factory: UnitOfWorkFactory, clock: FixedClock
) -> None:
    """Forecast에 key `won`이 있어도 Status의 `won`은 따로 센다."""
    result = await RegisterCode(uow_factory, clock).execute(
        kind=CodeKind.STATUS, name="Won", probability_hint=None
    )

    assert result.code.key == CodeKey("won")


async def test_register_code_allows_the_same_name_in_the_other_kind(
    seeded: FakeUnitOfWork, uow_factory: UnitOfWorkFactory, clock: FixedClock
) -> None:
    result = await RegisterCode(uow_factory, clock).execute(
        kind=CodeKind.STATUS, name="Best", probability_hint=None
    )

    assert result.code.name == "Best"


@pytest.mark.parametrize("name", ["best", "BEST", " Best "])
async def test_register_code_with_a_duplicate_name_conflicts_and_stores_nothing(
    seeded: FakeUnitOfWork, uow_factory: UnitOfWorkFactory, clock: FixedClock, name: str
) -> None:
    with pytest.raises(DuplicateCodeNameError):
        await RegisterCode(uow_factory, clock).execute(
            kind=CodeKind.FORECAST, name=name, probability_hint=None
        )

    assert await _count(seeded, CodeKind.FORECAST) == 6


@pytest.mark.parametrize("name", ["", "   ", "가" * 51], ids=["empty", "blank", "51-chars"])
async def test_register_code_with_an_invalid_name_stores_nothing(
    seeded: FakeUnitOfWork, uow_factory: UnitOfWorkFactory, clock: FixedClock, name: str
) -> None:
    with pytest.raises(InvalidValueError):
        await RegisterCode(uow_factory, clock).execute(
            kind=CodeKind.STATUS, name=name, probability_hint=None
        )

    assert await _count(seeded, CodeKind.STATUS) == 7


async def test_register_status_code_with_a_hint_is_rejected_and_stores_nothing(
    seeded: FakeUnitOfWork, uow_factory: UnitOfWorkFactory, clock: FixedClock
) -> None:
    with pytest.raises(InvalidValueError):
        await RegisterCode(uow_factory, clock).execute(
            kind=CodeKind.STATUS, name="Final Review", probability_hint="10-20"
        )

    assert await _count(seeded, CodeKind.STATUS) == 7


# --- RenameCode ---


async def test_rename_code_changes_only_the_name(
    seeded: FakeUnitOfWork, uow_factory: UnitOfWorkFactory, clock: FixedClock
) -> None:
    best = await code_by_key(seeded, CodeKind.FORECAST, "best")
    clock.advance(60)

    result = await RenameCode(uow_factory, clock).execute(best.id, "가능성 높음")

    stored = await seeded.codes.get(best.id)
    assert result.code.name == stored.name == "가능성 높음"
    assert stored.key == CodeKey("best")
    assert stored.order == best.order
    assert stored.updated_at == clock.now()


async def test_rename_locked_code_is_allowed_and_it_stays_locked(
    seeded: FakeUnitOfWork, uow_factory: UnitOfWorkFactory, clock: FixedClock
) -> None:
    done = await code_by_key(seeded, CodeKind.STATUS, "contract_completed")

    result = await RenameCode(uow_factory, clock).execute(done.id, "수주")

    assert result.code.name == "수주"
    assert result.code.key == CodeKey("contract_completed")
    assert result.code.locked


async def test_rename_code_reports_the_usage_count(
    seeded: FakeUnitOfWork, uow_factory: UnitOfWorkFactory, clock: FixedClock
) -> None:
    await add_deals_with_status(seeded, "introduction", 2)
    introduction = await code_by_key(seeded, CodeKind.STATUS, "introduction")

    result = await RenameCode(uow_factory, clock).execute(introduction.id, "소개")

    assert result.usage_count == 2


async def test_rename_code_to_the_same_name_in_another_case_is_allowed(
    seeded: FakeUnitOfWork, uow_factory: UnitOfWorkFactory, clock: FixedClock
) -> None:
    best = await code_by_key(seeded, CodeKind.FORECAST, "best")

    result = await RenameCode(uow_factory, clock).execute(best.id, "BEST")

    assert result.code.name == "BEST"


async def test_rename_code_to_another_codes_name_conflicts_and_keeps_the_name(
    seeded: FakeUnitOfWork, uow_factory: UnitOfWorkFactory, clock: FixedClock
) -> None:
    best = await code_by_key(seeded, CodeKind.FORECAST, "best")

    with pytest.raises(DuplicateCodeNameError):
        await RenameCode(uow_factory, clock).execute(best.id, "commit")

    assert (await seeded.codes.get(best.id)).name == "Best"


@pytest.mark.parametrize("name", ["", "  ", "가" * 51], ids=["empty", "blank", "51-chars"])
async def test_rename_code_with_an_invalid_name_keeps_the_name(
    seeded: FakeUnitOfWork, uow_factory: UnitOfWorkFactory, clock: FixedClock, name: str
) -> None:
    best = await code_by_key(seeded, CodeKind.FORECAST, "best")

    with pytest.raises(InvalidValueError):
        await RenameCode(uow_factory, clock).execute(best.id, name)

    assert (await seeded.codes.get(best.id)).name == "Best"


async def test_rename_missing_code_raises_not_found(
    seeded: FakeUnitOfWork, uow_factory: UnitOfWorkFactory, clock: FixedClock
) -> None:
    with pytest.raises(CodeNotFoundError):
        await RenameCode(uow_factory, clock).execute(CodeId(new_id()), "아무거나")
