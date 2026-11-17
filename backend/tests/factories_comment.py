"""Deal Comment 테스트용 생성 도우미. 기본은 유효한 더미 값이다.

팩토리는 연결 검사·권한을 거치지 않고 필드로 직접 만든다(규칙 자체를 검증하는 테스트가 팩토리에
기대지 않도록). 도메인 모듈은 사용 시점에 가져온다(구현 전에도 이 모듈을 쓰는 다른 테스트의 수집이
막히지 않게).

계약(구현 담당이 맞춘다): `DealComment.write(entity_id=, deal_code=, action_id=, author_user_id=,
body=, now=, deal_owner_id=)`는 키워드 전용이고, `body`는 이미 `comment_body`를 거친 값이다.
작성자가 `deal_owner_id`와 같으면 `read_at` = `now`, 아니면 None이다(CM-R26). 기본 Deal Owner는
팩토리 기본 담당자 `OWNER_ID`라서 기본 작성자(`ACTOR_ID`)의 Comment는 읽지 않음이다.
"""

from typing import TYPE_CHECKING

from tests.factories import NOW, make_deal_code
from tests.support.ids import new_id
from tests.support.user_ids import ACTOR_ID, OWNER_ID

if TYPE_CHECKING:
    from datetime import datetime

    from app.domain.deal.code import DealCode
    from app.domain.deal_action.value_objects import DealActionId
    from app.domain.deal_comment.entities import DealComment
    from app.domain.user.value_objects import UserId


def make_comment(  # noqa: PLR0913 - Comment 생성에 필요한 값이 모두 독립적인 선택지
    *,
    deal_code: DealCode | None = None,
    action_id: DealActionId | None = None,
    body: str = "예산 확인",
    author: UserId = ACTOR_ID,
    deal_owner: UserId = OWNER_ID,
    entity_id: int | None = None,
    now: datetime = NOW,
) -> DealComment:
    """저장하지 않은 Comment(`DealComment.write`). action_id가 None이면 Deal Comment다.

    deal_owner를 author와 같게 주면 읽음(read_at = now)으로 만들어진다.
    """
    from app.domain.deal_comment.entities import DealComment  # noqa: PLC0415
    from app.domain.deal_comment.values import DealCommentId  # noqa: PLC0415

    return DealComment.write(
        entity_id=DealCommentId(new_id() if entity_id is None else entity_id),
        deal_code=deal_code or make_deal_code(),
        action_id=action_id,
        author_user_id=author,
        body=body,
        now=now,
        deal_owner_id=deal_owner,
    )
