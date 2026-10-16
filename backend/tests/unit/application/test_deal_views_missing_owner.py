"""Owner 참조 일괄 조회 결과에 id가 빠졌을 때(R3 재리뷰 Minor 1): KeyError 대신 도메인 오류.

Port `get_refs`는 없는 id를 결과에서 뺀다. 그 빈 자리를 `UserNotFoundError`(404 계열)로 알린다.
Fake 저장소가 FK를 모사해 삭제를 막으므로, 읽기 결과에서 Owner id를 빼는 식으로 만든다.
"""

from typing import TYPE_CHECKING

import pytest

from app.application.ports.deal_repository import DealQuery
from app.domain.common.errors import NotFoundError
from app.domain.user.errors import UserNotFoundError
from tests.factories_deal import make_draft

if TYPE_CHECKING:
    from collections.abc import Collection, Mapping

    from app.domain.user.value_objects import UserId, UserRef
    from tests.unit.application.deal_env import DealEnv


def _drop_from_get_refs(env: DealEnv, monkeypatch: pytest.MonkeyPatch, gone: UserId) -> None:
    original = env.uow.users.get_refs

    async def get_refs(user_ids: Collection[UserId]) -> Mapping[UserId, UserRef]:
        found = await original(user_ids)
        return {uid: ref for uid, ref in found.items() if uid != gone}

    monkeypatch.setattr(env.uow.users, "get_refs", get_refs)


async def test_list_with_a_missing_owner_raises_user_not_found(
    env: DealEnv, monkeypatch: pytest.MonkeyPatch
) -> None:
    view = await env.new_deal(customer=make_draft(company="한빛은행", name="정민수"))
    _drop_from_get_refs(env, monkeypatch, view.item.deal.details.owner_user_id)

    with pytest.raises(UserNotFoundError):
        await env.list.execute(DealQuery())


async def test_the_owner_error_is_a_not_found_so_that_it_maps_to_404(
    env: DealEnv, monkeypatch: pytest.MonkeyPatch
) -> None:
    view = await env.new_deal(customer=make_draft(company="한빛은행", name="정민수"))
    _drop_from_get_refs(env, monkeypatch, view.item.deal.details.owner_user_id)

    with pytest.raises(NotFoundError):
        await env.list.execute(DealQuery())


async def test_the_detail_with_a_missing_owner_raises_user_not_found(
    env: DealEnv, monkeypatch: pytest.MonkeyPatch
) -> None:
    view = await env.new_deal(customer=make_draft(company="한빛은행", name="정민수"))
    _drop_from_get_refs(env, monkeypatch, view.item.deal.details.owner_user_id)

    with pytest.raises(UserNotFoundError):
        await env.get.execute(view.item.deal.id.value)
