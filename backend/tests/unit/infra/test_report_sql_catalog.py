"""Reports SQL 생성: 카탈로그의 모든 필드와 연산자가 SQL이 되고 표시 SQL로 그려진다.

필드 key는 카탈로그 조회로만 식을 얻는다(화이트리스트). 새 필드를 카탈로그에 넣고 SQL 매핑을
빠뜨리면 여기서 드러난다.
"""

from datetime import date
from typing import Any

import pytest

from app.domain.report.catalog import FIELD_CATALOG
from app.domain.report.vocabulary import FieldType
from tests.support.report_defs import VALID_CONDITIONS, col, cond, resolved
from tests.support.report_sql import build, compiled

SCALAR_FIELDS = [f for f in FIELD_CATALOG if not f.requires_grouping]
FILTERABLE = [f for f in FIELD_CATALOG if f.filterable]


def _display(report: Any) -> str:  # noqa: ANN401 - ResolvedReport
    from app.infra.db.report_render import display_sql  # noqa: PLC0415

    return display_sql(build(report))


def _sample(spec: Any, operator: str) -> object:  # noqa: PLR0911, ANN401 - FieldSpec
    if operator in {"is_empty", "is_not_empty"}:
        return None
    if spec.type == FieldType.TEXT:
        return "abc"
    if spec.type in {FieldType.CODE, FieldType.USER}:
        if spec.options:
            return [spec.options[0].value]
        return [1] if str(spec.value_kind) == "id" else ["x"]
    if spec.type == FieldType.NUMBER:
        return [1, 9] if operator == "between" else 5
    if operator == "relative":
        return {"period": "this_month"}
    if operator == "between":
        return ["2026-01-01", "2026-01-31"]
    return date(2026, 1, 1).isoformat()


@pytest.mark.parametrize("spec", SCALAR_FIELDS, ids=lambda f: f.key)
def test_every_field_can_be_selected_as_a_plain_column(spec: Any) -> None:  # noqa: ANN401
    # when: 필드 하나를 컬럼으로 하는 정의의 SQL을 만든다 (전제: 필드 매개변수)
    """카탈로그의 모든 필드는 일반 컬럼으로 SQL이 되고 Action 필드만 Action을 JOIN한다.

    테스트 코드: RQ-060
    """
    sql = compiled(build(resolved([col(spec.key)])))[0]

    # then: deals에서 읽고 Action 필드일 때만 deal_actions를 JOIN한다
    assert "FROM deals" in sql
    assert ("JOIN deal_actions" in sql) == (spec.entity == "action")  # Action 필드만 행을 늘린다


@pytest.mark.parametrize("spec", [f for f in FIELD_CATALOG if f.groupable], ids=lambda f: f.key)
def test_every_groupable_field_can_be_a_group_column(spec: Any) -> None:  # noqa: ANN401
    # given: 필드 하나를 그룹으로 하고 Deal code 건수를 가진 정의 (매개변수)
    """그룹핑 가능한 모든 필드는 그룹 키로 SQL이 된다.

    테스트 코드: RQ-060
    """
    report = resolved([col(spec.key, group=True), col("deal.code", aggregate="count")])

    # when: SQL을 만든다
    sql = compiled(build(report))[0]

    # then: GROUP BY 절이 비어 있지 않고 집계 식이 아니라 그룹 키이며 표시 SQL에도 GROUP BY가 있다
    clause = sql.rsplit("GROUP BY", 1)[1].split(" ORDER BY")[0].split(" LIMIT")[0]
    assert clause.strip()  # 그룹 컬럼 식이 GROUP BY에 들어간다
    assert "count(" not in clause  # 집계 식이 아니라 그룹 키다
    assert "GROUP BY" in _display(report).upper()


def test_action_count_can_be_selected_when_grouped() -> None:
    """그룹핑할 때 Action 건수는 Action을 JOIN해 count로 SQL이 된다.

    테스트 코드: RQ-060
    """
    # when: Vendor 그룹과 Action 건수의 SQL을 만든다
    sql = compiled(build(resolved([col("deal.vendor", group=True), col("action.count")])))[0]

    # then: deal_actions JOIN과 count 식이 있다
    assert "JOIN deal_actions" in sql
    assert "count(" in sql


@pytest.mark.parametrize(
    ("spec", "operator"),
    [(f, op) for f in FILTERABLE for op in f.operators],
    ids=lambda v: getattr(v, "key", str(v)),
)
def test_display_sql_renders_for_every_field_and_operator(spec: Any, operator: str) -> None:  # noqa: ANN401
    # given: 필드·연산자 조합 조건 (매개변수)
    """필터 가능한 모든 필드·연산자는 표시 SQL로 그려진다.

    테스트 코드: RQ-060
    """
    report = resolved(
        [col("deal.code")], [cond(spec.key, str(operator), _sample(spec, str(operator)))]
    )

    # when: 표시 SQL을 만든다
    text = _display(report)

    # then: SELECT 또는 WITH로 시작하는 문자열이다
    assert isinstance(text, str)
    assert text.lstrip().upper().startswith(("SELECT", "WITH"))


@pytest.mark.parametrize(("field", "operator", "value"), VALID_CONDITIONS)
def test_display_sql_renders_for_the_valid_condition_samples(
    field: str, operator: str, value: object
) -> None:
    """허용 조건 샘플은 모두 표시 SQL로 그려진다.

    테스트 코드: RQ-060
    """
    # when: 조건 샘플 하나의 표시 SQL을 만든다 (전제: 샘플 매개변수)
    text = _display(resolved([col("deal.code")], [cond(field, operator, value)]))

    # then: SELECT를 포함한다
    assert "SELECT" in text.upper()


def test_display_sql_shows_the_values_the_user_typed() -> None:
    """표시 SQL에는 사용자가 입력한 값이 보인다.

    테스트 코드: RQ-059
    """
    # when: 검색어 kickoff 조건의 표시 SQL을 만든다
    text = _display(resolved([col("deal.code")], [cond("deal.name", "contains", "kickoff")]))

    # then: 표시 SQL에 kickoff가 있다
    assert "kickoff" in text


def test_display_sql_renders_grouped_reports_with_totals_inputs() -> None:
    """그룹핑 리포트(경고 조건 포함)도 표시 SQL로 그려진다.

    테스트 코드: RQ-059
    """
    # when: 그룹핑과 경고 조건이 있는 리포트의 표시 SQL을 만든다
    text = _display(
        resolved(
            [col("deal.vendor", group=True), col("deal.amount"), col("deal.status_days")],
            [cond("deal.risk", "in", ["overdue"])],
        )
    )

    # then: GROUP BY가 있다
    assert "GROUP BY" in text.upper()
