"""사용자 컬럼 정리 리비전(c8e3f1a7d295): users의 등록자·퇴사 사유를 없애고 되돌린다.

날짜 전환 리비전(b4d7e2a9c613)까지 올린 스키마에 등록자가 있는 사용자 행을 넣은 뒤 head로 올려
행·퇴사 시각이 그대로인지, 두 컬럼과 FK·인덱스·CHECK만 사라지는지 확인하고, downgrade가 등록자를
자기 자신으로·퇴사 사유를 deleted_at으로 채워 이전 스키마로 되돌리는지 확인한다.
실제 PostgreSQL이 필요하다.
"""

from datetime import datetime, timedelta, timezone
from typing import TYPE_CHECKING

import pytest

from tests.support.raw_sql import run_sql
from tests.support.schema_catalog import (
    then_schema_is_at,
    when_operator_attempts_downgrade,
    when_operator_upgrades,
)

if TYPE_CHECKING:
    from sqlalchemy.engine import URL

pytestmark = pytest.mark.integration

KST = timezone(timedelta(hours=9))

DATE_REVISION = "b4d7e2a9c613"
HEAD = "c8e3f1a7d295"  # 이 파일이 검증하는 리비전(전체 head보다 한 단계 앞)
FK = "fk_users_created_by_user_id_users"
INDEX = "ix_users_created_by_user_id"
CHECKS = {"ck_users_delete_reason_valid", "ck_users_deleted_pair"}
RESIGNED_AT = datetime(2026, 11, 1, tzinfo=KST)

# 날짜 전환 리비전 스키마용 원시 INSERT(등록자·퇴사 사유 컬럼이 아직 있다)
INSERT_USER = (
    "insert into users (id, login_id, role, created_by_user_id, created_at, updated_at,"
    " deleted_at, delete_reason) values (:id, :login_id, :role, :creator, now(), now(),"
    " :deleted_at, :reason)"
)
INSERT_CONTACT = (
    "insert into contacts (id, kind, company, name, created_at, updated_at)"
    " values (1, 'customer', '회사', '담당', now(), now())"
)
INSERT_DEAL = (
    "insert into deals (id, deal_code, name, owner_user_id, users, status_kind, status_key,"
    " forecast_kind, forecast_key, revenue_amount, revenue_date, customer_id, procurement,"
    " solution, created_at, updated_at, status_changed_on) values (1, '20261116-A001', 'n',"
    " 2, 10, 'status', 'prospecting', 'forecast', 'pipeline', 100, current_date, 1, '', '',"
    " now(), now(), current_date)"
)
# (id, 아이디, 역할, 등록자, 퇴사 시각, 퇴사 사유): root는 자기 자신이 등록자다
USERS = [
    (1, "root", "admin", 1, None, None),
    (2, "kim", "sales", 1, None, None),
    (3, "lee", "sales", 1, RESIGNED_AT, "resigned"),
]
SNAPSHOT = "select id, login_id, role, deleted_at is not null from users order by id"
COLUMNS = (
    "select column_name from information_schema.columns"
    " where table_schema = 'public' and table_name = 'users'"
)
CONSTRAINTS = "select conname from pg_constraint where conrelid = 'users'::regclass"
INDEXES = "select indexname from pg_indexes where schemaname = 'public' and tablename = 'users'"


async def _seed_before(url: URL) -> None:
    """날짜 전환 리비전까지 올리고 사용자 3명(재직 2·퇴사 1)과 kim이 Owner인 Deal 하나를 넣는다."""
    await when_operator_upgrades(url, target=DATE_REVISION)
    for user_id, login_id, role, creator, deleted_at, reason in USERS:
        await run_sql(
            url,
            INSERT_USER,
            {
                "id": user_id,
                "login_id": login_id,
                "role": role,
                "creator": creator,
                "deleted_at": deleted_at,
                "reason": reason,
            },
        )
    await run_sql(url, INSERT_CONTACT)
    await run_sql(url, INSERT_DEAL)


async def _names(url: URL, statement: str) -> set[str]:
    return {row[0] for row in await run_sql(url, statement)}


async def _deleted_at_texts(url: URL) -> list[tuple[int, str | None]]:
    rows = await run_sql(url, "select id, deleted_at at time zone 'UTC' from users order by id")
    return [(row[0], None if row[1] is None else str(row[1])) for row in rows]


async def test_upgrade_keeps_the_user_rows_and_drops_only_the_creator_and_reason(
    blank_database: URL,
) -> None:
    """사용자 컬럼 정리 upgrade는 사용자 행·퇴사 시각을 두고 두 컬럼과 FK·인덱스·CHECK만 없앤다.

    테스트 코드: SC-041
    """
    # given: 등록자가 있는 사용자 3명과 kim이 Owner인 Deal이 있는 날짜 전환 리비전 스키마
    await _seed_before(blank_database)
    rows_before = await run_sql(blank_database, SNAPSHOT)
    resigned_before = await _deleted_at_texts(blank_database)
    assert len(rows_before) == 3

    # when: head까지 올린다
    await when_operator_upgrades(blank_database, target=HEAD)

    # then: 버전은 head이고 사용자 (id, 아이디, 역할, 퇴사 여부)와 퇴사 시각이 그대로다(행 수 3)
    await then_schema_is_at(blank_database, HEAD)
    assert await run_sql(blank_database, SNAPSHOT) == rows_before
    assert await _deleted_at_texts(blank_database) == resigned_before
    # then: 두 컬럼과 FK·인덱스·CHECK 2개가 없다
    columns = await _names(blank_database, COLUMNS)
    assert not {"created_by_user_id", "delete_reason"} & columns
    assert FK not in await _names(blank_database, CONSTRAINTS)
    assert not CHECKS & await _names(blank_database, CONSTRAINTS)
    assert INDEX not in await _names(blank_database, INDEXES)
    # then: Deal의 Owner는 kim 그대로다
    assert await run_sql(blank_database, "select owner_user_id from deals") == [(2,)]


async def test_downgrade_fills_the_creator_with_itself_and_the_reason_from_deleted_at(
    blank_database: URL,
) -> None:
    """사용자 컬럼 정리 downgrade는 등록자를 자기 자신으로, 퇴사 사유를 deleted_at에서 채운다.

    테스트 코드: SC-042
    """
    # given: head까지 올린 DB(재직 2명, 퇴사 1명)
    await _seed_before(blank_database)
    await when_operator_upgrades(blank_database, target=HEAD)
    at_head = await run_sql(blank_database, SNAPSHOT)

    # when: 한 단계 되돌린다
    outcome = await when_operator_attempts_downgrade(blank_database, target=DATE_REVISION)

    # then: 중단되지 않고 버전이 날짜 전환 리비전이며 사용자 행 수는 3이다
    assert outcome.error is None
    await then_schema_is_at(blank_database, DATE_REVISION)
    assert await run_sql(blank_database, SNAPSHOT) == at_head
    # then: 모든 행의 등록자는 자기 id이고 NOT NULL이며 FK(RESTRICT)와 인덱스가 있다
    creators = await run_sql(blank_database, "select id, created_by_user_id from users order by id")
    assert [tuple(row) for row in creators] == [(1, 1), (2, 2), (3, 3)]
    nullable = await run_sql(
        blank_database,
        "select is_nullable from information_schema.columns where table_schema = 'public'"
        " and table_name = 'users' and column_name = 'created_by_user_id'",
    )
    assert nullable == [("NO",)]
    fk = await run_sql(
        blank_database,
        "select confdeltype::text from pg_constraint where conname = :name",
        {"name": FK},
    )
    assert fk == [("r",)]  # r = RESTRICT
    assert INDEX in await _names(blank_database, INDEXES)
    # then: 퇴사 사유는 퇴사한 lee만 resigned이고 CHECK 2개가 있다
    reasons = await run_sql(blank_database, "select id, delete_reason from users order by id")
    assert [tuple(row) for row in reasons] == [(1, None), (2, None), (3, "resigned")]
    assert await _names(blank_database, CONSTRAINTS) >= CHECKS

    # when: 다시 head까지 올린다
    await when_operator_upgrades(blank_database, target=HEAD)

    # then: 첫 upgrade 결과와 같다
    await then_schema_is_at(blank_database, HEAD)
    assert await run_sql(blank_database, SNAPSHOT) == at_head
    assert not {"created_by_user_id", "delete_reason"} & await _names(blank_database, COLUMNS)
