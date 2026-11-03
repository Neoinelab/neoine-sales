"""Feature: 운영자는 개발 로그인 사용자 삭제 리비전을 올려 dev 세 계정과 그 참조 데이터를 지운다.

When: 운영자 명령(alembic upgrade). 대상은 `dev-admin`·`dev-sales`·`dev-user`(대소문자 무시) 세
아이디뿐이다. 그 사용자 행과 참조하는 모든 데이터(담당 Deal과 하위 행, 활동·이력, 첨부,
리포트, 파트너
미팅, 세션, 비밀번호 해시, Action 유형·BANT Label과 그것을 쓰는 다른 사용자의 행, 스냅숏 셀, 그
사용자가 등록한 단일 행 설정)를 한 트랜잭션에서 자식 -> 부모 순서로 지운다. 그 밖의 사용자(`dev-ops`
같은 다른 dev- 아이디 포함)의 데이터는 그대로다. dev가 등록한 일반 사용자는 남고 created_by가 자기
자신이 된다. 지운 첨부는 WARNING 로그로 알린다.
세 아이디 행이 없는 DB(product)에서는 아무것도 바꾸지 않는다.
downgrade는 항상 거부한다(복구는 백업 복원뿐).
"""

import logging
from typing import TYPE_CHECKING

import pytest
from sqlalchemy import text

from tests.functional.steps.schema import (
    given_rows,
    given_schema_at,
    then_command_aborted,
    then_schema_is_at,
    when_operator_attempts_downgrade,
    when_operator_upgrades,
)
from tests.support.alert_rows import insert_alert_settings
from tests.support.attachment_rows import insert_attachment, insert_storage_settings
from tests.support.directory_rows import insert_password_hash, insert_settings
from tests.support.forecast_rows import insert_cell, insert_column, insert_snapshot
from tests.support.head_rows import (
    insert_action,
    insert_bant,
    insert_contact,
    insert_deal,
    insert_history,
    insert_partner_link,
    insert_user,
)
from tests.support.ids import new_id
from tests.support.partner_meeting_rows import insert_meeting
from tests.support.report_rows import insert_report
from tests.support.revisions import partner_meetings_drop_deal_revision, retire_dev_users_revision
from tests.support.user_fk_migration import run_sql

if TYPE_CHECKING:
    from sqlalchemy.engine import URL
    from sqlalchemy.ext.asyncio import AsyncSession

pytestmark = pytest.mark.integration

INSERT_SESSION = (
    "insert into auth_sessions (token_hash, user_id, name, role, created_at, expires_at)"
    " values (:token_hash, :user_id, 'n', 'sales', now(), now() + interval '8 hours')"
)
DEV_DEAL = "20261101-D001"
KIM_DEAL = "20261101-K001"
SEALED = "gAAAAA-sealed-dummy"
# 사용자를 가리키는 데이터 표와 그 행 수를 센다(dev 쪽은 0, 일반 사용자 쪽은 그대로여야 한다)
COUNTS = {
    "users": "select count(*) from users",
    "deals": "select count(*) from deals",
    "deal_actions": "select count(*) from deal_actions",
    "deal_history": "select count(*) from deal_history",
    "deal_partners": "select count(*) from deal_partners",
    "reports": "select count(*) from reports",
    "partner_meetings": "select count(*) from partner_meetings",
    "auth_sessions": "select count(*) from auth_sessions",
    "user_password_hashes": "select count(*) from user_password_hashes",
}


async def _seed(session: AsyncSession) -> None:
    """dev-admin·dev-sales·kim 모두 데이터가 있고 dev 데이터 일부는 kim의 Deal에도 닿는다."""
    customer = await insert_contact(session)
    partner = await insert_contact(session, kind="partner", company="한빛")
    kim = await insert_user(session, "kim")
    dev_admin = await insert_user(session, "dev-admin", role="admin")
    dev_sales = await insert_user(session, "dev-sales")
    await insert_deal(session, customer, owner_user_id=dev_admin, code=DEV_DEAL)
    await insert_deal(session, customer, owner_user_id=kim, code=KIM_DEAL)
    await insert_partner_link(session, DEV_DEAL, partner)
    await insert_history(session, DEV_DEAL, dev_admin)
    await insert_history(session, KIM_DEAL, kim)
    await insert_history(session, KIM_DEAL, dev_sales)  # kim의 Deal에 dev 사용자가 남긴 이력
    await insert_action(session, DEV_DEAL, dev_admin)
    await insert_action(session, KIM_DEAL, kim)
    await insert_action(session, KIM_DEAL, dev_sales)  # kim의 Deal에 dev 사용자가 한 활동
    await insert_report(session, dev_admin, name="dev 리포트")
    await insert_report(session, kim, name="kim 리포트")
    await insert_meeting(session, dev_sales)
    await insert_meeting(session, kim, partner_company="Acme")
    for user_id, token in ((dev_admin, "t1"), (dev_sales, "t2"), (kim, "t3")):
        await session.execute(text(INSERT_SESSION), {"token_hash": token * 32, "user_id": user_id})
        await insert_password_hash(session, user_id)


async def _counts(url: URL) -> dict[str, int]:
    return {name: int((await run_sql(url, sql))[0][0]) for name, sql in COUNTS.items()}


async def _logins(url: URL) -> list[str]:
    return [str(r[0]) for r in await run_sql(url, "select login_id from users order by login_id")]


async def test_upgrade_deletes_dev_users_and_everything_that_references_them(
    blank_database: URL,
) -> None:
    """Scenario: 올리면 개발용 세 아이디와 참조 데이터가 0건이 되고 kim의 데이터는 그대로다."""
    # Given
    await given_schema_at(blank_database, partner_meetings_drop_deal_revision())
    await given_rows(blank_database, _seed)
    # When
    await when_operator_upgrades(blank_database)
    # Then
    await then_schema_is_at(blank_database, retire_dev_users_revision())
    assert await _logins(blank_database) == ["kim"]
    assert await _counts(blank_database) == {
        "users": 1,
        "deals": 1,  # kim의 Deal만 남는다
        "deal_actions": 1,  # kim의 활동만
        "deal_history": 1,  # kim의 이력만
        "deal_partners": 0,  # dev Deal의 파트너 링크는 Deal과 함께
        "reports": 1,
        "partner_meetings": 1,
        "auth_sessions": 1,
        "user_password_hashes": 1,
    }
    assert await run_sql(blank_database, "select deal_code from deals") == [(KIM_DEAL,)]
    assert await run_sql(blank_database, "select name from reports") == [("kim 리포트",)]
    assert await run_sql(blank_database, "select partner_company from partner_meetings") == [
        ("Acme",)
    ]


async def test_upgrade_deletes_settings_registered_by_a_dev_user_and_keeps_others(
    blank_database: URL,
) -> None:
    """Scenario: dev 사용자가 등록한 단일 행 설정은 지워지고 일반 사용자가 등록한 설정은 남는다."""

    async def seed(session: AsyncSession) -> None:
        dev = await insert_user(session, "dev-admin", role="admin")
        kim = await insert_user(session, "kim", role="admin")
        await insert_settings(session)
        await session.execute(
            text("update directory_settings set updated_by_user_id = :u"), {"u": dev}
        )
        await session.execute(
            text(
                "insert into storage_settings (id, path, updated_at, updated_by_user_id)"
                " values (1, '/data/files', now(), :u)"
            ),
            {"u": kim},
        )

    # Given
    await given_schema_at(blank_database, partner_meetings_drop_deal_revision())
    await given_rows(blank_database, seed)
    # When
    await when_operator_upgrades(blank_database)
    # Then
    assert await run_sql(blank_database, "select count(*) from directory_settings") == [(0,)]
    assert await run_sql(blank_database, "select path from storage_settings") == [("/data/files",)]
    assert await _logins(blank_database) == ["kim"]


async def test_upgrade_changes_nothing_without_dev_rows(blank_database: URL) -> None:
    """Scenario: 개발용 세 아이디 행이 없는 DB(product)에서는 어떤 표의 행도 바뀌지 않는다."""

    # Given
    await given_schema_at(blank_database, partner_meetings_drop_deal_revision())
    await given_rows(blank_database, _seed_without_dev)
    before = await _counts(blank_database)
    deals_before = await run_sql(blank_database, "select deal_code, owner_user_id from deals")
    # When
    await when_operator_upgrades(blank_database)
    # Then
    assert await _counts(blank_database) == before
    assert await run_sql(blank_database, "select deal_code, owner_user_id from deals") == (
        deals_before
    )
    await then_schema_is_at(blank_database, retire_dev_users_revision())


async def test_upgrade_of_an_empty_database_succeeds(blank_database: URL) -> None:
    """Scenario: 빈 DB를 head까지 올려도 성공하고 head는 이 리비전이다."""
    # Given
    # (마이그레이션이 하나도 적용되지 않은 빈 DB)
    # When
    await when_operator_upgrades(blank_database)
    # Then
    await then_schema_is_at(blank_database, retire_dev_users_revision())
    assert (await _counts(blank_database))["users"] == 0


async def test_a_lookalike_login_id_is_not_deleted(blank_database: URL) -> None:
    """Scenario: 세 아이디가 아닌 아이디(다른 dev- 아이디 포함)는 지워지지 않는다."""

    async def seed(session: AsyncSession) -> None:
        for login in ("devops", "xdev-admin", "dev", "dev-ops", "dev-qa", "dev-admin2"):
            await insert_user(session, login)
        await insert_user(session, "dev-user")  # 이것만 지워진다

    # Given
    await given_schema_at(blank_database, partner_meetings_drop_deal_revision())
    await given_rows(blank_database, seed)
    # When
    await when_operator_upgrades(blank_database)
    # Then
    assert await _logins(blank_database) == [
        "dev",
        "dev-admin2",
        "dev-ops",
        "dev-qa",
        "devops",
        "xdev-admin",
    ]


async def test_upgrade_matches_the_three_ids_ignoring_case(blank_database: URL) -> None:
    """Scenario: 대문자·혼합 표기의 세 아이디도 지워진다."""

    async def seed(session: AsyncSession) -> None:
        for login in ("DEV-ADMIN", "Dev-Sales", "dEv-UsEr", "kim"):
            await insert_user(session, login)

    # Given
    await given_schema_at(blank_database, partner_meetings_drop_deal_revision())
    await given_rows(blank_database, seed)
    # When
    await when_operator_upgrades(blank_database)
    # Then
    assert await _logins(blank_database) == ["kim"]


async def test_upgrade_keeps_another_dev_prefixed_user_and_all_of_its_data(
    blank_database: URL,
) -> None:
    """Scenario: dev-ops와 그 데이터(Deal·활동·이력·리포트·미팅·세션·해시)는 그대로 남는다."""

    async def seed(session: AsyncSession) -> None:
        customer = await insert_contact(session)
        ops = await insert_user(session, "dev-ops")
        await insert_user(session, "dev-admin", role="admin")
        await insert_deal(session, customer, owner_user_id=ops, code=KIM_DEAL)
        await insert_history(session, KIM_DEAL, ops)
        await insert_action(session, KIM_DEAL, ops)
        await insert_report(session, ops, name="ops 리포트")
        await insert_meeting(session, ops)
        await session.execute(text(INSERT_SESSION), {"token_hash": "o" * 64, "user_id": ops})
        await insert_password_hash(session, ops)

    # Given
    await given_schema_at(blank_database, partner_meetings_drop_deal_revision())
    await given_rows(blank_database, seed)
    # When
    await when_operator_upgrades(blank_database)
    # Then
    assert await _logins(blank_database) == ["dev-ops"]
    assert await _counts(blank_database) == {
        "users": 1,
        "deals": 1,
        "deal_actions": 1,
        "deal_history": 1,
        "deal_partners": 0,
        "reports": 1,
        "partner_meetings": 1,
        "auth_sessions": 1,
        "user_password_hashes": 1,
    }


async def _insert_type(session: AsyncSession, name: str, created_by: int) -> None:
    await session.execute(
        text(
            "insert into action_types (id, name, is_default, default_order, created_by_user_id,"
            " created_at, updated_at) values (:id, :name, false, null, :u, now(), now())"
        ),
        {"id": new_id(), "name": name, "u": created_by},
    )


async def _insert_label(
    session: AsyncSession, name: str, created_by: int, category: str = "need"
) -> int:
    label_id = new_id()
    await session.execute(
        text(
            "insert into bant_labels (id, category, name, is_default, default_order,"
            " created_by_user_id, created_at, updated_at)"
            " values (:id, :category, :name, false, null, :u, now(), now())"
        ),
        {"id": label_id, "category": category, "name": name, "u": created_by},
    )
    return label_id


async def test_upgrade_deletes_dev_catalog_entries_and_other_users_rows_that_use_them(
    blank_database: URL,
) -> None:
    """Scenario: dev가 만든 유형·Label과 그것을 쓰는 kim의 Action·BANT 선택이 지워진다."""

    async def seed(session: AsyncSession) -> None:
        customer = await insert_contact(session)
        kim = await insert_user(session, "kim")
        dev = await insert_user(session, "dev-admin", role="admin")
        await _insert_type(session, "dev 유형", dev)
        await _insert_type(session, "kim 유형", kim)
        dev_label = await _insert_label(session, "dev 라벨", dev)
        kim_label = await _insert_label(session, "kim 라벨", kim, "budget")
        await insert_deal(session, customer, owner_user_id=kim, code=KIM_DEAL)
        await insert_action(session, KIM_DEAL, kim, type_name="dev 유형")
        await insert_action(session, KIM_DEAL, kim, type_name="kim 유형")
        await insert_bant(session, KIM_DEAL, "need", dev_label)
        await insert_bant(session, KIM_DEAL, "budget", kim_label)

    # Given
    await given_schema_at(blank_database, partner_meetings_drop_deal_revision())
    await given_rows(blank_database, seed)
    defaults_before = await run_sql(
        blank_database, "select count(*) from action_types where created_by_user_id is null"
    )
    # When
    await when_operator_upgrades(blank_database)
    # Then
    types = await run_sql(
        blank_database, "select name from action_types where created_by_user_id is not null"
    )
    assert types == [("kim 유형",)]
    assert await run_sql(
        blank_database, "select name from bant_labels where created_by_user_id is not null"
    ) == [("kim 라벨",)]
    assert await run_sql(
        blank_database,
        "select t.name from deal_actions a join action_types t on t.id = a.action_type_id",
    ) == [("kim 유형",)]
    assert await run_sql(
        blank_database,
        "select l.name from deal_bant_labels b join bant_labels l on l.id = b.label_id",
    ) == [("kim 라벨",)]
    assert await run_sql(blank_database, "select count(*) from deals") == [(1,)]
    assert (
        await run_sql(
            blank_database, "select count(*) from action_types where created_by_user_id is null"
        )
        == defaults_before
    )


async def test_upgrade_keeps_a_user_registered_by_dev_and_points_created_by_at_itself(
    blank_database: URL,
) -> None:
    """Scenario: dev가 등록한 kim은 남고 created_by_user_id가 kim 자신이 된다."""

    async def seed(session: AsyncSession) -> None:
        dev = await insert_user(session, "dev-admin", role="admin")
        await insert_user(session, "kim", created_by_user_id=dev)

    # Given
    await given_schema_at(blank_database, partner_meetings_drop_deal_revision())
    await given_rows(blank_database, seed)
    # When
    await when_operator_upgrades(blank_database)
    # Then
    assert await run_sql(blank_database, "select login_id, created_by_user_id = id from users") == [
        ("kim", True)
    ]


async def test_upgrade_deletes_snapshot_cells_of_dev_owners_only(blank_database: URL) -> None:
    """Scenario: 스냅숏 셀 중 dev 담당자의 셀만 지워지고 kim의 셀은 남는다."""

    async def seed(session: AsyncSession) -> None:
        kim = await insert_user(session, "kim")
        dev = await insert_user(session, "dev-sales")
        snapshot = await insert_snapshot(session)
        await insert_column(session, snapshot)
        await insert_cell(session, snapshot, dev, amount=111)
        await insert_cell(session, snapshot, kim, amount=222)

    # Given
    await given_schema_at(blank_database, partner_meetings_drop_deal_revision())
    await given_rows(blank_database, seed)
    # When
    await when_operator_upgrades(blank_database)
    # Then
    assert await run_sql(blank_database, "select amount from forecast_snapshot_cells") == [(222,)]


@pytest.mark.parametrize(("editor", "expected"), [("dev-admin", 0), ("kim", 1)])
async def test_upgrade_deletes_alert_settings_saved_by_dev_only(
    blank_database: URL, editor: str, expected: int
) -> None:
    """Scenario: 경고 기준은 dev가 저장했으면 지워지고 kim이 저장했으면 남는다."""

    async def seed(session: AsyncSession) -> None:
        await insert_user(session, "dev-sales")  # 삭제 대상이 하나는 있어야 동작한다
        saver = await insert_user(session, editor, role="admin")
        await insert_alert_settings(session, saver)

    # Given
    await given_schema_at(blank_database, partner_meetings_drop_deal_revision())
    await given_rows(blank_database, seed)
    # When
    await when_operator_upgrades(blank_database)
    # Then
    assert await run_sql(blank_database, "select count(*) from alert_settings") == [(expected,)]


async def test_upgrade_deletes_a_storage_setting_registered_by_dev(blank_database: URL) -> None:
    """Scenario: dev가 등록한 저장 위치 행은 지워진다."""

    async def seed(session: AsyncSession) -> None:
        dev = await insert_user(session, "dev-user")
        await insert_storage_settings(session, updated_by=dev)

    # Given
    await given_schema_at(blank_database, partner_meetings_drop_deal_revision())
    await given_rows(blank_database, seed)
    # When
    await when_operator_upgrades(blank_database)
    # Then
    assert await run_sql(blank_database, "select count(*) from storage_settings") == [(0,)]


async def test_upgrade_deletes_dev_attachments_and_warns_with_the_path_and_keys(
    blank_database: URL, caplog: pytest.LogCaptureFixture
) -> None:
    """Scenario: dev가 올린 첨부 메타는 지워지고 WARNING에 저장 경로와 storage_key가 남는다."""

    async def seed(session: AsyncSession) -> None:
        customer = await insert_contact(session)
        kim = await insert_user(session, "kim")
        dev = await insert_user(session, "dev-sales")
        await insert_storage_settings(session, path="/data/files", updated_by=kim)
        await insert_settings(session, bind_password_encrypted=SEALED)
        await insert_deal(session, customer, owner_user_id=kim, code=KIM_DEAL)
        await insert_attachment(session, KIM_DEAL, dev, storage_key="devkey" + "a" * 26)
        await insert_attachment(session, KIM_DEAL, kim, storage_key="kimkey" + "b" * 26)

    # Given
    await given_schema_at(blank_database, partner_meetings_drop_deal_revision())
    await given_rows(blank_database, seed)
    # When
    with caplog.at_level(logging.WARNING):
        await when_operator_upgrades(blank_database)
    # Then
    assert await run_sql(blank_database, "select storage_key from deal_attachments") == [
        ("kimkey" + "b" * 26,)
    ]
    warnings = " ".join(r.getMessage() for r in caplog.records if r.levelno >= logging.WARNING)
    assert "/data/files" in warnings
    assert "devkey" + "a" * 26 in warnings
    assert "kimkey" not in warnings
    assert "gAAAAA" not in warnings


async def test_downgrade_is_always_refused(blank_database: URL) -> None:
    """Scenario: 내리기는 RuntimeError로 거부되고 스키마는 그대로다(복구는 백업 복원뿐)."""
    # Given
    await when_operator_upgrades(blank_database)
    # When
    outcome = await when_operator_attempts_downgrade(
        blank_database, target=partner_meetings_drop_deal_revision()
    )
    # Then
    then_command_aborted(outcome)
    await then_schema_is_at(blank_database, retire_dev_users_revision())


async def _seed_without_dev(session: AsyncSession) -> None:
    customer = await insert_contact(session)
    kim = await insert_user(session, "kim")
    await insert_deal(session, customer, owner_user_id=kim, code=KIM_DEAL)
    await insert_history(session, KIM_DEAL, kim)
    await insert_action(session, KIM_DEAL, kim)
    await insert_report(session, kim)
    await insert_meeting(session, kim)
    await session.execute(text(INSERT_SESSION), {"token_hash": "a" * 64, "user_id": kim})
    await insert_password_hash(session, kim)
