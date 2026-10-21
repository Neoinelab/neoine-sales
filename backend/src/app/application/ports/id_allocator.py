from enum import StrEnum
from typing import Protocol


class IdKind(StrEnum):
    """앱이 미리 id를 받는 테이블 종류. DB가 매기는 행(deals 등)은 없다."""

    USER = "user"
    SESSION = "session"
    CONTACT = "contact"
    CODE = "code"
    BANT_LABEL = "bant_label"
    ACTION_TYPE = "action_type"
    VENDOR = "vendor"
    SOLUTION = "solution"
    DEAL_ACTION = "deal_action"
    ATTACHMENT = "attachment"


class IdAllocator(Protocol):
    async def next_id(self, kind: IdKind) -> int:
        """kind 테이블 id 시퀀스의 다음 값(1 이상 MAX_ID 이하, 호출마다 증가).

        트랜잭션을 롤백해도 되돌리지 않는다(번호가 비는 것은 허용한다).
        """
        ...
