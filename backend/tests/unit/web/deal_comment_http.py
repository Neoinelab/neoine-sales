"""Deal Comment 라우터 단위 테스트 공용 도우미: FakeUseCases 위의 ASGI 클라이언트와 시드.

클라이언트(사용자별 세션)와 Problem 단언은 저장 리포트 라우터 테스트의 도우미를 그대로 쓴다.
Deal(CODE)과 그 Deal의 Action 하나, 다른 Deal(OTHER)과 그 Action은 Fake 저장소에 직접 두고
Comment는 API(POST)로 만든다.
"""

from typing import TYPE_CHECKING, Any, Final

from app.domain.auth.principal import Role
from tests.factories_deal import seed_deal
from tests.fakes.catalog_seed import seed_action_types, seed_catalog
from tests.support.user_ids import OWNER_ID
from tests.support.user_seed import ensure_users
from tests.unit.web.saved_report_http import clients, problem

if TYPE_CHECKING:
    from httpx import AsyncClient

    from app.domain.user.value_objects import UserId
    from tests.fakes.use_cases import FakeUseCases

__all__ = [
    "BLANK",
    "CODE",
    "COUNTS",
    "DEAL_COMMENTS",
    "NOT_FOUND",
    "OTHER",
    "READS",
    "READ_FORBIDDEN",
    "READ_ONLY",
    "RESPONSE_KEYS",
    "SINGLE",
    "USERS",
    "clients",
    "post_action",
    "post_comment",
    "problem",
    "seed",
]

CODE: Final = "20261016-A001"
OTHER: Final = "20261016-A002"
DEAL_COMMENTS: Final = f"/api/v1/deals/{CODE}/comments"
SINGLE: Final = "/api/v1/deal-comments"
READS: Final = f"/api/v1/deals/{CODE}/comment-reads"
COUNTS: Final = f"/api/v1/deals/{CODE}/comment-counts"
READ_ONLY: Final = "이 작업을 할 권한이 없습니다(읽기 전용 계정)"
NOT_FOUND: Final = "Comment를 찾을 수 없습니다."
BLANK: Final = "Comment를 입력하세요."
READ_FORBIDDEN: Final = "Deal Owner만 Comment를 읽음 처리할 수 있습니다."
USERS: Final = {
    "anon": Role.USER,
    "boss": Role.ADMIN,
    "kim": Role.SALES,
    "park": Role.SALES,
    "viewer": Role.USER,
}
RESPONSE_KEYS: Final = {
    "id",
    "deal_code",
    "action_id",
    "action",
    "body",
    "author",
    "created_at",
    "updated_at",
    "read_at",
}


async def seed(owner: UserId = OWNER_ID) -> FakeUseCases:
    """Deal 둘(CODE·OTHER)과 기본 코드·Action 유형이 있는 Fake 앱 상태. 두 Deal의 Owner는 owner다.

    `uid("kim")`을 주면 로그인 아이디 "kim" 사용자가 Owner가 된다(`clients`가 같은 행으로 로그인).
    """
    from tests.fakes.use_cases import FakeUseCases  # noqa: PLC0415

    use_cases = FakeUseCases()
    seed_catalog(use_cases.uow)
    seed_action_types(use_cases.uow)
    async with use_cases.uow as uow:
        await ensure_users(uow.users, owner)
        for code in (CODE, OTHER):
            await seed_deal(uow, code=code, commit=False, owner_user_id=owner)
        await uow.commit()
    return use_cases


async def post_action(http: AsyncClient, code: str = CODE) -> int:
    """그 Deal에 Action 하나를 API로 등록하고 id를 돌려준다."""
    body = {"action_type": {"name": "미팅"}, "action": "킥오프", "next_action": ""}
    response = await http.post(f"/api/v1/deals/{code}/actions", json=body)
    assert response.status_code == 201, response.text
    return int(response.json()["id"])


async def post_comment(http: AsyncClient, body: str = "예산 확인", **extra: Any) -> dict[str, Any]:  # noqa: ANN401
    """Comment 하나를 만들고 응답 본문을 돌려준다(Deal은 CODE)."""
    response = await http.post(DEAL_COMMENTS, json={"body": body, **extra})
    assert response.status_code == 201, response.text
    return dict(response.json())
