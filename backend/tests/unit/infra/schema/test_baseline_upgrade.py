"""최초 리비전(00c3126aa926)을 빈 임시 DB에 적용하는 운영자 명령(alembic upgrade/downgrade) 검증.

과거 리비전 체인은 2026-11-05에 최초 리비전 하나로 통합되었고 최초 리비전은 되돌릴 수 없다.
실제 PostgreSQL이 필요하므로 `integration` 마커를 쓴다(SC는 Fake 원칙의 예외).
"""

from typing import TYPE_CHECKING

import pytest
from alembic.util.exc import CommandError

from tests.factories_action_type import DEFAULT_ACTION_TYPE_NAMES
from tests.fakes.catalog_seed import DEFAULT_FORECASTS, DEFAULT_LABELS, DEFAULT_STATUSES
from tests.support.raw_sql import run_sql
from tests.support.schema_catalog import (
    table_names,
    table_structure,
    then_command_aborted,
    then_schema_is_at,
    when_operator_attempts_downgrade,
    when_operator_upgrades,
)

if TYPE_CHECKING:
    from sqlalchemy.engine import URL

pytestmark = pytest.mark.integration

BASELINE = "00c3126aa926"
SEEDED = {"codes": 13, "bant_labels": 23, "action_types": 8}
APP_TABLES = {
    "users",
    "login_failures",
    "directory_settings",
    "user_password_hashes",
    "auth_settings",
    "auth_sessions",
    "contacts",
    "codes",
    "bant_labels",
    "action_types",
    "vendors",
    "deals",
    "deal_partners",
    "deal_bant_labels",
    "deal_history",
    "deal_actions",
    "deal_attachments",
    "storage_settings",
    "alert_settings",
    "forecast_snapshots",
    "forecast_snapshot_columns",
    "forecast_snapshot_cells",
    "reports",
    "partner_meetings",
    "license_contracts",
    "license_contract_attachments",
}
EN_DASH = chr(0x2013)


async def _row_count(url: URL, table: str) -> int:
    rows = await run_sql(url, f"select count(*) from {table}")  # noqa: S608 - 상수 이름
    return int(rows[0][0])


async def test_upgrade_head_on_a_blank_database_creates_the_26_tables(
    blank_database: URL,
) -> None:
    """빈 DB에 head까지 올리면 앱 테이블 26개와 alembic_version만 생긴다.

    테스트 코드: SC-004
    """
    # when: upgrade head를 실행한다
    #   (전제: 마이그레이션이 하나도 적용되지 않은 빈 임시 DB(blank_database))
    await when_operator_upgrades(blank_database)
    # then: 앱 테이블 26개와 alembic_version뿐이고 버전은 기준선이다
    assert len(APP_TABLES) == 26
    assert await table_names(blank_database) == {*APP_TABLES, "alembic_version"}
    await then_schema_is_at(blank_database, BASELINE)


async def test_upgrade_head_on_a_blank_database_seeds_only_the_default_catalog(
    blank_database: URL,
) -> None:
    """새 DB에는 기본 코드·BANT Label·Action 유형만 있고 나머지 테이블은 비어 있다.

    테스트 코드: SC-005
    """
    # when: upgrade head를 실행한다 (전제: 빈 임시 DB)
    await when_operator_upgrades(blank_database)
    # then: 시드 3개 테이블만 정해진 행 수이고 나머지는 0이다
    for table in sorted(APP_TABLES):
        assert await _row_count(blank_database, table) == SEEDED.get(table, 0), table
    # then: Forecast best의 확률 힌트는 EN DASH를 쓴다
    hints = await run_sql(
        blank_database,
        "select probability_hint from codes where kind = 'forecast' and key = 'best'",
    )
    assert hints == [(f"51{EN_DASH}75",)]


async def test_upgrade_head_seeds_the_same_values_as_the_fake_seed(blank_database: URL) -> None:
    """새 DB의 시드 값(코드·BANT Label·Action 유형)이 Fake 시드와 순서까지 같다.

    테스트 코드: SC-006
    """
    # when: upgrade head를 실행한다 (전제: 빈 임시 DB)
    await when_operator_upgrades(blank_database)
    # then: codes가 Fake 시드(Status 7 + Forecast 6)와 같다
    codes = await run_sql(
        blank_database,
        "select kind, key, name, sort_order, outcome, probability_hint from codes"
        " order by (kind = 'forecast'), sort_order",
    )
    expected_codes = [
        ("status", key, name, order, "open", None)
        for order, (key, name) in enumerate(DEFAULT_STATUSES, start=1)
    ] + [
        ("forecast", key, name, order, outcome, hint)
        for order, (key, name, outcome, hint) in enumerate(DEFAULT_FORECASTS, start=1)
    ]
    assert [tuple(row) for row in codes] == expected_codes
    # then: bant_labels가 Fake 시드와 같고 모두 기본 Label이며 만든 사람이 없다
    labels = await run_sql(
        blank_database,
        "select category, name, default_order, is_default, created_by_user_id from bant_labels",
    )
    expected_labels = {
        (category, name, order, True, None)
        for category, names in DEFAULT_LABELS.items()
        for order, name in enumerate(names, start=1)
    }
    assert {tuple(row) for row in labels} == expected_labels
    assert len(labels) == len(expected_labels)
    # then: action_types가 Fake 시드와 같고 모두 기본 유형이며 만든 사람이 없다
    types = await run_sql(
        blank_database,
        "select name, default_order, is_default, created_by_user_id from action_types"
        " order by default_order",
    )
    assert [tuple(row) for row in types] == [
        (name, order, True, None) for order, name in enumerate(DEFAULT_ACTION_TYPE_NAMES, start=1)
    ]


async def test_upgrade_head_at_head_changes_nothing(blank_database: URL) -> None:
    """이미 head인 DB에 upgrade head를 다시 실행해도 구조와 행 수가 그대로다.

    테스트 코드: SC-007
    """
    # given: head까지 올린 DB와 모든 앱 테이블의 구조·행 수 기록
    await when_operator_upgrades(blank_database)
    structure_before = {t: await table_structure(blank_database, t) for t in sorted(APP_TABLES)}
    counts_before = {t: await _row_count(blank_database, t) for t in sorted(APP_TABLES)}
    # when: upgrade head를 다시 실행한다
    await when_operator_upgrades(blank_database)
    # then: 버전, 모든 앱 테이블의 구조와 행 수가 기록과 같다
    await then_schema_is_at(blank_database, BASELINE)
    structure_after = {t: await table_structure(blank_database, t) for t in sorted(APP_TABLES)}
    counts_after = {t: await _row_count(blank_database, t) for t in sorted(APP_TABLES)}
    assert structure_after == structure_before
    assert counts_after == counts_before


async def test_upgrade_head_from_a_retired_revision_fails_without_changes(
    blank_database: URL,
) -> None:
    """통합 전 리비전 id가 남은 DB는 upgrade가 실패하고 스키마는 바뀌지 않는다.

    테스트 코드: SC-008
    """
    # given: alembic_version에 퇴역 리비전 id만 있는 DB
    await run_sql(
        blank_database, "create table alembic_version (version_num varchar(32) primary key)"
    )
    await run_sql(blank_database, "insert into alembic_version values ('f2b7c9e4a615')")
    # when: upgrade head를 실행하면 CommandError로 실패한다
    with pytest.raises(CommandError):
        await when_operator_upgrades(blank_database)
    # then: 테이블은 alembic_version 하나뿐이고 버전은 그대로다
    assert await table_names(blank_database) == {"alembic_version"}
    await then_schema_is_at(blank_database, "f2b7c9e4a615")


async def test_downgrade_base_at_head_is_refused_without_changes(blank_database: URL) -> None:
    """최초 리비전을 base로 내리려 하면 거부되고 스키마가 그대로 남는다.

    테스트 코드: SC-010
    """
    # given: head까지 올린 DB와 테이블 목록 기록
    await when_operator_upgrades(blank_database)
    tables_before = await table_names(blank_database)
    # when: downgrade base를 실행한다
    outcome = await when_operator_attempts_downgrade(blank_database, target="base")
    # then: 안내 문구와 함께 중단되고 버전·테이블 목록이 그대로다
    then_command_aborted(outcome, "최초 리비전", "DB를 새로 만드세요")
    await then_schema_is_at(blank_database, BASELINE)
    assert await table_names(blank_database) == tables_before
