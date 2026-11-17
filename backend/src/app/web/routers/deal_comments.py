"""Deal Comment. 작성·Deal별 조회는 Deal 아래에, 개별 조작은 /deal-comments에 둔다."""

from fastapi import Response, status

from app.application.deal.inputs import Actor
from app.domain.deal_action.value_objects import DealActionId
from app.domain.deal_comment.values import DealCommentId
from app.web.dependencies import Provider
from app.web.permissions import BusinessRouter
from app.web.routers.responses import READ_ERRORS, WRITE_ERRORS
from app.web.schemas.deal_comment import (
    DealCommentCounts,
    DealCommentCreateRequest,
    DealCommentList,
    DealCommentReadRequest,
    DealCommentResponse,
    comment_response,
    comment_responses,
)
from app.web.schemas.ids import PathId, QueryId
from app.web.security import CurrentUser

router = BusinessRouter(prefix="/api/v1", tags=["deal-comments"])


def _actor(user: CurrentUser) -> Actor:
    return Actor(user_id=user.user_id, role=user.role)


@router.post(
    "/deals/{code}/comments",
    status_code=status.HTTP_201_CREATED,
    response_model=DealCommentResponse,
    responses=WRITE_ERRORS,
)
async def write_deal_comment(
    code: str,
    body: DealCommentCreateRequest,
    response: Response,
    user: CurrentUser,
    provider: Provider,
) -> DealCommentResponse:
    comment = await provider.write_deal_comment().execute(code, body.to_input(), _actor(user))
    response.headers["Location"] = f"{router.prefix}/deal-comments/{comment.id}"
    return await comment_response(provider, await provider.get_deal_comment().execute(comment.id))


@router.get("/deals/{code}/comments", response_model=DealCommentList, responses=READ_ERRORS)
async def list_deal_comments(
    code: str, provider: Provider, action_id: QueryId | None = None
) -> DealCommentList:
    link = None if action_id is None else DealActionId(action_id)
    found = await provider.list_deal_comments().execute(code, link)
    return DealCommentList(items=await comment_responses(provider, found))


@router.get(
    "/deal-comments/{comment_id}", response_model=DealCommentResponse, responses=READ_ERRORS
)
async def get_deal_comment(comment_id: PathId, provider: Provider) -> DealCommentResponse:
    comment = await provider.get_deal_comment().execute(DealCommentId(comment_id))
    return await comment_response(provider, comment)


@router.post(
    "/deals/{code}/comment-reads",
    status_code=status.HTTP_204_NO_CONTENT,
    responses=WRITE_ERRORS,
)
async def mark_deal_comments_read(
    code: str, body: DealCommentReadRequest, user: CurrentUser, provider: Provider
) -> None:
    ids = [DealCommentId(i) for i in body.comment_ids]
    await provider.mark_deal_comments_read().execute(code, _actor(user), ids)


@router.get("/deals/{code}/comment-counts", response_model=DealCommentCounts, responses=READ_ERRORS)
async def count_unread_deal_comments(code: str, provider: Provider) -> DealCommentCounts:
    counts = await provider.count_unread_deal_comments().execute(code)
    return DealCommentCounts.from_counts(counts)


@router.delete(
    "/deal-comments/{comment_id}", status_code=status.HTTP_204_NO_CONTENT, responses=READ_ERRORS
)
async def delete_deal_comment(comment_id: PathId, user: CurrentUser, provider: Provider) -> None:
    await provider.delete_deal_comment().execute(DealCommentId(comment_id), _actor(user))
