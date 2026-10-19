"""CodeRepository 계약(AC-01·03·04·06): Fake와 SQL 구현(실제 PostgreSQL)에 같은 테스트를 적용한다.

SQL 쪽에는 마이그레이션 시드(기본 코드 13개)가 있을 수 있어 비어 있는 저장소를 가정하지 않는다.
이름·key는 시드와 겹치지 않는 값을 쓰고, 목록은 `mine_codes`로 자기가 만든 행만 비교한다.
"""

from typing import TYPE_CHECKING
from uuid import uuid4

import pytest

from app.domain.code.errors import CodeNotFoundError, DuplicateCodeNameError
from app.domain.code.values import CodeId, CodeKey, CodeKind, ForecastOutcome
from app.domain.common.errors import AlreadyExistsError
from tests.factories import NOW, later
from tests.factories_catalog import make_code

if TYPE_CHECKING:
    from tests.unit.repositories.catalog_case import CatalogCase


async def test_add_then_get_round_trips_every_field(catalog: CatalogCase) -> None:
    code = make_code(
        CodeKind.FORECAST,
        key="zz_upside",
        name="ZZ Upside",
        order=77,
        outcome=ForecastOutcome.OPEN,
        probability_hint="10-20",
        now=NOW,
    )
    await catalog.codes.add(code)

    stored = await catalog.codes.get(code.id)

    assert stored == code
    assert (stored.kind, stored.key, stored.name, stored.order) == (
        CodeKind.FORECAST,
        CodeKey("zz_upside"),
        "ZZ Upside",
        77,
    )
    assert (stored.outcome, stored.probability_hint) == (ForecastOutcome.OPEN, "10-20")
    assert (stored.created_at, stored.updated_at) == (NOW, NOW)


@pytest.mark.parametrize("outcome", [ForecastOutcome.WON, ForecastOutcome.LOST])
async def test_forecast_outcome_round_trips(catalog: CatalogCase, outcome: ForecastOutcome) -> None:
    code = make_code(
        CodeKind.FORECAST, key=f"zz_{outcome.value}", name=f"ZZ {outcome}", outcome=outcome
    )
    await catalog.codes.add(code)

    assert (await catalog.codes.get(code.id)).outcome is outcome


async def test_status_code_without_hint_round_trips(catalog: CatalogCase) -> None:
    code = make_code(CodeKind.STATUS, key="zz_status", name="ZZ 상태")
    await catalog.codes.add(code)

    stored = await catalog.codes.get(code.id)

    assert (stored.probability_hint, stored.outcome) == (None, ForecastOutcome.OPEN)


async def test_get_missing_code_raises_not_found(catalog: CatalogCase) -> None:
    with pytest.raises(CodeNotFoundError):
        await catalog.codes.get(CodeId(uuid4()))


async def test_list_orders_a_kind_by_order(catalog: CatalogCase) -> None:
    third = make_code(CodeKind.STATUS, key="zz_c", name="ZZ C", order=300)
    first = make_code(CodeKind.STATUS, key="zz_a", name="ZZ A", order=100)
    second = make_code(CodeKind.STATUS, key="zz_b", name="ZZ B", order=200)
    for code in (third, second, first):
        await catalog.codes.add(code)

    listed = await catalog.mine_codes(CodeKind.STATUS, {first.id, second.id, third.id})

    assert [c.id for c in listed] == [first.id, second.id, third.id]


async def test_list_breaks_order_ties_by_id(catalog: CatalogCase) -> None:
    twins = [
        make_code(CodeKind.STATUS, key=f"zz_t{n}", name=f"ZZ T{n}", order=500) for n in range(3)
    ]
    for code in twins:
        await catalog.codes.add(code)

    listed = await catalog.mine_codes(CodeKind.STATUS, {c.id for c in twins})

    assert [str(c.id) for c in listed] == sorted(str(c.id) for c in twins)


async def test_list_with_kind_returns_only_that_kind(catalog: CatalogCase) -> None:
    status = make_code(CodeKind.STATUS, key="zz_s", name="ZZ S")
    forecast = make_code(CodeKind.FORECAST, key="zz_f", name="ZZ F")
    await catalog.codes.add(status)
    await catalog.codes.add(forecast)

    listed = await catalog.codes.list(CodeKind.FORECAST)

    assert forecast.id in {c.id for c in listed}
    assert status.id not in {c.id for c in listed}
    assert {c.kind for c in listed} == {CodeKind.FORECAST}


async def test_list_for_update_returns_the_same_rows(catalog: CatalogCase) -> None:
    code = make_code(CodeKind.STATUS, key="zz_s", name="ZZ S")
    await catalog.codes.add(code)

    plain = await catalog.codes.list(CodeKind.STATUS)
    locked = await catalog.codes.list(CodeKind.STATUS, for_update=True)

    assert [c.id for c in locked] == [c.id for c in plain]


@pytest.mark.parametrize("duplicate", ["zz name", "ZZ NAME", "Zz Name"])
async def test_add_with_same_name_in_the_kind_ignoring_case_conflicts(
    catalog: CatalogCase, duplicate: str
) -> None:
    await catalog.codes.add(make_code(CodeKind.STATUS, key="zz_one", name="ZZ Name"))

    with pytest.raises(DuplicateCodeNameError):
        await catalog.codes.add(make_code(CodeKind.STATUS, key="zz_two", name=duplicate))


async def test_add_with_same_name_in_the_other_kind_is_allowed(catalog: CatalogCase) -> None:
    await catalog.codes.add(make_code(CodeKind.STATUS, key="zz_one", name="ZZ Name"))
    other = make_code(CodeKind.FORECAST, key="zz_two", name="ZZ Name")

    await catalog.codes.add(other)

    assert (await catalog.codes.get(other.id)).name == "ZZ Name"


async def test_add_with_same_key_in_the_kind_conflicts_as_already_exists(
    catalog: CatalogCase,
) -> None:
    await catalog.codes.add(make_code(CodeKind.STATUS, key="zz_same", name="ZZ One"))

    with pytest.raises(AlreadyExistsError) as raised:
        await catalog.codes.add(make_code(CodeKind.STATUS, key="zz_same", name="ZZ Two"))

    assert not isinstance(raised.value, DuplicateCodeNameError)


async def test_add_with_same_key_in_the_other_kind_is_allowed(catalog: CatalogCase) -> None:
    await catalog.codes.add(make_code(CodeKind.STATUS, key="zz_same", name="ZZ One"))
    other = make_code(CodeKind.FORECAST, key="zz_same", name="ZZ Two")

    await catalog.codes.add(other)

    assert (await catalog.codes.get(other.id)).key == CodeKey("zz_same")


async def test_repository_stays_usable_after_a_conflict(catalog: CatalogCase) -> None:
    await catalog.codes.add(make_code(CodeKind.STATUS, key="zz_one", name="ZZ One"))
    with pytest.raises(DuplicateCodeNameError):
        await catalog.codes.add(make_code(CodeKind.STATUS, key="zz_two", name="zz one"))
    after = make_code(CodeKind.STATUS, key="zz_three", name="ZZ Three")

    await catalog.codes.add(after)

    assert (await catalog.codes.get(after.id)).name == "ZZ Three"


async def test_update_persists_name_and_order(catalog: CatalogCase) -> None:
    code = make_code(CodeKind.STATUS, key="zz_s", name="ZZ S", order=10)
    await catalog.codes.add(code)
    code.rename("ZZ 새 이름", later(60))
    code.place(11, later(60))

    await catalog.codes.update(code)

    stored = await catalog.codes.get(code.id)
    assert (stored.name, stored.order, stored.updated_at) == ("ZZ 새 이름", 11, later(60))
    assert (stored.key, stored.created_at) == (CodeKey("zz_s"), NOW)


async def test_update_missing_code_raises_not_found(catalog: CatalogCase) -> None:
    with pytest.raises(CodeNotFoundError):
        await catalog.codes.update(make_code(CodeKind.STATUS, key="zz_s", name="ZZ S"))


async def test_update_to_another_codes_name_ignoring_case_conflicts(catalog: CatalogCase) -> None:
    await catalog.codes.add(make_code(CodeKind.STATUS, key="zz_one", name="ZZ One"))
    other = make_code(CodeKind.STATUS, key="zz_two", name="ZZ Two")
    await catalog.codes.add(other)
    other.rename("zz one", later(60))

    with pytest.raises(DuplicateCodeNameError):
        await catalog.codes.update(other)


async def test_update_to_own_name_in_another_case_is_allowed(catalog: CatalogCase) -> None:
    code = make_code(CodeKind.STATUS, key="zz_s", name="ZZ Name")
    await catalog.codes.add(code)
    code.rename("zz name", later(60))

    await catalog.codes.update(code)

    assert (await catalog.codes.get(code.id)).name == "zz name"


async def test_delete_removes_only_that_code(catalog: CatalogCase) -> None:
    gone = make_code(CodeKind.STATUS, key="zz_gone", name="ZZ Gone")
    kept = make_code(CodeKind.STATUS, key="zz_kept", name="ZZ Kept")
    await catalog.codes.add(gone)
    await catalog.codes.add(kept)

    await catalog.codes.delete(gone.id)

    assert [c.id for c in await catalog.mine_codes(CodeKind.STATUS, {gone.id, kept.id})] == [
        kept.id
    ]
    with pytest.raises(CodeNotFoundError):
        await catalog.codes.get(gone.id)


async def test_deleted_name_and_key_can_be_added_again(catalog: CatalogCase) -> None:
    first = make_code(CodeKind.STATUS, key="zz_again", name="ZZ Again")
    await catalog.codes.add(first)
    await catalog.codes.delete(first.id)
    again = make_code(CodeKind.STATUS, key="zz_again", name="ZZ Again")

    await catalog.codes.add(again)

    assert (await catalog.codes.get(again.id)).id == again.id


async def test_delete_missing_code_raises_not_found(catalog: CatalogCase) -> None:
    with pytest.raises(CodeNotFoundError):
        await catalog.codes.delete(CodeId(uuid4()))
