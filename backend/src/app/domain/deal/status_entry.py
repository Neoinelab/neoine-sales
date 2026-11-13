from dataclasses import dataclass
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from datetime import date


@dataclass(frozen=True, slots=True)
class StatusEntry:
    """현재 Status에 진입한 업무 날짜. Status가 바뀔 때만 새로 만든다."""

    status_key: str
    changed_on: date
