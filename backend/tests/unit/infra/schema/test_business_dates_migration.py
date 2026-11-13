"""날짜 전환 리비전(b4d7e2a9c613): 기존 시각 컬럼 4개를 업무 날짜(date) 컬럼으로 옮기고 되돌린다.

기준선 스키마에 옛 형식(timestamptz) 행을 넣은 뒤 head까지 올려 채움·행 수 보존·NOT NULL·옛 컬럼
drop을 확인하고, downgrade로 날짜의 00:00(업무 시간대)이 되살아나는지 확인한다. 업무 시간대는
마이그레이션을 실행하는 프로세스의 OS 로컬 시간대(테스트가 Asia/Seoul로 고정)다.
실제 PostgreSQL이 필요하다.
"""

from datetime import date, datetime
from typing import TYPE_CHECKING

import pytest

from tests.support.raw_sql import run_sql
from tests.support.schema_catalog import (
    table_names,
    then_schema_is_at,
    when_operator_attempts_downgrade,
    when_operator_upgrades,
)

if TYPE_CHECKING:
    from collections.abc import Callable

    from sqlalchemy.engine import URL

pytestmark = pytest.mark.integration

BASELINE = "00c3126aa926"
HEAD = "b4d7e2a9c613"

# 기준선 스키마용 원시 INSERT(옛 컬럼 이름). 제약 통과에 필요한 열만 넣는다.
INSERT_USER = (
    "insert into users (id, login_id, role, created_by_user_id, created_at, updated_at)"
    " values (1, 'kim', 'sales', 1, now(), now())"
)
INSERT_CONTACT = (
    "insert into contacts (id, kind, company, name, created_at, updated_at)"
    " values (1, 'customer', '회사', '담당', now(), now())"
)
INSERT_DEAL = (
    "insert into deals (id, deal_code, name, owner_user_id, users, status_kind, status_key,"
    " forecast_kind, forecast_key, revenue_amount, revenue_date, customer_id, quote_submitted,"
    " quote_submitted_date, poc_state, poc_completed_date, procurement, solution, created_at,"
    " updated_at, status_changed_at) values (:id, :code, 'n', 1, 10, 'status', 'prospecting',"
    " 'forecast', 'pipeline', 100, current_date, 1, null, null, null, null, '', '',"
    " now(), now(), :changed_at)"
)
INSERT_ACTION = (
    "insert into deal_actions (id, deal_id, action_type_id, action, memo, next_action, due_date,"
    " next_action_status, next_action_closed_at, acted_at, actor_user_id, status_key,"
    " forecast_key, created_at, updated_at) values (:id, :deal_id,"
    " (select id from action_types where name = '미팅'), 'a', '', :next_action, :due_date,"
    " :status, :closed_at, :acted_at, 1, 'prospecting', 'pipeline', now(), now())"
)
INSERT_CONTRACT = (
    "insert into license_contracts (id, deal_id, status, license_start, license_end,"
    " term_amount, term_unit, ended_at, created_by_user_id, updated_by_user_id, created_at,"
    " updated_at) values (:id, :deal_id, :status, :start, :end, :amount, :unit, :ended_at,"
    " 1, 1, now(), now())"
)

# (id, 옛 acted_at, next_action, due_date, 상태, 옛 next_action_closed_at)
ACTIONS = [
    (1, "2026-11-10T23:59:59+09:00", None, None, None, None),  # 서울 11-10
    (2, "2026-11-10T15:30:00Z", "계획", "2026-12-01", "open", None),  # 서울 11-11
    (3, "2026-11-12T01:00:00+09:00", "계획", "2026-12-01", "done", "2026-11-12T16:00:00Z"),
    (4, "2026-11-13T00:00:00+09:00", "계획", "2026-12-01", "not_done", "2026-11-14T14:59:59Z"),
]
# (id, 옛 status_changed_at) → 서울 날짜
DEAL_ENTRIES = {
    "20261116-A001": "2026-11-09T14:59:59Z",  # 서울 11-09 23:59:59
    "20261116-A002": "2026-11-09T15:00:00Z",  # 서울 11-10 00:00:00
}
EXPECTED_ACTED_ON = {1: "2026-11-10", 2: "2026-11-11", 3: "2026-11-12", 4: "2026-11-13"}
EXPECTED_CLOSED_ON = {1: None, 2: None, 3: "2026-11-13", 4: "2026-11-14"}
EXPECTED_ENTRY_ON = {"20261116-A001": "2026-11-09", "20261116-A002": "2026-11-10"}


@pytest.fixture(autouse=True)
def _seoul(local_tz: Callable[[str], None]) -> None:
    local_tz("Asia/Seoul")


async def _seed_baseline(url: URL) -> None:
    """기준선까지만 올리고 옛 형식의 Deal 2건·Action 4건·계약 2건을 넣는다."""
    await when_operator_upgrades(url, target=BASELINE)
    await run_sql(url, INSERT_USER)
    await run_sql(url, INSERT_CONTACT)
    for number, (code, changed_at) in enumerate(DEAL_ENTRIES.items(), start=1):
        await run_sql(url, INSERT_DEAL, {"id": number, "code": code, "changed_at": _ts(changed_at)})
    for action_id, acted_at, next_action, due, status, closed_at in ACTIONS:
        await run_sql(
            url,
            INSERT_ACTION,
            {
                "id": action_id,
                "deal_id": 1,
                "next_action": next_action,
                "due_date": None if due is None else _day(due),
                "status": status,
                "closed_at": _ts(closed_at),
                "acted_at": _ts(acted_at),
            },
        )
    contracts = ((1, "not_issued", None), (2, "ended", "2026-06-30T16:30:00Z"))
    for contract_id, status, ended_at in contracts:
        issued = status == "ended"
        await run_sql(
            url,
            INSERT_CONTRACT,
            {
                "id": contract_id,
                "deal_id": 1,
                "status": status,
                "start": _day("2026-01-01") if issued else None,
                "end": _day("2026-12-31") if issued else None,
                "amount": 1 if issued else None,
                "unit": "year" if issued else None,
                "ended_at": _ts(ended_at),
            },
        )


def _day(text: str) -> date:
    return date.fromisoformat(text)


def _ts(text: str | None) -> datetime | None:
    """ISO 8601 문자열(Z 또는 오프셋 포함)을 시간대 있는 datetime으로."""
    return None if text is None else datetime.fromisoformat(text)


async def _row_counts(url: URL) -> dict[str, int]:
    counts = {}
    for table in ("deals", "deal_actions", "license_contracts"):
        rows = await run_sql(url, f"select count(*) from {table}")  # noqa: S608 - 상수 이름
        counts[table] = int(rows[0][0])
    return counts


async def _columns(url: URL, table: str) -> dict[str, tuple[str, str]]:
    rows = await run_sql(
        url,
        "select column_name, data_type, is_nullable from information_schema.columns"
        " where table_schema = 'public' and table_name = :table",
        {"table": table},
    )
    return {name: (data_type, nullable) for name, data_type, nullable in rows}


async def _names(url: URL, statement: str, table: str) -> set[str]:
    rows = await run_sql(url, statement, {"table": table})
    return {row[0] for row in rows}


CONSTRAINTS = "select conname from pg_constraint where conrelid = cast(:table as regclass)"
INDEXES = "select indexname from pg_indexes where schemaname = 'public' and tablename = :table"


async def test_upgrade_fills_acted_on_with_the_business_date_and_keeps_the_rows(
    blank_database: URL,
) -> None:
    """업그레이드는 수행 일시를 업무 시간대 날짜로 채우고 행 수를 유지한 뒤 acted_at을 없앤다.

    테스트 코드: AC-113
    """
    # given: 기준선에 옛 형식 Deal 2건·Action 4건·계약 2건이 있다 (전제: 업무 시간대 Asia/Seoul)
    await _seed_baseline(blank_database)
    before = await _row_counts(blank_database)

    # when: head(날짜 전환 리비전)까지 올린다
    await when_operator_upgrades(blank_database)

    # then: 버전은 head이고 모든 테이블의 행 수가 그대로다
    await then_schema_is_at(blank_database, HEAD)
    assert (
        await _row_counts(blank_database)
        == before
        == {
            "deals": 2,
            "deal_actions": 4,
            "license_contracts": 2,
        }
    )
    # then: 수행일은 업무 시간대 날짜다(서울 23:59:59 → 같은 날, UTC 15:30 → 다음 날)
    rows = await run_sql(blank_database, "select id, acted_on::text from deal_actions order by id")
    assert {row[0]: row[1] for row in rows} == EXPECTED_ACTED_ON
    # then: acted_on은 NOT NULL date이고 acted_at 컬럼은 없다
    columns = await _columns(blank_database, "deal_actions")
    assert columns["acted_on"] == ("date", "NO")
    assert "acted_at" not in columns


async def test_upgrade_fills_next_action_closed_on_and_keeps_null_for_open_rows(
    blank_database: URL,
) -> None:
    """종료 시각은 업무 날짜로 채우고 비어 있던 행은 null로 두며 CHECK를 새 컬럼으로 만든다.

    테스트 코드: NA-071
    """
    # given: 종료·미종료 Action이 섞인 기준선 DB
    await _seed_baseline(blank_database)

    # when: head까지 올린다
    await when_operator_upgrades(blank_database)

    # then: 종료일은 업무 날짜(UTC 16:00 → 서울 다음 날)이고 미종료 행은 null이다
    rows = await run_sql(
        blank_database,
        "select id, next_action_closed_on::text from deal_actions order by id",
    )
    assert {row[0]: row[1] for row in rows} == EXPECTED_CLOSED_ON
    # then: 컬럼은 NULL 허용 date이고 옛 컬럼은 없다
    columns = await _columns(blank_database, "deal_actions")
    assert columns["next_action_closed_on"] == ("date", "YES")
    assert "next_action_closed_at" not in columns
    # then: CHECK는 새 컬럼 이름으로 바뀌었고 옛 이름은 없다
    constraints = await _names(blank_database, CONSTRAINTS, "deal_actions")
    assert "ck_deal_actions_next_action_closed_on" in constraints
    assert "ck_deal_actions_next_action_closed_at" not in constraints


async def test_upgrade_renames_the_acted_on_indexes(blank_database: URL) -> None:
    """수행일 인덱스 둘이 acted_on 기준 이름으로 바뀌고 옛 인덱스는 없다.

    테스트 코드: AC-113
    """
    # given: 기준선 DB
    await when_operator_upgrades(blank_database, target=BASELINE)

    # when: head까지 올린다
    await when_operator_upgrades(blank_database)

    # then: 새 인덱스 이름만 있다
    indexes = await _names(blank_database, INDEXES, "deal_actions")
    assert {"ix_deal_actions_acted_on", "ix_deal_actions_deal_id_acted_on"} <= indexes
    assert not {"ix_deal_actions_acted_at", "ix_deal_actions_deal_id_acted_at"} & indexes


async def test_upgrade_fills_status_changed_on_and_makes_it_not_null(
    blank_database: URL,
) -> None:
    """Status 진입 시각을 업무 날짜로 채워 NOT NULL date로 바꾸고 옛 컬럼을 없앤다.

    테스트 코드: RK-069
    """
    # given: Status 진입 시각이 서울 자정 직전·직후인 Deal 둘이 있는 기준선 DB
    await _seed_baseline(blank_database)

    # when: head까지 올린다
    await when_operator_upgrades(blank_database)

    # then: 진입일은 서울 날짜다(23:59:59 → 11-09, 00:00:00 → 11-10)
    rows = await run_sql(
        blank_database, "select deal_code, status_changed_on::text from deals order by deal_code"
    )
    assert {row[0]: row[1] for row in rows} == EXPECTED_ENTRY_ON
    # then: NOT NULL date이고 옛 컬럼은 없다
    columns = await _columns(blank_database, "deals")
    assert columns["status_changed_on"] == ("date", "NO")
    assert "status_changed_at" not in columns


async def test_upgrade_fills_ended_on_and_keeps_null_for_not_ended_contracts(
    blank_database: URL,
) -> None:
    """계약 종료 시각은 업무 날짜로 채우고 비어 있던 행은 null로 두며 CHECK를 새 컬럼으로 만든다.

    테스트 코드: LC-087
    """
    # given: 미발급 계약(ended_at 없음)과 종료 계약(UTC 6/30 16:30 = 서울 7/1)이 있는 기준선 DB
    await _seed_baseline(blank_database)

    # when: head까지 올린다
    await when_operator_upgrades(blank_database)

    # then: 종료 계약은 서울 날짜 2026-07-01이고 미발급 계약은 null이다
    rows = await run_sql(
        blank_database, "select id, ended_on::text from license_contracts order by id"
    )
    assert {row[0]: row[1] for row in rows} == {1: None, 2: "2026-07-01"}
    # then: ended_on은 NULL 허용 date이고 옛 컬럼은 없다
    columns = await _columns(blank_database, "license_contracts")
    assert columns["ended_on"] == ("date", "YES")
    assert "ended_at" not in columns
    # then: CHECK는 새 이름으로 바뀌었다
    constraints = await _names(blank_database, CONSTRAINTS, "license_contracts")
    assert "ck_license_contracts_ended_has_date" in constraints
    assert "ck_license_contracts_ended_has_time" not in constraints


async def test_downgrade_restores_the_time_columns_at_midnight_of_the_business_date(
    blank_database: URL,
) -> None:
    """downgrade는 옛 시각 컬럼을 날짜의 업무 시간대 00:00으로 되살리고 새 컬럼을 없앤다.

    테스트 코드: AC-114, RK-069
    """
    # given: 옛 형식 데이터를 넣고 head까지 올린 DB
    await _seed_baseline(blank_database)
    await when_operator_upgrades(blank_database)
    before = await _row_counts(blank_database)

    # when: 한 단계 되돌린다(기준선으로)
    outcome = await when_operator_attempts_downgrade(blank_database, target=BASELINE)

    # then: 중단되지 않고 버전이 기준선이며 행 수가 그대로다
    assert outcome.error is None
    await then_schema_is_at(blank_database, BASELINE)
    assert await _row_counts(blank_database) == before
    # then: acted_at은 NOT NULL timestamptz이고 날짜의 서울 00:00(UTC로 전날 15:00)이다
    columns = await _columns(blank_database, "deal_actions")
    assert columns["acted_at"] == ("timestamp with time zone", "NO")
    assert "acted_on" not in columns
    acted = await run_sql(
        blank_database,
        "select id, to_char(acted_at at time zone 'Asia/Seoul', 'YYYY-MM-DD HH24:MI:SS')"
        " from deal_actions order by id",
    )
    assert {row[0]: row[1] for row in acted} == {
        1: "2026-11-10 00:00:00",
        2: "2026-11-11 00:00:00",
        3: "2026-11-12 00:00:00",
        4: "2026-11-13 00:00:00",
    }
    # then: 종료 시각은 NULL 허용이고 값이 없던 행은 null, 있던 행은 날짜의 00:00이다
    assert columns["next_action_closed_at"] == ("timestamp with time zone", "YES")
    closed = await run_sql(
        blank_database,
        "select id, to_char(next_action_closed_at at time zone 'Asia/Seoul',"
        " 'YYYY-MM-DD HH24:MI:SS') from deal_actions order by id",
    )
    assert {row[0]: row[1] for row in closed} == {
        1: None,
        2: None,
        3: "2026-11-13 00:00:00",
        4: "2026-11-14 00:00:00",
    }
    # then: Status 진입 시각과 계약 종료 시각도 00:00으로 되살아나고 옛 CHECK·인덱스가 돌아온다
    entry = await run_sql(
        blank_database,
        "select deal_code, to_char(status_changed_at at time zone 'Asia/Seoul',"
        " 'YYYY-MM-DD HH24:MI:SS') from deals order by deal_code",
    )
    assert {row[0]: row[1] for row in entry} == {
        "20261116-A001": "2026-11-09 00:00:00",
        "20261116-A002": "2026-11-10 00:00:00",
    }
    ended = await run_sql(
        blank_database,
        "select id, to_char(ended_at at time zone 'Asia/Seoul', 'YYYY-MM-DD HH24:MI:SS')"
        " from license_contracts order by id",
    )
    assert {row[0]: row[1] for row in ended} == {1: None, 2: "2026-07-01 00:00:00"}
    assert "ck_deal_actions_next_action_closed_at" in await _names(
        blank_database, CONSTRAINTS, "deal_actions"
    )
    assert "ck_license_contracts_ended_has_time" in await _names(
        blank_database, CONSTRAINTS, "license_contracts"
    )
    assert {"ix_deal_actions_acted_at", "ix_deal_actions_deal_id_acted_at"} <= await _names(
        blank_database, INDEXES, "deal_actions"
    )
    assert "status_changed_on" not in await _columns(blank_database, "deals")


async def test_upgrade_on_an_empty_database_creates_only_the_date_columns(
    blank_database: URL,
) -> None:
    """빈 DB를 head까지 올리면 앱 테이블에 날짜 컬럼만 있고 옛 시각 컬럼은 없다.

    테스트 코드: SC-004
    """
    # when: 빈 DB에 upgrade head를 한다
    await when_operator_upgrades(blank_database)

    # then: 네 날짜 컬럼이 있고 옛 네 컬럼은 어느 테이블에도 없다
    assert "alembic_version" in await table_names(blank_database)
    assert "acted_on" in await _columns(blank_database, "deal_actions")
    assert "next_action_closed_on" in await _columns(blank_database, "deal_actions")
    assert "status_changed_on" in await _columns(blank_database, "deals")
    assert "ended_on" in await _columns(blank_database, "license_contracts")
    leftovers = await run_sql(
        blank_database,
        "select table_name, column_name from information_schema.columns"
        " where table_schema = 'public' and column_name in"
        " ('acted_at', 'next_action_closed_at', 'status_changed_at', 'ended_at')",
    )
    assert leftovers == []
