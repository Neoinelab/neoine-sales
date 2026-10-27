"""필드 카탈로그의 항목(`FieldSpec`)과 형식별 생성 도우미."""

from dataclasses import dataclass, replace

from app.domain.report.vocabulary import (
    TYPE_AGGREGATES,
    TYPE_DEFAULT_FORMAT,
    TYPE_FORMATS,
    TYPE_OPERATORS,
    Aggregate,
    Entity,
    FieldType,
    Format,
    Operator,
    OptionsSource,
    ValueKind,
)


@dataclass(frozen=True, slots=True)
class FieldOption:
    value: str
    label: str


@dataclass(frozen=True, slots=True)
class CodeSource:
    """코드 필드의 조건 값 모양과 선택지: 정적 목록 또는 기존 API 출처 중 하나."""

    kind: ValueKind
    options: tuple[FieldOption, ...] | None = None
    source: OptionsSource | None = None
    category: str | None = None

    @classmethod
    def static(cls, *options: tuple[str, str]) -> CodeSource:
        return cls(ValueKind.KEY, options=tuple(FieldOption(v, label) for v, label in options))

    @classmethod
    def by_key(cls, source: OptionsSource) -> CodeSource:
        return cls(ValueKind.KEY, source=source)

    @classmethod
    def by_id(cls, source: OptionsSource, category: str | None = None) -> CodeSource:
        return cls(ValueKind.ID, source=source, category=category)


@dataclass(frozen=True, slots=True)
class FieldSpec:
    """허용 필드 하나. 리포트는 이 목록에 있는 key만 쓸 수 있다(화이트리스트)."""

    key: str
    label: str
    type: FieldType
    formats: tuple[Format, ...]
    default_format: Format
    operators: tuple[Operator, ...]
    aggregates: tuple[Aggregate, ...]
    default_aggregate: Aggregate | None = None
    groupable: bool = True
    filterable: bool = True
    requires_grouping: bool = False
    deal_number: bool = False
    value_kind: ValueKind | None = None
    options: tuple[FieldOption, ...] | None = None
    options_source: OptionsSource | None = None
    options_category: str | None = None

    @property
    def entity(self) -> Entity:
        return Entity(self.key.split(".", 1)[0])

    def allowed_aggregates(self) -> tuple[Aggregate, ...]:
        """그룹핑 리포트에서 고를 수 있는 집계. 집계 목록이 비어 있으면 고정 집계 하나뿐이다."""
        if self.aggregates:
            return self.aggregates
        return (self.default_aggregate,) if self.default_aggregate else ()


def _base(key: str, label: str, field_type: FieldType) -> FieldSpec:
    return FieldSpec(
        key=key,
        label=label,
        type=field_type,
        formats=TYPE_FORMATS[field_type],
        default_format=TYPE_DEFAULT_FORMAT[field_type],
        operators=TYPE_OPERATORS[field_type],
        aggregates=TYPE_AGGREGATES[field_type],
    )


def text_field(key: str, label: str) -> FieldSpec:
    return _base(key, label, FieldType.TEXT)


def code_field(key: str, label: str, source: CodeSource) -> FieldSpec:
    return replace(
        _base(key, label, FieldType.CODE),
        value_kind=source.kind,
        options=source.options,
        options_source=source.source,
        options_category=source.category,
    )


def user_field(key: str, label: str) -> FieldSpec:
    return replace(
        _base(key, label, FieldType.USER),
        value_kind=ValueKind.ID,
        options_source=OptionsSource.USERS,
    )


def number_field(
    key: str,
    label: str,
    *,
    default_format: Format = Format.THOUSANDS,
    default_aggregate: Aggregate = Aggregate.SUM,
) -> FieldSpec:
    """Deal 숫자(금액·Users·Status 체류 일수). 행 범위가 Action이면 Deal당 한 번 계산한다."""
    return replace(
        _base(key, label, FieldType.NUMBER),
        default_format=default_format,
        default_aggregate=default_aggregate,
        deal_number=True,
    )


def date_field(key: str, label: str) -> FieldSpec:
    return _base(key, label, FieldType.DATE)


def datetime_field(key: str, label: str) -> FieldSpec:
    return _base(key, label, FieldType.DATETIME)
