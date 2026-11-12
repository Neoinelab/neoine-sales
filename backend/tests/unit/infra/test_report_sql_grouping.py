"""Reports SQL 생성: 그룹핑·Deal당 한 번·날짜 묶음·정렬·행 수·합계 문장."""

import pytest

from tests.support.report_defs import col, cond, resolved
from tests.support.report_sql import build, compiled, sql_of

ACTION_TYPE = col("action.type", group=True)


def test_grouped_action_scope_sums_deal_numbers_once() -> None:
    """Action 행 범위 그룹핑의 Deal 금액 합계는 Deal당 한 번만 세도록 SQL이 만들어진다.

    테스트 코드: RQ-047
    """
    # when: Action 유형 그룹핑과 금액 합계의 SQL을 만든다
    sql = sql_of(resolved([ACTION_TYPE, col("deal.amount", aggregate="sum")]))

    # then: Deal별 row_number 분할과 CASE WHEN이 있다
    assert "row_number() OVER (PARTITION BY" in sql
    assert "CASE WHEN" in sql


def test_grouped_action_scope_averages_deal_numbers_once() -> None:
    """Action 행 범위 그룹핑의 Deal 숫자 평균도 Deal당 한 번 세는 CASE WHEN을 쓴다.

    테스트 코드: RQ-048
    """
    # when: Action 유형 그룹핑과 Users 평균의 SQL을 만든다
    sql = sql_of(resolved([ACTION_TYPE, col("deal.users", aggregate="avg")]))

    # then: CASE WHEN이 있다
    assert "CASE WHEN" in sql


def test_min_and_max_of_deal_numbers_need_no_once_per_deal_case() -> None:
    """Deal 숫자의 최소·최대는 Deal당 한 번 CASE가 필요 없다.

    테스트 코드: RQ-047
    """
    # when: Action 유형 그룹핑과 금액 최소·Users 최대의 SQL을 만든다
    sql = sql_of(
        resolved(
            [
                ACTION_TYPE,
                col("deal.amount", aggregate="min"),
                col("deal.users", aggregate="max"),
            ]
        )
    )

    # then: CASE WHEN이 없다
    assert "CASE WHEN" not in sql


def test_deal_scope_grouping_does_not_need_the_once_per_deal_case() -> None:
    """Deal 행 범위 그룹핑은 Deal당 한 번 CASE가 필요 없다.

    테스트 코드: RQ-047
    """
    # when: Vendor 그룹핑과 금액 합계의 SQL을 만든다
    sql = sql_of(resolved([col("deal.vendor", group=True), col("deal.amount")]))

    # then: CASE WHEN이 없다
    assert "CASE WHEN" not in sql


def test_date_quarter_format_changes_select_and_group_by() -> None:
    """날짜 분기 포맷은 SELECT와 GROUP BY를 바꾼다.

    테스트 코드: RQ-042
    """
    # when: 만기일 분기 그룹핑의 SQL을 만든다
    sql = sql_of(
        resolved([col("deal.expected_close", format="quarter", group=True), col("deal.amount")])
    )

    # then: to_char 식과 GROUP BY가 있다
    assert "to_char" in sql
    assert "GROUP BY" in sql


def test_datetime_year_format_converts_to_the_business_timezone() -> None:
    """시각 연도 포맷은 업무 시간대로 바꾼 날짜로 묶는다.

    테스트 코드: RQ-043
    """
    # when: 등록일 연도 그룹핑의 SQL을 만든다
    sql = sql_of(resolved([col("deal.created_at", format="year", group=True), col("deal.amount")]))

    # then: timezone 변환과 GROUP BY가 있다
    assert "timezone(" in sql
    assert "GROUP BY" in sql


def test_display_only_format_does_not_change_the_statement() -> None:
    """표시 전용 포맷(요일)은 SQL 문장을 바꾸지 않는다.

    테스트 코드: RQ-042
    """
    # when: ymd와 weekday 포맷의 SQL을 각각 만든다
    plain = sql_of(resolved([col("deal.expected_close", format="ymd"), col("deal.code")]))
    weekday = sql_of(resolved([col("deal.expected_close", format="weekday"), col("deal.code")]))

    # then: 두 SQL이 같다
    assert plain == weekday


def test_nulls_last_and_tie_breakers_are_appended() -> None:
    """정렬은 NULL을 맨 뒤로 두고 Deal code 순 동률 키를 붙인다.

    테스트 코드: RQ-051
    """
    # when: 이름 내림차순 정렬 SQL을 만든다
    sql = sql_of(
        resolved(
            [col("deal.name", sort="desc"), col("deal.code")],
        )
    )

    # then: NULLS LAST와 deal_code ASC가 있다
    assert "NULLS LAST" in sql
    assert "deal_code ASC" in sql


def test_action_rows_are_tie_broken_by_acted_at_and_id() -> None:
    """Action 행의 동률은 수행일시·id 순이다.

    테스트 코드: RQ-053
    """
    # when: Action 컬럼이 있는 SQL을 만든다
    sql = sql_of(resolved([col("deal.code"), col("action.action")]))

    # then: acted_at ASC와 Action id ASC가 있다
    assert "acted_at ASC" in sql
    assert "deal_actions.id ASC" in sql or "a.id ASC" in sql


def test_total_count_comes_from_the_same_statement_and_rows_are_limited() -> None:
    """총 행 수는 같은 문장의 window count이고 행은 LIMIT으로 자른다.

    테스트 코드: RQ-054
    """
    # when: 행 수 100의 SQL을 만든다
    sql = sql_of(resolved([col("deal.code")], row_limit=100))

    # then: window count와 LIMIT이 있다
    assert "count(*) OVER ()" in sql
    assert "LIMIT" in sql


def test_grouped_report_orders_by_group_columns_without_explicit_sort() -> None:
    """정렬 없는 그룹핑 리포트는 그룹 컬럼 순서로 정렬하고 Status는 코드 순서다.

    테스트 코드: RQ-052
    """
    # when: Status 그룹핑 SQL을 만든다
    sql = sql_of(resolved([col("deal.status", group=True), col("deal.code", aggregate="count")]))

    # then: ORDER BY가 있고 Status는 sort_order를 쓴다
    assert "ORDER BY" in sql
    assert "sort_order" in sql  # Status는 codes.sort_order 순서


def test_totals_statement_exists_only_for_grouped_reports() -> None:
    """합계 문장은 그룹핑 리포트에만 있다.

    테스트 코드: RQ-057
    """
    # given: 그룹핑 없는 정의와 그룹핑 정의
    from app.infra.db.report_select import build_totals_select  # noqa: PLC0415

    grouped = resolved([col("deal.vendor", group=True), col("deal.amount")])
    plain = resolved([col("deal.vendor"), col("deal.amount")])

    # when: 두 정의의 합계 문장을 만든다
    plain_totals = build_totals_select(plain)
    grouped_totals = build_totals_select(grouped)
    # then: 그룹핑 없으면 None이고 그룹핑이면 있다
    assert plain_totals is None
    assert grouped_totals is not None


def test_totals_statement_has_no_group_by_and_no_row_limit() -> None:
    """합계 문장은 GROUP BY와 LIMIT 없이 같은 조건 전체를 집계한다.

    테스트 코드: RQ-055
    """
    # given: 조건이 있는 그룹핑 정의
    from app.infra.db.report_select import build_totals_select  # noqa: PLC0415

    report = resolved(
        [col("deal.vendor", group=True), col("deal.amount")],
        [cond("deal.amount", "gt", 5)],
    )
    # when: 합계 문장을 만든다
    statement = build_totals_select(report)

    # then: GROUP BY·LIMIT이 없고 sum을 쓴다
    assert statement is not None
    sql, _ = compiled(statement)
    assert "GROUP BY" not in sql
    assert "LIMIT" not in sql
    assert "sum(" in sql.lower()


def test_totals_statement_for_action_scope_keeps_the_once_per_deal_case() -> None:
    """Action 행 범위의 합계 문장도 Deal당 한 번 CASE를 유지한다.

    테스트 코드: RQ-056
    """
    # given: Action 행 범위의 그룹핑 정의
    from app.infra.db.report_select import build_totals_select  # noqa: PLC0415

    report = resolved([ACTION_TYPE, col("deal.amount", aggregate="sum")])
    # when: 합계 문장을 만든다
    statement = build_totals_select(report)

    # then: CASE WHEN이 있다
    assert statement is not None
    assert "CASE WHEN" in compiled(statement)[0]


@pytest.mark.parametrize("limit", [100, 1000, 10000])
def test_each_row_limit_builds_a_statement(limit: int) -> None:
    """행 수 제한 100·1000·10000 모두 SQL 문장이 만들어진다.

    테스트 코드: RQ-054
    """
    # when: 행 수 제한을 준 정의의 문장을 만든다 (전제: 값 매개변수)
    statement = build(resolved([col("deal.code")], row_limit=limit))
    # then: 문장이 만들어진다
    assert statement is not None


def test_totals_statement_counts_distinct_over_the_whole_range() -> None:
    """합계 문장의 고유 건수는 전체 범위의 count distinct다.

    테스트 코드: RQ-056
    """
    # given: 담당자 고유 건수를 가진 그룹핑 정의
    from app.infra.db.report_select import build_totals_select  # noqa: PLC0415

    report = resolved(
        [col("deal.vendor", group=True), col("deal.owner", aggregate="count_distinct")]
    )
    # when: 합계 문장을 만든다
    statement = build_totals_select(report)

    # then: count(DISTINCT 식이 있고 GROUP BY가 없다
    assert statement is not None
    sql = compiled(statement)[0]
    assert "count(DISTINCT" in sql
    assert "GROUP BY" not in sql


def test_totals_statement_is_none_when_no_measure_column_exists() -> None:
    """집계 컬럼 없이 그룹 컬럼뿐이면 합계 문장이 없다.

    테스트 코드: RQ-057
    """
    # given: 그룹 컬럼만 있는 정의
    from app.infra.db.report_select import build_totals_select  # noqa: PLC0415

    report = resolved([col("deal.forecast", group=True), col("deal.vendor", group=True)])

    # when: 합계 문장을 만든다
    totals = build_totals_select(report)
    # then: None이다
    assert totals is None


# ---- 앞 N자는 SQL에 쓰지 않는다 / 코드 컬럼 값은 이름 식 ----


def test_prefix_length_does_not_change_sql() -> None:
    """앞 N자는 SQL을 바꾸지 않는다.

    테스트 코드: RQ-065
    """
    # when: 앞 N자 없는 정의와 있는 정의의 SQL을 만든다
    plain = sql_of(resolved([col("deal.name", group=True), col("deal.amount")]))
    prefixed = sql_of(resolved([col("deal.name", group=True, prefix_length=3), col("deal.amount")]))

    # then: 두 SQL이 같다
    assert plain == prefixed


def test_prefix_length_does_not_change_sql_for_aggregate_and_date_columns() -> None:
    """집계·날짜 컬럼의 앞 N자도 SQL을 바꾸지 않는다.

    테스트 코드: RQ-065
    """
    # given: 날짜 그룹과 금액 컬럼, 앞 N자를 준 같은 정의
    columns = [col("deal.expected_close", format="quarter", group=True), col("deal.amount")]
    prefixed = [
        col("deal.expected_close", format="quarter", group=True, prefix_length=2),
        col("deal.amount", prefix_length=4),
    ]

    # when: 두 정의의 SQL을 만든다
    plain_sql = sql_of(resolved(columns))
    prefixed_sql = sql_of(resolved(prefixed))
    # then: 같다
    assert plain_sql == prefixed_sql


def test_code_column_value_is_name_expression() -> None:
    """코드 컬럼의 값은 key가 아니라 이름 식이다.

    테스트 코드: RQ-041
    """
    # when: Status 그룹핑 SQL을 만든다
    sql = sql_of(resolved([col("deal.status", group=True), col("deal.amount")]))

    # then: 이름 식(cs.name)을 쓰고 첫 컬럼 값이 키가 아니라 이름 열이다
    assert "cs.name AS" in sql
    assert sql.startswith("SELECT base.i1 AS c0")  # 첫 컬럼의 값은 key(i0)가 아니라 이름(i1)
