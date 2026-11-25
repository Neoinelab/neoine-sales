"""AD 바인드 컬럼 리비전(c5e9a2f7d104, 순수 expand): 두 컬럼의 NOT NULL만 풀고 값을 보존한다.

부모(b3a8d1f6c527)까지 올린 DB에 예전 바인드 값이 든 행을 넣고 head로 올려 값·행 수·컬럼 형식을
보고, NULL 행이 있으면 downgrade가 지우지 않고 중단하는지 본다(SC-R27). 실제 PostgreSQL이 필요하다.
"""

from typing import TYPE_CHECKING

import pytest

from tests.support.raw_sql import run_sql
from tests.support.schema_catalog import (
    then_command_aborted,
    then_schema_is_at,
    when_operator_attempts_downgrade,
    when_operator_upgrades,
)

if TYPE_CHECKING:
    from sqlalchemy.engine import URL

pytestmark = pytest.mark.integration

PARENT = "c9f2a6b8d401"  # 계약 날짜 리비전(부모 b3a8d1f6c527)
HEAD = "c5e9a2f7d104"
INSERT_ROW = (
    "insert into directory_settings (id, revision, host, port, security, bind_account,"
    " bind_password_encrypted, base_dn, user_filter, connect_timeout_seconds, updated_at)"
    " values (1, 1, 'dc1.corp.test', 636, 'ssl', :account, :token, 'dc=corp,dc=test',"
    " '(sAMAccountName={login_id})', 5, now())"
)
ROW = (
    "select id, revision, host, port, security, bind_account, bind_password_encrypted, base_dn,"
    " user_filter, connect_timeout_seconds, updated_at, updated_by_user_id from directory_settings"
)
COUNT = "select count(*) from directory_settings"
COLUMNS = (
    "select column_name, is_nullable, data_type, character_maximum_length"
    " from information_schema.columns where table_schema = 'public'"
    " and table_name = 'directory_settings'"
    " and column_name in ('bind_account', 'bind_password_encrypted') order by column_name"
)
NULLABLE = (
    "select column_name, is_nullable from information_schema.columns"
    " where table_schema = 'public' and table_name = 'directory_settings'"
    " and column_name in ('bind_account', 'bind_password_encrypted') order by column_name"
)


async def test_upgrade_keeps_an_old_row_value_for_value_and_makes_the_two_columns_nullable(
    blank_database: URL,
) -> None:
    """바인드 값이 있는 AD 설정 행은 upgrade 뒤에도 값이 그대로이고 두 컬럼은 NULL 허용이다.

    테스트 코드: SC-063
    """
    # given: 부모 리비전까지 올린 빈 DB에 바인드 계정 CN=svc,DC=x·암호문 OLD-TOKEN인 행 1개
    await when_operator_upgrades(blank_database, target=PARENT)
    await run_sql(blank_database, INSERT_ROW, {"account": "CN=svc,DC=x", "token": "OLD-TOKEN"})
    before = await run_sql(blank_database, ROW)
    columns_before = await run_sql(blank_database, COLUMNS)
    assert [row[1] for row in columns_before] == ["NO", "NO"]

    # when: head까지 올린다
    await when_operator_upgrades(blank_database, target=HEAD)

    # then: 행 수는 1이고 모든 컬럼 값이 같다
    await then_schema_is_at(blank_database, HEAD)
    assert await run_sql(blank_database, COUNT) == [(1,)]
    assert await run_sql(blank_database, ROW) == before
    # then: 두 컬럼은 NULL 허용이고 형식은 그대로(character varying(256)·text)다
    columns_after = await run_sql(blank_database, COLUMNS)
    assert [(r[0], r[1]) for r in columns_after] == [
        ("bind_account", "YES"),
        ("bind_password_encrypted", "YES"),
    ]
    assert [tuple(r[2:]) for r in columns_after] == [
        (r[2], r[3]) for r in columns_before
    ]  # 타입·길이 불변


async def test_downgrade_refuses_when_a_row_has_null_bind_values_and_deletes_nothing(
    blank_database: URL,
) -> None:
    """바인드 컬럼이 NULL인 행이 있으면 downgrade는 지우지 않고 중단한다.

    테스트 코드: SC-064
    """
    # given: head까지 올린 DB에 두 바인드 컬럼이 NULL인 AD 설정 행 1개
    await when_operator_upgrades(blank_database, target=HEAD)
    await run_sql(blank_database, INSERT_ROW, {"account": None, "token": None})
    before = await run_sql(blank_database, ROW)

    # when: downgrade -1을 시도한다
    outcome = await when_operator_attempts_downgrade(blank_database, target=PARENT)

    # then: RuntimeError이고 문구에 건수 "1건"과 "행은 삭제하지 않음"이 있다
    then_command_aborted(outcome, "1건", "행은 삭제하지 않음")
    assert isinstance(outcome.error, RuntimeError)
    # then: 행은 그대로이고 버전은 head이며 두 컬럼은 여전히 NULL 허용이다
    assert await run_sql(blank_database, ROW) == before
    await then_schema_is_at(blank_database, HEAD)
    assert [tuple(r) for r in await run_sql(blank_database, NULLABLE)] == [
        ("bind_account", "YES"),
        ("bind_password_encrypted", "YES"),
    ]


@pytest.mark.parametrize("with_row", [False, True], ids=["no-row", "row-with-values"])
async def test_downgrade_succeeds_when_no_row_has_null_bind_values(
    blank_database: URL, *, with_row: bool
) -> None:
    """행이 없거나 두 값이 모두 있으면 downgrade -1이 성공해 두 컬럼이 다시 NOT NULL이 된다.

    테스트 코드: SC-064
    """
    # given: head까지 올린 DB(행 없음 또는 두 값이 모두 있는 행)
    await when_operator_upgrades(blank_database, target=HEAD)
    if with_row:
        await run_sql(blank_database, INSERT_ROW, {"account": "CN=svc,DC=x", "token": "OLD-TOKEN"})
    before = await run_sql(blank_database, ROW)

    # when: downgrade -1을 실행한다
    outcome = await when_operator_attempts_downgrade(blank_database, target=PARENT)

    # then: 성공하고 버전은 부모이며 두 컬럼은 NOT NULL이고 행은 그대로다
    assert outcome.error is None
    await then_schema_is_at(blank_database, PARENT)
    assert [tuple(r) for r in await run_sql(blank_database, NULLABLE)] == [
        ("bind_account", "NO"),
        ("bind_password_encrypted", "NO"),
    ]
    assert await run_sql(blank_database, ROW) == before
