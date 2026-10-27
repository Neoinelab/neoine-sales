"""Reports SQL 생성 단위 테스트용 컴파일 도우미(DB 접속 없음).

계약(구현 담당이 맞춘다):
- `app.infra.db.report_select.build_select(report: ResolvedReport) -> sqlalchemy.Select`:
  데이터 문장(바인딩 파라미터만 쓴다, 행 수 제한·`count(*) OVER ()` 포함)
- `app.infra.db.report_select.build_totals_select(report) -> Select | None`:
  그룹핑이 있을 때만 같은 조건·같은 Q5 규칙의 그룹 없는 합계 문장, 그 밖은 None
- `app.infra.db.report_render.display_sql(statement) -> str`: 표시 전용 SQL 문자열
"""

from typing import TYPE_CHECKING, Any

from sqlalchemy.dialects import postgresql

if TYPE_CHECKING:
    from sqlalchemy import Select

    from app.domain.report.resolve import ResolvedReport


def build(report: ResolvedReport) -> Select[Any]:
    from app.infra.db.report_select import build_select  # noqa: PLC0415

    return build_select(report)


def compiled(statement: Select[Any]) -> tuple[str, dict[str, Any]]:
    """실행용 컴파일 결과 (SQL 문자열, 바인딩 파라미터). 값이 SQL 문자열에 들어가지 않는다."""
    result = statement.compile(dialect=postgresql.dialect())  # type: ignore[no-untyped-call]
    return str(result), dict(result.params)


def sql_of(report: ResolvedReport) -> str:
    return compiled(build(report))[0]


def params_of(report: ResolvedReport) -> dict[str, Any]:
    return compiled(build(report))[1]


def flat_params(report: ResolvedReport) -> list[Any]:
    """파라미터 값을 평평하게 편다(expanding IN 목록 포함)."""
    out: list[Any] = []
    for value in params_of(report).values():
        out.extend(value) if isinstance(value, (list, tuple)) else out.append(value)
    return out
