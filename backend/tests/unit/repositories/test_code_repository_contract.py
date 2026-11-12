"""CodeRepository 계약: Fake와 SQL 구현(실제 PostgreSQL)에 같은 테스트를 적용한다.

SQL 쪽에는 마이그레이션 시드(기본 코드 13개)가 있을 수 있어 비어 있는 저장소를 가정하지 않는다.
이름·key는 시드와 겹치지 않는 값을 쓰고, 목록은 `mine_codes`로 자기가 만든 행만 비교한다.
"""

from typing import TYPE_CHECKING

import pytest

from app.domain.code.errors import CodeNotFoundError, DuplicateCodeNameError
from app.domain.code.values import CodeId, CodeKey, CodeKind, ForecastOutcome
from app.domain.common.errors import AlreadyExistsError
from tests.factories import NOW, later
from tests.factories_catalog import make_code
from tests.support.ids import new_id

if TYPE_CHECKING:
    from tests.unit.repositories.catalog_case import CatalogCase


async def test_add_then_get_round_trips_every_field(catalog: CatalogCase) -> None:
    """코드를 저장한 뒤 읽으면 모든 필드가 그대로 돌아오는지 확인한다."""
    # given: 모든 필드를 채운 Forecast 코드가 있다
    code = make_code(
        CodeKind.FORECAST,
        key="zz_upside",
        name="ZZ Upside",
        order=77,
        outcome=ForecastOutcome.OPEN,
        probability_hint="10-20",
        now=NOW,
    )
    # when: 코드를 저장하고 다시 읽는다
    await catalog.codes.add(code)

    stored = await catalog.codes.get(code.id)

    # then: 읽은 코드가 저장한 것과 같고 각 필드가 보존된다
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
    """Forecast 결과 구분(WON·LOST)이 저장 뒤에도 유지되는지 확인한다."""
    # given: 결과 구분이 지정된 Forecast 코드가 있다
    code = make_code(
        CodeKind.FORECAST, key=f"zz_{outcome.value}", name=f"ZZ {outcome}", outcome=outcome
    )
    # when: 코드를 저장하고 다시 읽는다
    await catalog.codes.add(code)
    stored = await catalog.codes.get(code.id)

    # then: 읽은 코드의 결과 구분이 저장한 값이다
    assert stored.outcome is outcome


async def test_status_code_without_hint_round_trips(catalog: CatalogCase) -> None:
    """힌트 없는 Status 코드가 저장 뒤에도 힌트 없이 OPEN인지 확인한다."""
    # given: 힌트 없는 Status 코드가 있다
    code = make_code(CodeKind.STATUS, key="zz_status", name="ZZ 상태")
    # when: 코드를 저장하고 다시 읽는다
    await catalog.codes.add(code)

    stored = await catalog.codes.get(code.id)

    # then: 힌트는 None이고 결과 구분은 OPEN이다
    assert (stored.probability_hint, stored.outcome) == (None, ForecastOutcome.OPEN)


async def test_get_missing_code_raises_not_found(catalog: CatalogCase) -> None:
    """없는 코드를 읽으면 CodeNotFoundError인지 확인한다."""
    # when·then: 없는 id로 읽으면 CodeNotFoundError가 난다
    with pytest.raises(CodeNotFoundError):
        await catalog.codes.get(CodeId(new_id()))


async def test_list_orders_a_kind_by_order(catalog: CatalogCase) -> None:
    """같은 종류 목록이 order 순으로 정렬되는지 확인한다."""
    # given: order가 300·100·200인 Status 코드를 순서 없이 저장한다
    third = make_code(CodeKind.STATUS, key="zz_c", name="ZZ C", order=300)
    first = make_code(CodeKind.STATUS, key="zz_a", name="ZZ A", order=100)
    second = make_code(CodeKind.STATUS, key="zz_b", name="ZZ B", order=200)
    for code in (third, second, first):
        await catalog.codes.add(code)

    # when: 자기가 만든 코드만 목록으로 조회한다
    listed = await catalog.mine_codes(CodeKind.STATUS, {first.id, second.id, third.id})

    # then: order 오름차순이다
    assert [c.id for c in listed] == [first.id, second.id, third.id]


async def test_list_breaks_order_ties_by_id(catalog: CatalogCase) -> None:
    """order가 같으면 id 순으로 정렬되는지 확인한다."""
    # given: order가 같은 코드 세 개를 저장한다
    twins = [
        make_code(CodeKind.STATUS, key=f"zz_t{n}", name=f"ZZ T{n}", order=500) for n in range(3)
    ]
    for code in twins:
        await catalog.codes.add(code)

    # when: 자기가 만든 코드만 목록으로 조회한다
    listed = await catalog.mine_codes(CodeKind.STATUS, {c.id for c in twins})

    # then: id 오름차순이다
    assert [c.id for c in listed] == sorted(c.id for c in twins)


async def test_list_with_kind_returns_only_that_kind(catalog: CatalogCase) -> None:
    """종류를 주면 그 종류의 코드만 목록에 나오는지 확인한다."""
    # given: Status 코드와 Forecast 코드를 저장한다
    status = make_code(CodeKind.STATUS, key="zz_s", name="ZZ S")
    forecast = make_code(CodeKind.FORECAST, key="zz_f", name="ZZ F")
    await catalog.codes.add(status)
    await catalog.codes.add(forecast)

    # when: Forecast 종류로 목록을 조회한다
    listed = await catalog.codes.list(CodeKind.FORECAST)

    # then: Forecast만 나오고 Status는 없다
    assert forecast.id in {c.id for c in listed}
    assert status.id not in {c.id for c in listed}
    assert {c.kind for c in listed} == {CodeKind.FORECAST}


async def test_list_for_update_returns_the_same_rows(catalog: CatalogCase) -> None:
    """for_update 목록이 일반 목록과 같은 행을 돌려주는지 확인한다."""
    # given: Status 코드를 저장한다
    code = make_code(CodeKind.STATUS, key="zz_s", name="ZZ S")
    await catalog.codes.add(code)

    # when: 일반 조회와 for_update 조회를 한다
    plain = await catalog.codes.list(CodeKind.STATUS)
    locked = await catalog.codes.list(CodeKind.STATUS, for_update=True)

    # then: 두 목록의 id가 같다
    assert [c.id for c in locked] == [c.id for c in plain]


@pytest.mark.parametrize("duplicate", ["zz name", "ZZ NAME", "Zz Name"])
async def test_add_with_same_name_in_the_kind_ignoring_case_conflicts(
    catalog: CatalogCase, duplicate: str
) -> None:
    """같은 종류 안에서 대소문자만 다른 이름은 충돌하는지 확인한다."""
    # given: 이름이 있는 Status 코드를 저장한다
    await catalog.codes.add(make_code(CodeKind.STATUS, key="zz_one", name="ZZ Name"))

    # when·then: 대소문자만 다른 이름으로 저장하면 DuplicateCodeNameError가 난다
    with pytest.raises(DuplicateCodeNameError):
        await catalog.codes.add(make_code(CodeKind.STATUS, key="zz_two", name=duplicate))


async def test_add_with_same_name_in_the_other_kind_is_allowed(catalog: CatalogCase) -> None:
    """다른 종류에는 같은 이름을 저장할 수 있는지 확인한다."""
    # given: Status 코드를 저장한다
    await catalog.codes.add(make_code(CodeKind.STATUS, key="zz_one", name="ZZ Name"))
    other = make_code(CodeKind.FORECAST, key="zz_two", name="ZZ Name")

    # when: 같은 이름의 Forecast 코드를 저장한다
    await catalog.codes.add(other)

    # then: 저장되어 이름이 그대로 읽힌다
    assert (await catalog.codes.get(other.id)).name == "ZZ Name"


async def test_add_with_same_key_in_the_kind_conflicts_as_already_exists(
    catalog: CatalogCase,
) -> None:
    """같은 종류 안에서 같은 key는 AlreadyExistsError인지 확인한다."""
    # given: key가 있는 Status 코드를 저장한다
    await catalog.codes.add(make_code(CodeKind.STATUS, key="zz_same", name="ZZ One"))

    # when: 같은 key로 이름만 다른 코드를 저장한다
    with pytest.raises(AlreadyExistsError) as raised:
        await catalog.codes.add(make_code(CodeKind.STATUS, key="zz_same", name="ZZ Two"))

    # then: AlreadyExistsError이되 이름 중복 오류는 아니다
    assert not isinstance(raised.value, DuplicateCodeNameError)


async def test_add_with_same_key_in_the_other_kind_is_allowed(catalog: CatalogCase) -> None:
    """다른 종류에는 같은 key를 저장할 수 있는지 확인한다."""
    # given: Status 코드를 저장한다
    await catalog.codes.add(make_code(CodeKind.STATUS, key="zz_same", name="ZZ One"))
    other = make_code(CodeKind.FORECAST, key="zz_same", name="ZZ Two")

    # when: 같은 key의 Forecast 코드를 저장한다
    await catalog.codes.add(other)

    # then: 저장되어 key가 그대로 읽힌다
    assert (await catalog.codes.get(other.id)).key == CodeKey("zz_same")


async def test_repository_stays_usable_after_a_conflict(catalog: CatalogCase) -> None:
    """충돌 오류 뒤에도 저장소를 계속 쓸 수 있는지 확인한다."""
    # given: 코드를 저장하고 이름 충돌을 한 번 일으킨다
    await catalog.codes.add(make_code(CodeKind.STATUS, key="zz_one", name="ZZ One"))
    with pytest.raises(DuplicateCodeNameError):
        await catalog.codes.add(make_code(CodeKind.STATUS, key="zz_two", name="zz one"))
    after = make_code(CodeKind.STATUS, key="zz_three", name="ZZ Three")

    # when: 충돌 뒤 새 코드를 저장한다
    await catalog.codes.add(after)

    # then: 새 코드가 읽힌다
    assert (await catalog.codes.get(after.id)).name == "ZZ Three"


async def test_update_persists_name_and_order(catalog: CatalogCase) -> None:
    """수정한 이름과 order가 저장되는지 확인한다."""
    # given: 저장된 코드의 이름과 order를 바꿔 둔다
    code = make_code(CodeKind.STATUS, key="zz_s", name="ZZ S", order=10)
    await catalog.codes.add(code)
    code.rename("ZZ 새 이름", later(60))
    code.place(11, later(60))

    # when: 코드를 수정 저장한다
    await catalog.codes.update(code)

    # then: 이름·order·수정 시각이 바뀌고 key·생성 시각은 그대로다
    stored = await catalog.codes.get(code.id)
    assert (stored.name, stored.order, stored.updated_at) == ("ZZ 새 이름", 11, later(60))
    assert (stored.key, stored.created_at) == (CodeKey("zz_s"), NOW)


async def test_update_missing_code_raises_not_found(catalog: CatalogCase) -> None:
    """없는 코드를 수정하면 CodeNotFoundError인지 확인한다."""
    # when·then: 저장하지 않은 코드를 수정하면 CodeNotFoundError가 난다
    with pytest.raises(CodeNotFoundError):
        await catalog.codes.update(make_code(CodeKind.STATUS, key="zz_s", name="ZZ S"))


async def test_update_to_another_codes_name_ignoring_case_conflicts(catalog: CatalogCase) -> None:
    """다른 코드의 이름으로(대소문자 무시) 바꾸면 충돌하는지 확인한다."""
    # given: 코드 두 개를 저장하고 둘째 이름을 첫째와 대소문자만 다르게 바꿔 둔다
    await catalog.codes.add(make_code(CodeKind.STATUS, key="zz_one", name="ZZ One"))
    other = make_code(CodeKind.STATUS, key="zz_two", name="ZZ Two")
    await catalog.codes.add(other)
    other.rename("zz one", later(60))

    # when·then: 수정 저장하면 DuplicateCodeNameError가 난다
    with pytest.raises(DuplicateCodeNameError):
        await catalog.codes.update(other)


async def test_update_to_own_name_in_another_case_is_allowed(catalog: CatalogCase) -> None:
    """자기 이름의 대소문자만 바꾸는 수정은 허용되는지 확인한다."""
    # given: 저장된 코드의 이름 대소문자를 바꿔 둔다
    code = make_code(CodeKind.STATUS, key="zz_s", name="ZZ Name")
    await catalog.codes.add(code)
    code.rename("zz name", later(60))

    # when: 수정 저장한다
    await catalog.codes.update(code)

    # then: 바뀐 이름이 읽힌다
    assert (await catalog.codes.get(code.id)).name == "zz name"


async def test_delete_removes_only_that_code(catalog: CatalogCase) -> None:
    """삭제하면 그 코드만 사라지는지 확인한다."""
    # given: 코드 두 개를 저장한다
    gone = make_code(CodeKind.STATUS, key="zz_gone", name="ZZ Gone")
    kept = make_code(CodeKind.STATUS, key="zz_kept", name="ZZ Kept")
    await catalog.codes.add(gone)
    await catalog.codes.add(kept)

    # when: 하나를 삭제한다
    await catalog.codes.delete(gone.id)

    listed = await catalog.mine_codes(CodeKind.STATUS, {gone.id, kept.id})

    # then: 남은 코드만 목록에 있고 삭제한 코드는 읽으면 CodeNotFoundError다
    assert [c.id for c in listed] == [kept.id]
    with pytest.raises(CodeNotFoundError):
        await catalog.codes.get(gone.id)


async def test_deleted_name_and_key_can_be_added_again(catalog: CatalogCase) -> None:
    """삭제한 이름과 key를 다시 쓸 수 있는지 확인한다."""
    # given: 코드를 저장했다가 삭제한다
    first = make_code(CodeKind.STATUS, key="zz_again", name="ZZ Again")
    await catalog.codes.add(first)
    await catalog.codes.delete(first.id)
    again = make_code(CodeKind.STATUS, key="zz_again", name="ZZ Again")

    # when: 같은 이름·key의 코드를 다시 저장한다
    await catalog.codes.add(again)

    # then: 새 코드가 읽힌다
    assert (await catalog.codes.get(again.id)).id == again.id


async def test_delete_missing_code_raises_not_found(catalog: CatalogCase) -> None:
    """없는 코드를 삭제하면 CodeNotFoundError인지 확인한다."""
    # when·then: 없는 id를 삭제하면 CodeNotFoundError가 난다
    with pytest.raises(CodeNotFoundError):
        await catalog.codes.delete(CodeId(new_id()))
