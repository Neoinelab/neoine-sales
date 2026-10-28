"""리포트 어휘: 엔티티·형식·포맷·연산자·집계와 형식별 허용표, 한도 상수.

검증(`parse`)과 카탈로그 응답이 같은 표를 쓴다.
"""

from enum import StrEnum


class Entity(StrEnum):
    DEAL = "deal"
    ACTION = "action"


class FieldType(StrEnum):
    TEXT = "text"
    CODE = "code"
    USER = "user"
    NUMBER = "number"
    DATE = "date"
    DATETIME = "datetime"


class ValueKind(StrEnum):
    """코드·사용자 조건 값의 모양: 문자열 key 또는 정수 id."""

    KEY = "key"
    ID = "id"


class OptionsSource(StrEnum):
    """DB 목록 선택지의 출처(기존 API). 카탈로그는 출처만 알린다."""

    USERS = "users"
    VENDORS = "vendors"
    STATUS_CODES = "status_codes"
    FORECAST_CODES = "forecast_codes"
    BANT_LABELS = "bant_labels"
    ACTION_TYPES = "action_types"


class Format(StrEnum):
    YMD = "ymd"
    YMD_HM = "ymd_hm"
    YEAR = "year"
    QUARTER = "quarter"
    MONTH = "month"
    WEEKDAY = "weekday"
    RELATIVE = "relative"

    @property
    def affects_query(self) -> bool:
        """SQL(묶음·선택 식)에 영향을 주는 포맷. 나머지는 표시 전용이다."""
        return self in _QUERY_FORMATS


_QUERY_FORMATS = frozenset({Format.YMD, Format.YEAR, Format.QUARTER, Format.MONTH})


class NumberUnit(StrEnum):
    """숫자 값의 표시 단위. 값은 원 단위 그대로 주고 화면이 이 단위로 나눠 보인다."""

    KRW_THOUSAND = "krw_thousand"


class Operator(StrEnum):
    CONTAINS = "contains"
    EQUALS = "equals"
    STARTS_WITH = "starts_with"
    IS_EMPTY = "is_empty"
    IS_NOT_EMPTY = "is_not_empty"
    IN = "in"
    NOT_IN = "not_in"
    EQ = "eq"
    NE = "ne"
    GT = "gt"
    GTE = "gte"
    LT = "lt"
    LTE = "lte"
    BETWEEN = "between"
    BEFORE = "before"
    AFTER = "after"
    RELATIVE = "relative"


class Aggregate(StrEnum):
    SUM = "sum"
    AVG = "avg"
    MIN = "min"
    MAX = "max"
    COUNT = "count"
    COUNT_DISTINCT = "count_distinct"


class Combine(StrEnum):
    AND = "and"
    OR = "or"


class SortDirection(StrEnum):
    ASC = "asc"
    DESC = "desc"


class RelativePeriod(StrEnum):
    THIS_YEAR = "this_year"
    THIS_QUARTER = "this_quarter"
    THIS_MONTH = "this_month"
    LAST_N_DAYS = "last_n_days"
    BEFORE_TODAY = "before_today"


class ResultValueType(StrEnum):
    """결과 열 값의 JSON 모양."""

    TEXT = "text"
    INTEGER = "integer"
    DECIMAL = "decimal"
    DATE = "date"
    DATETIME = "datetime"


# ---- 한도 ----
COLUMNS_MIN = 1
COLUMNS_MAX = 30
CONDITIONS_MAX = 20
LABEL_MAX = 100
PREFIX_MIN = 1
PREFIX_MAX = 200
TEXT_VALUE_MAX = 200
LIST_VALUE_MAX = 100
LAST_N_DAYS_MAX = 3650
NUMBER_MAX = 2**53 - 1
ROW_LIMITS = (100, 1000, 10000)
DEFAULT_ROW_LIMIT = 1000
STATEMENT_TIMEOUT_SECONDS = 10

# ---- 형식별 허용표 (포맷 없는 형식은 빈 튜플·기본 None) ----
TYPE_FORMATS: dict[FieldType, tuple[Format, ...]] = {
    FieldType.TEXT: (),
    FieldType.CODE: (),
    FieldType.USER: (),
    FieldType.NUMBER: (),
    FieldType.DATE: (
        Format.YMD,
        Format.YEAR,
        Format.QUARTER,
        Format.MONTH,
        Format.WEEKDAY,
        Format.RELATIVE,
    ),
    FieldType.DATETIME: (
        Format.YMD_HM,
        Format.YMD,
        Format.YEAR,
        Format.QUARTER,
        Format.MONTH,
        Format.WEEKDAY,
        Format.RELATIVE,
    ),
}
_TEXT_OPERATORS = (
    Operator.CONTAINS,
    Operator.EQUALS,
    Operator.STARTS_WITH,
    Operator.IS_EMPTY,
    Operator.IS_NOT_EMPTY,
)
_LIST_OPERATORS = (Operator.IN, Operator.NOT_IN, Operator.IS_EMPTY)
_DATE_OPERATORS = (Operator.BETWEEN, Operator.BEFORE, Operator.AFTER, Operator.RELATIVE)
TYPE_OPERATORS: dict[FieldType, tuple[Operator, ...]] = {
    FieldType.TEXT: _TEXT_OPERATORS,
    FieldType.CODE: _LIST_OPERATORS,
    FieldType.USER: _LIST_OPERATORS,
    FieldType.NUMBER: (
        Operator.EQ,
        Operator.NE,
        Operator.GT,
        Operator.GTE,
        Operator.LT,
        Operator.LTE,
        Operator.BETWEEN,
    ),
    FieldType.DATE: _DATE_OPERATORS,
    FieldType.DATETIME: _DATE_OPERATORS,
}
_COUNT_AGGREGATES = (Aggregate.COUNT, Aggregate.COUNT_DISTINCT)
TYPE_AGGREGATES: dict[FieldType, tuple[Aggregate, ...]] = {
    FieldType.TEXT: _COUNT_AGGREGATES,
    FieldType.CODE: _COUNT_AGGREGATES,
    FieldType.USER: _COUNT_AGGREGATES,
    FieldType.NUMBER: (Aggregate.SUM, Aggregate.AVG, Aggregate.MIN, Aggregate.MAX),
    FieldType.DATE: _COUNT_AGGREGATES,
    FieldType.DATETIME: _COUNT_AGGREGATES,
}
TYPE_DEFAULT_FORMAT: dict[FieldType, Format | None] = {
    FieldType.TEXT: None,
    FieldType.CODE: None,
    FieldType.USER: None,
    FieldType.NUMBER: None,
    FieldType.DATE: Format.YMD,
    FieldType.DATETIME: Format.YMD_HM,
}
