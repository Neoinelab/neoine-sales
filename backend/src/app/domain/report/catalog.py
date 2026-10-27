"""리포트가 쓸 수 있는 필드의 화이트리스트. 여기 없는 key는 어떤 경로로도 SQL에 닿지 않는다."""

from typing import TYPE_CHECKING

from app.domain.report.catalog_action import ACTION_FIELDS
from app.domain.report.catalog_deal import DEAL_FIELDS

if TYPE_CHECKING:
    from app.domain.report.fields import FieldSpec

FIELD_CATALOG: tuple[FieldSpec, ...] = (*DEAL_FIELDS, *ACTION_FIELDS)

_BY_KEY: dict[str, FieldSpec] = {spec.key: spec for spec in FIELD_CATALOG}


def find_field(key: str) -> FieldSpec | None:
    """key가 카탈로그와 정확히 같을 때만 찾는다(대소문자·공백 구분)."""
    return _BY_KEY.get(key)
