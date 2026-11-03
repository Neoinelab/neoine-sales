"""차트 설정의 단순 칸(켜기·끄기, 글자, 축 범위) 검증. `parse_chart`가 쓴다."""

from typing import TYPE_CHECKING

from app.domain.report.chart import CHART_TEXT_MAX, PERCENT_MAX
from app.domain.report.parse_chart_options import is_bounded_number

if TYPE_CHECKING:
    from app.domain.report.chart_kinds import KindRule
    from app.domain.report.errors import IssueLog
    from app.domain.report.raw import RawChart


def check_flag(  # noqa: PLR0913
    raw: object,
    key: str,
    code: str,
    *,
    allowed: bool | None,
    log: IssueLog,
    bad_type_code: str | None = None,
) -> bool:
    """bool이어야 하고, `allowed`가 False(알려진 종류가 막음)이면 true일 수 없다."""
    if type(raw) is not bool:
        message = "켜기·끄기 값이어야 합니다"
        if key == "swap":
            message = "이 차트는 행/열 전환을 쓸 수 없습니다"
        log.add(("chart", key), bad_type_code or code, message)
        return False
    if raw and allowed is False:
        message = (
            "보조 축은 콤보 차트에서만 쓸 수 있습니다"
            if key == "secondary_axis"
            else "이 차트는 행/열 전환을 쓸 수 없습니다"
        )
        log.add(("chart", key), code, message)
    return raw


def check_text(raw: object, key: str, log: IssueLog) -> str:
    if type(raw) is str and "\x00" not in raw and len(raw.strip()) <= CHART_TEXT_MAX:
        return raw.strip()
    log.add(("chart", key), "chart-text-invalid", "100자 이내 글자로 입력하세요")
    return ""


def check_range(
    raw: RawChart, rule: KindRule | None, log: IssueLog
) -> tuple[int | float | None, int | float | None]:
    bounds: dict[str, int | float | None] = {}
    for key, value in (("value_min", raw.value_min), ("value_max", raw.value_max)):
        bounds[key] = _bound(key, value, rule, log)
    low, high = bounds["value_min"], bounds["value_max"]
    if low is not None and high is not None and low >= high and not _has_range_issue(log):
        log.add(("chart", "value_max"), "chart-range-order", "최대는 최소보다 커야 합니다")
    return low, high


def _has_range_issue(log: IssueLog) -> bool:
    return any(i.code == "chart-range-invalid" for i in log.items)


def _bound(key: str, value: object, rule: KindRule | None, log: IssueLog) -> int | float | None:
    if value is None:
        return None
    location = ("chart", key)
    if not is_bounded_number(value):
        log.add(location, "chart-range-invalid", "숫자를 입력하세요")
        return None
    number: int | float = value  # type: ignore[assignment]
    if rule is not None and not rule.allows_value_range:
        log.add(location, "chart-range-invalid", "이 차트는 축 범위를 쓸 수 없습니다")
    elif rule is not None and rule.percent_axis and not 0 <= number <= PERCENT_MAX:
        log.add(location, "chart-range-invalid", "0~100 사이로 입력하세요")
    return number
