"""Deal Vendor 필수 리비전(e6b1d4f8a302): deals.vendor_id를 NOT NULL로 바꾸고 되돌린다.

사용자 컬럼 정리 리비전(c8e3f1a7d295)까지 올린 스키마에 Deal 행을 넣은 뒤 head로 올려, Vendor가
모두 있으면 행·값이 그대로인 채 NOT NULL이 되는지, Vendor 없는 Deal이 있으면 건수·code와 함께
중단되고 스키마·행이 그대로인지, downgrade가 NOT NULL만 푸는지 확인한다. 실제 PostgreSQL이 필요하다.
"""

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

PARENT = "c8e3f1a7d295"
HEAD = "e6b1d4f8a302"

INSERT_USER = (
    "insert into users (id, login_id, role, created_at, updated_at)"
    " values (1, 'kim', 'sales', now(), now())"
)
INSERT_CONTACT = (
    "insert into contacts (id, kind, company, name, created_at, updated_at)"
    " values (1, 'customer', '회사', '담당', now(), now())"
)
INSERT_VENDOR = (
    "insert into vendors (id, name, created_at, updated_at) values (1, 'SAP', now(), now())"
)
INSERT_DEAL = (
    "insert into deals (id, deal_code, name, owner_user_id, vendor_id, users, status_kind,"
    " status_key, forecast_kind, forecast_key, revenue_amount, revenue_date, customer_id,"
    " procurement, solution, created_at, updated_at, status_changed_on) values (:id, :code, 'n',"
    " 1, :vendor_id, 10, 'status', 'prospecting', 'forecast', 'pipeline', 100, current_date, 1,"
    " '', :solution, now(), now(), current_date)"
)
SNAPSHOT = "select id, deal_code, name, vendor_id, solution from deals order by id"
VENDOR_NULLABLE = (
    "select is_nullable from information_schema.columns where table_schema = 'public'"
    " and table_name = 'deals' and column_name = 'vendor_id'"
)
VENDOR_FK = (
    "select count(*) from pg_constraint where conrelid = 'deals'::regclass and contype = 'f'"
    " and pg_get_constraintdef(oid) like '%(vendor_id)%'"
)


async def _seed_parent(url: URL, deals: list[tuple[int, str, int | None, str]]) -> None:
    """부모 리비전까지 올리고 Vendor 1개(SAP)와 (id, code, vendor_id, solution) Deal들을 넣는다."""
    await when_operator_upgrades(url, target=PARENT)
    await run_sql(url, INSERT_USER)
    await run_sql(url, INSERT_CONTACT)
    await run_sql(url, INSERT_VENDOR)
    for deal_id, code, vendor_id, solution in deals:
        params = {"id": deal_id, "code": code, "vendor_id": vendor_id, "solution": solution}
        await run_sql(url, INSERT_DEAL, params)


async def test_upgrade_keeps_every_row_and_makes_vendor_id_not_null(blank_database: URL) -> None:
    """Vendor가 모두 있는 DB의 upgrade는 행·값을 그대로 두고 vendor_id를 NOT NULL로 만든다.

    테스트 코드: SC-045
    """
    # given: 부모 리비전 스키마에 Vendor가 있는 Deal 2건(Solution은 값과 빈 값)
    await _seed_parent(
        blank_database,
        [(1, "20261116-A001", 1, "ITDR"), (2, "20261116-A002", 1, "")],
    )
    before = await run_sql(blank_database, SNAPSHOT)
    assert await run_sql(blank_database, VENDOR_NULLABLE) == [("YES",)]

    # when: head까지 올린다
    await when_operator_upgrades(blank_database)

    # then: 버전은 head이고 Deal 행·값(빈 Solution 포함)이 그대로이며 vendor_id는 NOT NULL이다
    await then_schema_is_at(blank_database, HEAD)
    assert await run_sql(blank_database, SNAPSHOT) == before
    assert len(before) == 2
    assert await run_sql(blank_database, VENDOR_NULLABLE) == [("NO",)]
    # then: Vendor FK는 그대로 있다
    assert await run_sql(blank_database, VENDOR_FK) == [(1,)]


async def test_upgrade_with_deals_without_a_vendor_aborts_and_changes_nothing(
    blank_database: URL,
) -> None:
    """Vendor 없는 Deal이 있으면 upgrade가 건수·code 문구로 중단되고 스키마·행이 그대로다.

    테스트 코드: SC-046
    """
    # given: Vendor 없는 Deal 2건과 Vendor 있는 Deal 1건이 있는 부모 리비전 스키마
    await _seed_parent(
        blank_database,
        [
            (1, "20261116-A001", None, "ITDR"),
            (2, "20261116-A002", 1, ""),
            (3, "20261116-A003", None, ""),
        ],
    )
    before = await run_sql(blank_database, SNAPSHOT)

    # when: head까지 올리면 RuntimeError로 중단된다
    with pytest.raises(RuntimeError) as aborted:
        await when_operator_upgrades(blank_database)

    # then: 건수와 Vendor 없는 Deal의 code가 문구에 있고 Vendor 있는 Deal의 code는 없다
    message = str(aborted.value)
    assert "Vendor가 없는 Deal이 2건 있어 deals.vendor_id를 NOT NULL로 바꿀 수 없습니다" in message
    assert "먼저 이 Deal들에 Vendor를 지정하세요" in message
    assert "20261116-A001" in message
    assert "20261116-A003" in message
    assert "20261116-A002" not in message
    # then: 버전은 부모 그대로, vendor_id는 NULL 허용 그대로, 행은 하나도 바뀌지 않았다
    await then_schema_is_at(blank_database, PARENT)
    assert await run_sql(blank_database, VENDOR_NULLABLE) == [("YES",)]
    assert await run_sql(blank_database, SNAPSHOT) == before


async def test_downgrade_only_drops_the_not_null_and_keeps_every_row(
    blank_database: URL,
) -> None:
    """Deal Vendor 필수 downgrade는 NOT NULL만 풀고 행·값이 그대로다.

    테스트 코드: SC-047
    """
    # given: head까지 올린 DB(Vendor 있는 Deal 2건)
    await _seed_parent(
        blank_database,
        [(1, "20261116-A001", 1, "ITDR"), (2, "20261116-A002", 1, "")],
    )
    await when_operator_upgrades(blank_database)
    at_head = await run_sql(blank_database, SNAPSHOT)

    # when: 한 단계 되돌린다
    outcome = await when_operator_attempts_downgrade(blank_database, target=PARENT)

    # then: 중단되지 않고 버전이 부모이며 vendor_id는 다시 NULL을 허용하고 행·값은 그대로다
    assert outcome.error is None
    await then_schema_is_at(blank_database, PARENT)
    assert await run_sql(blank_database, VENDOR_NULLABLE) == [("YES",)]
    assert await run_sql(blank_database, SNAPSHOT) == at_head
    assert await run_sql(blank_database, VENDOR_FK) == [(1,)]

    # when: 다시 head까지 올린다
    await when_operator_upgrades(blank_database)

    # then: 첫 upgrade 결과와 같다
    await then_schema_is_at(blank_database, HEAD)
    assert await run_sql(blank_database, VENDOR_NULLABLE) == [("NO",)]
    assert await run_sql(blank_database, SNAPSHOT) == at_head
