"""Deal Actions 필드 12개 (계획 4.3 표 순서). `action.count`는 그룹핑할 때만 쓰는 가상 필드다."""

from dataclasses import replace

from app.domain.deal_action.next_action_status import NextActionStatus
from app.domain.report.fields import (
    CodeSource,
    FieldSpec,
    code_field,
    date_field,
    datetime_field,
    number_field,
    text_field,
    user_field,
)
from app.domain.report.vocabulary import Aggregate, OptionsSource

_ACTION_COUNT = replace(
    number_field("action.count", "Action 건수"),
    operators=(),
    aggregates=(),
    default_aggregate=Aggregate.COUNT,
    groupable=False,
    filterable=False,
    requires_grouping=True,
    deal_number=False,
)

ACTION_FIELDS: tuple[FieldSpec, ...] = (
    text_field("action.action", "진행사항"),
    text_field("action.next_action", "Next Action"),
    text_field("action.memo", "Memo"),
    user_field("action.actor", "수행자"),
    code_field("action.type", "Action 유형", CodeSource.by_id(OptionsSource.ACTION_TYPES)),
    code_field(
        "action.next_action_status",
        "Next Action 상태",
        CodeSource.static(*((s.value, s.label) for s in NextActionStatus)),
    ),
    code_field("action.status", "당시 Status", CodeSource.by_key(OptionsSource.STATUS_CODES)),
    code_field("action.forecast", "당시 Forecast", CodeSource.by_key(OptionsSource.FORECAST_CODES)),
    date_field("action.due_date", "Due Date"),
    datetime_field("action.acted_at", "수행일시"),
    datetime_field("action.closed_at", "종료 시각"),
    _ACTION_COUNT,
)
