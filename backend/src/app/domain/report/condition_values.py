"""조건 값의 모양(값 객체)과 연산자별 해석. 모양이 틀리면 `ConditionValueError`."""

import re
from dataclasses import dataclass
from datetime import date

from app.domain.common.validation import DATE_CRITERIA_MAX, DATE_CRITERIA_MIN
from app.domain.report.vocabulary import (
    LAST_N_DAYS_MAX,
    LIST_VALUE_MAX,
    NUMBER_MAX,
    TEXT_VALUE_MAX,
    Operator,
    RelativePeriod,
    ValueKind,
)

_DATE_PATTERN = re.compile(r"[0-9]{4}-[0-9]{2}-[0-9]{2}")


class ConditionValueError(ValueError):
    """조건 값이 연산자가 요구하는 모양이 아님(메시지는 사용자에게 보여 줄 한국어)."""


@dataclass(frozen=True, slots=True)
class NoValue:
    """is_empty·is_not_empty: 값 없음."""


@dataclass(frozen=True, slots=True)
class TextValue:
    text: str


@dataclass(frozen=True, slots=True)
class KeyList:
    keys: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class IdList:
    ids: tuple[int, ...]


@dataclass(frozen=True, slots=True)
class NumberValue:
    n: int


@dataclass(frozen=True, slots=True)
class NumberRange:
    low: int
    high: int


@dataclass(frozen=True, slots=True)
class DateValue:
    day: date


@dataclass(frozen=True, slots=True)
class DateRange:
    first: date
    last: date


@dataclass(frozen=True, slots=True)
class RelativeValue:
    period: RelativePeriod
    days: int | None = None


type ConditionValue = (
    NoValue
    | TextValue
    | KeyList
    | IdList
    | NumberValue
    | NumberRange
    | DateValue
    | DateRange
    | RelativeValue
)

_TEXT_OPERATORS = frozenset({Operator.CONTAINS, Operator.EQUALS, Operator.STARTS_WITH})
_RANGED_OPERATORS = frozenset(
    {Operator.BETWEEN, Operator.BEFORE, Operator.AFTER, Operator.RELATIVE}
)


def _number(raw: object) -> int:
    if type(raw) is not int or not -NUMBER_MAX <= raw <= NUMBER_MAX:
        raise ConditionValueError(f"정수(절댓값 {NUMBER_MAX} 이하)를 입력하세요")
    return raw


def _day(raw: object) -> date:
    if not isinstance(raw, str) or not _DATE_PATTERN.fullmatch(raw):
        raise ConditionValueError("날짜는 YYYY-MM-DD 형식으로 입력하세요")
    try:
        day = date.fromisoformat(raw)
    except ValueError:
        raise ConditionValueError("존재하지 않는 날짜입니다") from None
    if not DATE_CRITERIA_MIN <= day <= DATE_CRITERIA_MAX:
        raise ConditionValueError("날짜는 1900-01-01부터 2999-12-31 사이여야 합니다")
    return day


def _pair(raw: object) -> tuple[object, object]:
    if not isinstance(raw, list | tuple) or len(raw) != 2:  # noqa: PLR2004
        raise ConditionValueError("범위는 시작과 끝 두 값이 필요합니다")
    return raw[0], raw[1]


def _text(raw: object) -> TextValue:
    if not isinstance(raw, str) or "\x00" in raw:
        raise ConditionValueError("검색어를 문자열로 입력하세요")
    text = raw.strip()
    if not text or len(text) > TEXT_VALUE_MAX:
        raise ConditionValueError(f"검색어는 공백이 아닌 {TEXT_VALUE_MAX}자 이하여야 합니다")
    return TextValue(text)


def _id(raw: object) -> int:
    if type(raw) is not int or not 1 <= raw <= NUMBER_MAX:
        raise ConditionValueError("선택 값은 양의 정수 id여야 합니다")
    return raw


def _key(raw: object) -> str:
    if not isinstance(raw, str) or not raw or len(raw) > TEXT_VALUE_MAX or "\x00" in raw:
        raise ConditionValueError("선택 값은 비어 있지 않은 문자열이어야 합니다")
    return raw


def _choices(raw: object, kind: ValueKind | None) -> KeyList | IdList:
    if not isinstance(raw, list | tuple) or not 1 <= len(raw) <= LIST_VALUE_MAX:
        raise ConditionValueError(f"선택 값은 1개 이상 {LIST_VALUE_MAX}개 이하의 목록이어야 합니다")
    if kind is ValueKind.ID:
        return IdList(tuple(_id(item) for item in raw))
    return KeyList(tuple(_key(item) for item in raw))


def _number_range(raw: object) -> NumberRange:
    low, high = (_number(v) for v in _pair(raw))
    if low > high:
        raise ConditionValueError("범위의 시작이 끝보다 클 수 없습니다")
    return NumberRange(low, high)


def _date_range(raw: object) -> DateRange:
    first, last = (_day(v) for v in _pair(raw))
    if first > last:
        raise ConditionValueError("범위의 시작이 끝보다 늦을 수 없습니다")
    return DateRange(first, last)


def _relative(raw: object) -> RelativeValue:
    if not isinstance(raw, dict) or not set(raw) <= {"period", "days"}:
        raise ConditionValueError("상대 기간은 period(와 days)를 가진 객체여야 합니다")
    period_name = raw.get("period")
    period = RelativePeriod(period_name) if period_name in set(RelativePeriod) else None
    if period is None:
        raise ConditionValueError("알 수 없는 상대 기간입니다")
    days = raw.get("days")
    if period is not RelativePeriod.LAST_N_DAYS:
        if days is not None:
            raise ConditionValueError("days는 최근 N일에서만 쓸 수 있습니다")
        return RelativeValue(period)
    if type(days) is not int or not 1 <= days <= LAST_N_DAYS_MAX:
        raise ConditionValueError(f"최근 N일의 N은 1~{LAST_N_DAYS_MAX}의 정수여야 합니다")
    return RelativeValue(period, days)


def _ranged(operator: Operator, raw: object, *, is_date: bool) -> ConditionValue:
    if operator is Operator.RELATIVE:
        return _relative(raw)
    if operator is Operator.BETWEEN:
        return _date_range(raw) if is_date else _number_range(raw)
    return DateValue(_day(raw))


def parse_condition_value(
    operator: Operator, raw: object, *, is_date: bool, kind: ValueKind | None
) -> ConditionValue:
    """연산자가 요구하는 모양으로 값을 해석한다. is_date는 날짜·시각 필드, kind는 코드·사용자 값."""
    if operator in {Operator.IS_EMPTY, Operator.IS_NOT_EMPTY}:
        if raw is not None:
            raise ConditionValueError("이 연산자에는 값이 필요하지 않습니다")
        return NoValue()
    if operator in _TEXT_OPERATORS:
        return _text(raw)
    if operator in {Operator.IN, Operator.NOT_IN}:
        return _choices(raw, kind)
    if operator in _RANGED_OPERATORS:
        return _ranged(operator, raw, is_date=is_date)
    return NumberValue(_number(raw))
