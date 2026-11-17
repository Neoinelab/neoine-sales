"""Deal Comment 리비전: Memo를 Comment로 옮긴 뒤 deal_actions.memo를 없애고, 되돌린다.

Product 이름 변경 리비전(a9d3f5c7e214)까지 올린 스키마에 Action 행을 넣은 뒤 head로 올려, Memo가
있는 Action마다 Comment가 같은 값·작성자·시각으로 생기는지, 건수 점검이 실패하면 아무것도
바뀌지 않는지, downgrade가 memo를 다시 채우는지 확인한다. 실제 PostgreSQL이 필요하다.
(리비전 그래프·upgrade 본문 검사는 DB가 필요 없어 test_revision_graph.py에 있다. 리비전 id는
그래프에서 읽는다.)

복사 INSERT는 `op.execute`로 실행되어야 한다(건수 점검 실패 시험이 그 호출을 가로챈다).
"""

from datetime import UTC, datetime
from typing import TYPE_CHECKING, Any

import pytest

from tests.support.raw_sql import run_sql
from tests.support.schema_catalog import (
    head_revision,
    then_schema_is_at,
    when_operator_attempts_downgrade,
    when_operator_upgrades,
)

if TYPE_CHECKING:
    from sqlalchemy.engine import URL

pytestmark = pytest.mark.integration

PARENT = "a9d3f5c7e214"
HEAD = head_revision()
C1 = datetime(2026, 11, 10, 9, 0, tzinfo=UTC)
U1 = datetime(2026, 11, 12, 15, 30, tzinfo=UTC)

INSERT_USERS = (
    "insert into users (id, login_id, role, created_at, updated_at) values"
    " (1, 'kim', 'sales', now(), now()), (2, 'park', 'sales', now(), now())"
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
    " procurement, product, created_at, updated_at, status_changed_on) values (:id, :code, 'n',"
    " 1, 1, 10, 'status', 'prospecting', 'forecast', 'pipeline', 100, current_date, 1,"
    " '', 'p', now(), now(), current_date)"
)
INSERT_ACTION = (
    "insert into deal_actions (id, deal_id, action_type_id, action, memo, next_action,"
    " due_date, acted_on, actor_user_id, status_key, forecast_key, next_action_status,"
    " created_at, updated_at) values (:id, :deal_id,"
    " (select id from action_types where name = '미팅'), 'a', :memo, 'n', current_date,"
    " current_date, :actor, 'prospecting', 'pipeline', 'open', :created_at, :updated_at)"
)
INSERT_HISTORY = (
    "insert into deal_history (deal_id, changed_at, changed_by_user_id, category, target,"
    " before_text, after_text) values (1, now(), 1, 'action', 'Action', '', '등록')"
)
ACTION_ROWS = "select id, deal_id, actor_user_id, action, next_action from deal_actions order by id"
COMMENTS = (
    "select deal_id, action_id, author_user_id, body, created_at, updated_at"
    " from deal_comments order by action_id, id"
)
HAS_MEMO = (
    "select count(*) from information_schema.columns where table_schema = 'public'"
    " and table_name = 'deal_actions' and column_name = 'memo'"
)
MEMO_INFO = (
    "select is_nullable, column_default from information_schema.columns"
    " where table_schema = 'public' and table_name = 'deal_actions' and column_name = 'memo'"
)
HAS_COMMENTS_TABLE = "select to_regclass('public.deal_comments') is not null"
UNIQUE_ID_DEAL = (
    "select count(*) from pg_constraint where conrelid = 'deal_actions'::regclass"
    " and conname = 'uq_deal_actions_id'"
)
MEMOS = "select id, memo from deal_actions order by id"


async def _seed_parent(
    url: URL, actions: list[tuple[int, str, int, datetime, datetime]], *, deals: int = 1
) -> None:
    """부모 리비전까지 올리고 Deal·(id, memo, 작성자, 작성 시각, 수정 시각) Action들을 넣는다."""
    await when_operator_upgrades(url, target=PARENT)
    await run_sql(url, INSERT_USERS)
    await run_sql(url, INSERT_CONTACT)
    await run_sql(url, INSERT_VENDOR)
    for number in range(1, deals + 1):
        await run_sql(url, INSERT_DEAL, {"id": number, "code": f"20261117-A00{number}"})
    for action_id, memo, actor, created, updated in actions:
        params: dict[str, Any] = {
            "id": action_id,
            "deal_id": 1,
            "memo": memo,
            "actor": actor,
            "created_at": created,
            "updated_at": updated,
        }
        await run_sql(url, INSERT_ACTION, params)


async def test_upgrade_copies_each_memo_into_an_action_comment_and_drops_the_column(
    blank_database: URL,
) -> None:
    """upgrade는 Memo가 있는 Action마다 같은 값·작성자·시각의 Action Comment를 만든 뒤 memo를
    없애고 Action 행 수는 그대로다.

    테스트 코드: CM-042
    """
    # given: 부모 리비전 스키마에 Memo가 있는 X(KIM)·빈 Y·5,000자 Z(PARK)
    long_memo = "가" * 5_000
    await _seed_parent(
        blank_database,
        [
            (1, "요구사항 정리", 1, C1, U1),
            (2, "", 2, C1, U1),
            (3, long_memo, 2, C1, U1),
        ],
    )
    actions_before = await run_sql(blank_database, ACTION_ROWS)

    # when: head까지 올린다
    await when_operator_upgrades(blank_database)

    # then: 버전은 head이고 Comment는 X·Z 2행이며 값·작성자·시각이 Action의 것 그대로다
    await then_schema_is_at(blank_database, HEAD)
    comments = await run_sql(blank_database, COMMENTS)
    assert [tuple(row) for row in comments] == [
        (1, 1, 1, "요구사항 정리", C1, U1),
        (1, 3, 2, long_memo, C1, U1),
    ]
    # then: Action 행 수와 나머지 값은 그대로이고 memo 컬럼이 없다
    assert await run_sql(blank_database, ACTION_ROWS) == actions_before
    assert len(actions_before) == 3
    assert await run_sql(blank_database, HAS_MEMO) == [(0,)]
    assert await run_sql(blank_database, UNIQUE_ID_DEAL) == [(1,)]


async def test_upgrade_keeps_multiline_memos_whole_skips_blank_ones_and_writes_no_history(
    blank_database: URL,
) -> None:
    """upgrade는 여러 줄 Memo를 나누지 않고 빈 Memo는 옮기지 않으며 이력을 만들지 않는다.

    테스트 코드: CM-043
    """
    # given: 여러 줄 Memo의 Action M, 빈 Memo(공백 포함 아님)의 Action W, 이력 1행
    await _seed_parent(
        blank_database,
        [(1, "기존\n전달 완료", 1, C1, U1), (2, "", 1, C1, U1)],
    )
    await run_sql(blank_database, INSERT_HISTORY)

    # when: head까지 올린다
    await when_operator_upgrades(blank_database)

    # then: M의 Comment는 본문 "기존\n전달 완료" 1건이고 W는 Comment가 없다
    comments = await run_sql(blank_database, COMMENTS)
    assert [(row[1], row[3]) for row in comments] == [(1, "기존\n전달 완료")]
    # then: 이력은 1행 그대로다
    assert await run_sql(blank_database, "select count(*) from deal_history") == [(1,)]


async def test_upgrade_aborts_without_any_change_when_the_copy_count_is_wrong(
    blank_database: URL, monkeypatch: pytest.MonkeyPatch
) -> None:
    """복사된 건수가 Memo가 있는 Action 수와 다르면 upgrade가 중단되고 memo 컬럼·Action 행·
    Comment가 upgrade 전 그대로다.

    테스트 코드: CM-047
    """
    # given: Memo가 있는 Action 둘, 그리고 복사 INSERT 직후 한 행이 사라지게 하는 가로채기
    import alembic.op as alembic_op  # noqa: PLC0415 - 가로챌 때만 쓴다

    await _seed_parent(blank_database, [(1, "첫째", 1, C1, U1), (2, "둘째", 2, C1, U1)])
    memos_before = await run_sql(blank_database, MEMOS)
    original = alembic_op.execute

    def execute_dropping_one_copied_row(statement: Any, *args: Any, **kwargs: Any) -> Any:  # noqa: ANN401
        result = original(statement, *args, **kwargs)
        if "insert into deal_comments" in str(statement).lower():
            original("delete from deal_comments where id = (select min(id) from deal_comments)")
        return result

    monkeypatch.setattr(alembic_op, "execute", execute_dropping_one_copied_row)

    # when: head까지 올리면 RuntimeError로 중단된다
    with pytest.raises(RuntimeError) as aborted:
        await when_operator_upgrades(blank_database)

    # then: 문구에 넣은 수와 대상 수가 들어 있다
    assert str(aborted.value) == (
        "Memo를 Comment로 옮긴 건수(1)가 Memo가 있는 Action 수(2)와 다릅니다."
    )
    # then: 버전은 부모 그대로, memo 컬럼과 값이 그대로, Comment 테이블은 없다
    await then_schema_is_at(blank_database, PARENT)
    assert await run_sql(blank_database, HAS_MEMO) == [(1,)]
    assert await run_sql(blank_database, MEMOS) == memos_before
    assert await run_sql(blank_database, HAS_COMMENTS_TABLE) == [(False,)]
    assert await run_sql(blank_database, UNIQUE_ID_DEAL) == [(0,)]


async def test_downgrade_refills_memo_from_the_action_comments_and_loses_deal_comments(
    blank_database: URL,
) -> None:
    """downgrade는 memo를 Action Comment로 다시 채우고 Deal Comment는 소실된다.

    테스트 코드: CM-044
    """
    # given: Memo "요구사항 정리"를 옮긴 X, Comment 없는 Y, upgrade 뒤 X에 쓴 Comment "추가"와
    #   Deal Comment 1건이 있는 head DB
    await _seed_parent(blank_database, [(1, "요구사항 정리", 1, C1, U1), (2, "", 2, C1, U1)])
    await when_operator_upgrades(blank_database)
    later = datetime(2026, 11, 17, 9, 0, tzinfo=UTC)
    await run_sql(
        blank_database,
        "insert into deal_comments (id, deal_id, action_id, author_user_id, body, created_at,"
        " updated_at) values (900, 1, 1, 2, '추가', :at, :at),"
        " (901, 1, null, 1, '딜 글', :at, :at)",
        {"at": later},
    )
    actions_before = await run_sql(blank_database, ACTION_ROWS)

    # when: Comment 리비전의 부모까지(읽음 리비전과 Comment 리비전을) 되돌린다
    outcome = await when_operator_attempts_downgrade(blank_database, target=PARENT)

    # then: 중단되지 않고 버전이 부모이며 memo는 NOT NULL·서버 기본값 없음이다
    assert outcome.error is None
    await then_schema_is_at(blank_database, PARENT)
    assert await run_sql(blank_database, MEMO_INFO) == [("NO", None)]
    # then: X는 옮긴 Memo와 새 Comment를 줄바꿈으로 이은 값, Y는 ""다
    assert await run_sql(blank_database, MEMOS) == [(1, "요구사항 정리\n추가"), (2, "")]
    # then: Comment 테이블과 uq_deal_actions_id가 없고(Deal Comment 소실) Action 행은 그대로다
    assert await run_sql(blank_database, HAS_COMMENTS_TABLE) == [(False,)]
    assert await run_sql(blank_database, UNIQUE_ID_DEAL) == [(0,)]
    assert await run_sql(blank_database, ACTION_ROWS) == actions_before
