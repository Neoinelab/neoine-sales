"""Deal Product 이름 변경 리비전(a9d3f5c7e214): deals.solution을 deals.product로 이름만 바꾼다.

Vendor 필수 리비전(e6b1d4f8a302)까지 올린 스키마에 Deal 행을 넣은 뒤 head로 올려,
값·행이 그대로인 채 열 이름만 바뀌는지, downgrade가 이름만 되돌리고 값이 그대로인지 확인한다.
실제 PostgreSQL이 필요하다.
(리비전 그래프·upgrade 본문 검사는 DB가 필요 없어 test_revision_graph.py에 있다.)
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

PARENT = "e6b1d4f8a302"
HEAD = "a9d3f5c7e214"

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
    " procurement, {column}, created_at, updated_at, status_changed_on) values (:id, :code, 'n',"
    " 1, 1, 10, 'status', 'prospecting', 'forecast', 'pipeline', 100, current_date, 1,"
    " '', :value, now(), now(), current_date)"
)
OTHER_COLUMNS = (
    "select id, deal_code, name, owner_user_id, vendor_id, users, revenue_amount, procurement"
    " from deals order by id"
)
COLUMN_INFO = (
    "select column_name, data_type, character_maximum_length, is_nullable"
    " from information_schema.columns where table_schema = 'public' and table_name = 'deals'"
    " and column_name in ('solution', 'product') order by column_name"
)


async def _seed(url: URL, *, target: str, column: str, values: list[str]) -> None:
    """target 리비전까지 올리고 (column에 값을 넣은) Deal들을 넣는다."""
    await when_operator_upgrades(url, target=target)
    await run_sql(url, INSERT_USER)
    await run_sql(url, INSERT_CONTACT)
    await run_sql(url, INSERT_VENDOR)
    for number, value in enumerate(values, start=1):
        params = {"id": number, "code": f"20261116-A00{number}", "value": value}
        await run_sql(url, INSERT_DEAL.format(column=column), params)


async def test_upgrade_renames_the_column_and_keeps_every_row_and_value(
    blank_database: URL,
) -> None:
    """Product 이름 변경 upgrade는 행·값을 그대로 두고 deals.solution을 deals.product로 바꾼다.

    테스트 코드: SC-050
    """
    # given: 부모 리비전 스키마에 solution이 "ITDR"·""인 Deal 2건
    await _seed(blank_database, target=PARENT, column="solution", values=["ITDR", ""])
    others_before = await run_sql(blank_database, OTHER_COLUMNS)

    # when: head까지 올린다
    await when_operator_upgrades(blank_database)

    # then: 버전은 head이고 solution 열이 없으며 product가 varchar(200) NOT NULL이다
    await then_schema_is_at(blank_database, HEAD)
    assert await run_sql(blank_database, COLUMN_INFO) == [
        ("product", "character varying", 200, "NO")
    ]
    # then: 두 Deal의 product는 "ITDR"·""이고 다른 열 값과 행 수가 전과 같다
    assert await run_sql(blank_database, "select product from deals order by id") == [
        ("ITDR",),
        ("",),
    ]
    assert await run_sql(blank_database, OTHER_COLUMNS) == others_before
    assert len(others_before) == 2


async def test_downgrade_only_renames_the_column_back_and_keeps_every_value(
    blank_database: URL,
) -> None:
    """Product 이름 변경 downgrade는 열 이름만 solution으로 되돌리고 값이 그대로다.

    테스트 코드: SC-051
    """
    # given: head까지 올린 DB에 product가 "ITDR"인 Deal 1건
    await _seed(blank_database, target=HEAD, column="product", values=["ITDR"])
    others_at_head = await run_sql(blank_database, OTHER_COLUMNS)

    # when: 한 단계 되돌린다
    outcome = await when_operator_attempts_downgrade(blank_database, target=PARENT)

    # then: 중단되지 않고 버전이 부모이며 solution이 "ITDR"이고 product 열이 없다
    assert outcome.error is None
    await then_schema_is_at(blank_database, PARENT)
    assert await run_sql(blank_database, COLUMN_INFO) == [
        ("solution", "character varying", 200, "NO")
    ]
    assert await run_sql(blank_database, "select solution from deals") == [("ITDR",)]
    # then: 행 수와 다른 열 값이 같다
    assert await run_sql(blank_database, OTHER_COLUMNS) == others_at_head
    assert len(others_at_head) == 1
