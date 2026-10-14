"""Deal 이력(활동) API: 생성·조회·수정·삭제와 Deal 삭제 정책(AC1, 5~8, 11, 12)."""

from typing import TYPE_CHECKING
from uuid import uuid4

from tests.e2e.payloads import action_payload, customer_payload, deal_payload
from tests.support.user_ids import ACTOR_ID

if TYPE_CHECKING:
    from httpx import AsyncClient

DEALS = "/api/v1/deals"
ACTIONS = "/api/v1/deal-actions"
PROBLEM = "application/problem+json"
IN_USE_DETAIL = "활동 또는 단계 변경 이력이 있어 삭제할 수 없습니다"


async def _deal(client: AsyncClient, code: str = "DEAL-001") -> str:
    customer = (await client.post("/api/v1/customers", json=customer_payload())).json()
    response = await client.post(DEALS, json=deal_payload(customer["id"], code=code))
    return str(response.json()["id"])


async def _create(client: AsyncClient, deal_id: str, **overrides: object) -> dict[str, object]:
    response = await client.post(f"{DEALS}/{deal_id}/actions", json=action_payload(**overrides))
    assert response.status_code == 201, response.text
    body: dict[str, object] = response.json()
    return body


async def test_create_returns_new_fields_and_no_legacy_fields(client: AsyncClient) -> None:
    deal_id = await _deal(client)

    response = await client.post(f"{DEALS}/{deal_id}/actions", json=action_payload())

    body = response.json()
    assert response.status_code == 201
    assert response.headers["location"] == f"{ACTIONS}/{body['id']}"
    assert body["deal_id"] == deal_id
    assert body["action_type"] == "meeting"
    assert body["action"] == "킥오프 미팅"
    assert body["next_action"] == "요구사항 문서 전달"
    assert body["due_date"] == "2026-03-10"
    assert body["memo"] == "요구사항 정리"
    assert body["actor"] == {
        "id": str(ACTOR_ID),
        "name": "actor",
        "resigned": False,
        "label": "actor",
    }
    assert "actor_user_id" not in body
    assert body["acted_at"].startswith("2026-03-02T10:00:00")
    assert body["created_at"].startswith("2026-01-01T09:00:")
    assert body["updated_at"]
    assert "title" not in body
    assert "content" not in body


async def test_create_without_memo_defaults_to_an_empty_memo(client: AsyncClient) -> None:
    deal_id = await _deal(client)
    payload = action_payload()
    del payload["memo"]

    response = await client.post(f"{DEALS}/{deal_id}/actions", json=payload)

    assert response.status_code == 201
    assert response.json()["memo"] == ""


async def test_create_for_an_unknown_deal_is_a_404(client: AsyncClient) -> None:
    response = await client.post(f"{DEALS}/{uuid4()}/actions", json=action_payload())

    assert response.status_code == 404
    assert response.json()["type"].endswith("not-found")


async def test_one_deal_holds_many_actions_listed_latest_first(client: AsyncClient) -> None:
    deal_id = await _deal(client)
    await _create(client, deal_id, action="먼저", acted_at="2026-03-01T10:00:00+09:00")
    await _create(client, deal_id, action="나중", acted_at="2026-03-05T10:00:00+09:00")
    await _create(client, deal_id, action="중간", acted_at="2026-03-03T10:00:00+09:00")

    page = (await client.get(f"{DEALS}/{deal_id}/actions")).json()

    assert [item["action"] for item in page["items"]] == ["나중", "중간", "먼저"]
    assert (page["offset"], page["limit"]) == (0, 50)
    assert (await client.get(f"{DEALS}/{uuid4()}/actions")).status_code == 404


async def test_get_returns_new_fields(client: AsyncClient) -> None:
    created = await _create(client, await _deal(client))

    response = await client.get(f"{ACTIONS}/{created['id']}")

    assert response.status_code == 200
    assert response.json() == created
    assert response.json()["next_action"] == "요구사항 문서 전달"
    assert (await client.get(f"{ACTIONS}/{uuid4()}")).status_code == 404


async def test_put_replaces_every_field_and_touches_updated_at(client: AsyncClient) -> None:
    created = await _create(client, await _deal(client))

    updated = await client.put(
        f"{ACTIONS}/{created['id']}",
        json=action_payload(
            action_type="proposal",
            action="제안 발표",
            next_action="견적 회신",
            due_date="2026-04-01",
            memo="",
        ),
    )

    body = updated.json()
    assert updated.status_code == 200
    assert (body["action"], body["next_action"], body["due_date"]) == (
        "제안 발표",
        "견적 회신",
        "2026-04-01",
    )
    assert body["memo"] == ""
    assert body["action_type"] == "proposal"
    assert body["deal_id"] == created["deal_id"]
    assert body["created_at"] == created["created_at"]
    assert body["updated_at"] > created["updated_at"]


async def test_put_requires_the_required_fields(client: AsyncClient) -> None:
    created = await _create(client, await _deal(client))

    for field in ("action", "next_action", "due_date"):
        payload = action_payload()
        del payload[field]

        response = await client.put(f"{ACTIONS}/{created['id']}", json=payload)

        assert response.status_code == 422, field
        assert response.json()["type"].endswith("request-validation")


async def test_update_cannot_send_a_different_deal(client: AsyncClient) -> None:
    created = await _create(client, await _deal(client))

    response = await client.put(
        f"{ACTIONS}/{created['id']}", json=action_payload(deal_id=str(uuid4()))
    )

    assert response.status_code == 422  # deal_id는 허용되지 않는 필드


async def test_delete_action_is_physical(client: AsyncClient) -> None:
    deal_id = await _deal(client)
    created = await _create(client, deal_id)

    assert (await client.delete(f"{ACTIONS}/{created['id']}")).status_code == 204

    assert (await client.get(f"{ACTIONS}/{created['id']}")).status_code == 404
    assert (await client.get(f"{DEALS}/{deal_id}/actions")).json()["items"] == []
    assert (await client.delete(f"{ACTIONS}/{created['id']}")).status_code == 404


async def test_delete_deal_without_actions_is_204_and_frees_the_code(client: AsyncClient) -> None:
    deal_id = await _deal(client)

    assert (await client.delete(f"{DEALS}/{deal_id}")).status_code == 204

    assert (await client.get(f"{DEALS}/{deal_id}")).status_code == 404
    assert (await client.get(f"{DEALS}/{deal_id}/actions")).status_code == 404
    assert (await _deal(client, "DEAL-001")) != deal_id  # 같은 코드로 다시 등록된다


async def test_delete_deal_with_actions_is_409_invalid_state(client: AsyncClient) -> None:
    deal_id = await _deal(client)
    created = await _create(client, deal_id)

    response = await client.delete(f"{DEALS}/{deal_id}")

    assert response.status_code == 409
    assert response.headers["content-type"].startswith(PROBLEM)
    assert response.json()["type"].endswith("invalid-state")
    assert IN_USE_DETAIL in response.json()["detail"]
    assert (await client.get(f"{DEALS}/{deal_id}")).status_code == 200
    assert (await client.get(f"{ACTIONS}/{created['id']}")).status_code == 200


async def test_delete_deal_after_removing_actions_succeeds(client: AsyncClient) -> None:
    deal_id = await _deal(client)
    first, second = await _create(client, deal_id), await _create(client, deal_id, action="후속")
    await client.delete(f"{ACTIONS}/{first['id']}")
    assert (await client.delete(f"{DEALS}/{deal_id}")).status_code == 409
    await client.delete(f"{ACTIONS}/{second['id']}")

    assert (await client.delete(f"{DEALS}/{deal_id}")).status_code == 204
    assert (await client.get(f"{DEALS}/{deal_id}")).status_code == 404
