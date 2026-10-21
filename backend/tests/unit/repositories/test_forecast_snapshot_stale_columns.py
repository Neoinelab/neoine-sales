"""SQL 전용: 스냅숏을 만드는 사이 코드가 바뀌어 셀이 열과 맞지 않는 경우(복합 FK 위반).

`replace`가 DB 오류를 그대로 올리지 않고 '다시 실행' 안내가 있는 RuntimeError로 바꾸고, 호출한 쪽이
롤백하면 이전 스냅숏이 그대로 남는다. 열에 없는 key의 셀을 거절하는 것은 DB의 복합 FK이므로 Fake에는
같은 불변식이 없다(메모리 dict, FK 없음). 그래서 Fake용 계약은 만들지 않고 SQL만 검증한다.
"""

from typing import TYPE_CHECKING

import pytest

from app.domain.forecast.snapshot import YearMonth
from tests.support.user_ids import uid
from tests.unit.repositories.forecast_snapshot_case import (
    make_cell,
    make_column,
    make_snapshot,
    open_snapshot_case,
)

if TYPE_CHECKING:
    from sqlalchemy.engine import URL

pytestmark = pytest.mark.integration

SEPT = YearMonth(2026, 9)
KIM = uid("stale-kim")


async def test_cell_with_a_key_missing_from_columns_raises_rerun_runtime_error(
    test_database_url: URL,
) -> None:
    async with open_snapshot_case("sql", test_database_url) as case:
        await case.ensure_owner(KIM)
        stale = make_snapshot(
            SEPT,
            make_cell(KIM, key="commit"),
            columns=[make_column("pipeline")],  # commit 열이 없다
        )

        with pytest.raises(RuntimeError, match="다시 실행"):
            await case.snapshots.replace(stale)


async def test_failed_replace_leaves_the_previous_snapshot_after_rollback(
    test_database_url: URL,
) -> None:
    async with open_snapshot_case("sql", test_database_url) as case:
        await case.ensure_owner(KIM)
        previous = make_snapshot(SEPT, make_cell(KIM, key="pipeline", amount=7))
        await case.snapshots.replace(previous)
        savepoint = await case.snapshots._session.begin_nested()
        stale = make_snapshot(
            SEPT,
            make_cell(KIM, key="commit", amount=99),
            columns=[make_column("pipeline")],
        )

        with pytest.raises(RuntimeError):
            await case.snapshots.replace(stale)
        await savepoint.rollback()

        found = await case.snapshots.get(SEPT)
        assert found is not None
        assert [(c.forecast_key, c.tally.amount) for c in found.cells] == [("pipeline", 7)]
        assert len(found.columns) == len(previous.columns)
