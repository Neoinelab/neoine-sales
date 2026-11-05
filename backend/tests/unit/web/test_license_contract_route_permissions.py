"""계약 라우터의 권한(AC15·AC16).

읽기는 모든 역할, 쓰기는 sales·admin, 삭제는 admin만, 미로그인은 401.

쓰기 경로의 user 403은 본문·레코드 검사보다 먼저다. 계약 삭제는 sales도 403이지만 레코드가
없으면 404가 먼저다(없음 -> 권한 순서).
"""

from typing import Any

import pytest

from app.domain.auth.principal import Role
from tests.fakes.use_cases import FakeUseCases
from tests.support.ids import new_id
from tests.unit.web.license_contract_http import (
    ATTACHMENT_URL,
    BASE,
    READ_ONLY,
    clients,
    problem,
    seed_contract,
)

ISSUE_BODY = {"start_date": "2026-01-01", "term_amount": 1, "term_unit": "year"}


def _writes(contract_id: object) -> list[tuple[str, str, Any]]:
    return [
        ("PUT", f"{BASE}/{contract_id}", {}),
        ("POST", f"{BASE}/{contract_id}/issue", ISSUE_BODY),
        ("POST", f"{BASE}/{contract_id}/renewal", ISSUE_BODY),
        ("POST", f"{BASE}/{contract_id}/end", None),
        ("DELETE", f"{BASE}/{contract_id}", None),
        ("DELETE", ATTACHMENT_URL.format(id=contract_id), None),
    ]


async def test_a_read_only_user_cannot_write_and_nothing_changes() -> None:
    use_cases = FakeUseCases()
    contract = await seed_contract(use_cases)
    async with clients(use_cases, {"viewer": Role.USER, "boss": Role.ADMIN}) as c:
        responses = [
            await c["viewer"].request(method, url, json=body)
            for method, url, body in _writes(contract.id)
        ]
        upload = await c["viewer"].post(
            f"{BASE}/{contract.id}/attachments", files={"file": ("a.pdf", b"x", "application/pdf")}
        )
        detail = (await c["boss"].get(f"{BASE}/{contract.id}")).json()

    for response in [*responses, upload]:
        assert problem(response, 403, "forbidden")["detail"] == READ_ONLY
    assert detail["status"] == "not_issued"
    assert detail["attachment_count"] == 0


async def test_a_read_only_user_is_forbidden_before_the_body_or_the_record_is_checked() -> None:
    async with clients(FakeUseCases(), {"viewer": Role.USER}) as c:
        garbage = await c["viewer"].put(f"{BASE}/{new_id()}", json={"unexpected": ["garbage"]})
        absent = await c["viewer"].post(f"{BASE}/{new_id()}/end")
        delete = await c["viewer"].delete(f"{BASE}/{new_id()}")

    for response in (garbage, absent, delete):
        problem(response, 403, "forbidden")


@pytest.mark.parametrize("role", [Role.USER, Role.SALES, Role.ADMIN])
async def test_every_role_may_read_the_list_the_detail_and_the_attachment_list(
    role: Role,
) -> None:
    use_cases = FakeUseCases()
    contract = await seed_contract(use_cases)
    async with clients(use_cases, {"someone": role}) as c:
        listed = await c["someone"].get(BASE)
        detail = await c["someone"].get(f"{BASE}/{contract.id}")
        files = await c["someone"].get(f"{BASE}/{contract.id}/attachments")

    assert listed.status_code == 200, listed.text
    assert detail.status_code == 200, detail.text
    assert files.status_code == 200, files.text


@pytest.mark.parametrize("role", [Role.SALES, Role.ADMIN])
async def test_sales_and_admin_may_change_the_contract_fields_and_end_it(role: Role) -> None:
    use_cases = FakeUseCases()
    contract = await seed_contract(use_cases)
    async with clients(use_cases, {"someone": role}) as c:
        updated = await c["someone"].put(f"{BASE}/{contract.id}", json={"tech_owner": "이기술"})
        ended = await c["someone"].post(f"{BASE}/{contract.id}/end")

    assert updated.status_code == 200, updated.text
    assert ended.status_code == 200, ended.text
    assert ended.json()["status"] == "ended"


async def test_delete_by_admin_is_204_and_by_sales_is_403_with_the_admin_only_message() -> None:
    use_cases = FakeUseCases()
    contract = await seed_contract(use_cases, status="issued_new")
    async with clients(use_cases, {"kim": Role.SALES, "boss": Role.ADMIN}) as c:
        by_sales = await c["kim"].delete(f"{BASE}/{contract.id}")
        still_there = await c["boss"].get(f"{BASE}/{contract.id}")
        by_admin = await c["boss"].delete(f"{BASE}/{contract.id}")
        gone = await c["boss"].get(f"{BASE}/{contract.id}")

    assert problem(by_sales, 403, "forbidden")["detail"] == "계약 삭제는 관리자만 할 수 있습니다."
    assert still_there.status_code == 200
    assert by_admin.status_code == 204
    assert by_admin.content == b""
    problem(gone, 404, "not-found")


async def test_delete_of_a_missing_contract_is_404_for_sales_and_admin() -> None:
    async with clients(FakeUseCases(), {"kim": Role.SALES, "boss": Role.ADMIN}) as c:
        by_sales = await c["kim"].delete(f"{BASE}/{new_id()}")
        by_admin = await c["boss"].delete(f"{BASE}/{new_id()}")

    problem(by_sales, 404, "not-found")
    problem(by_admin, 404, "not-found")


async def test_unauthenticated_requests_are_401() -> None:
    async with clients(FakeUseCases(), {"anon": Role.USER}) as c:
        responses = [await c["anon"].get(BASE), await c["anon"].get(f"{BASE}/{new_id()}")]
        for method, url, body in _writes(new_id()):
            responses.append(await c["anon"].request(method, url, json=body))

    for response in responses:
        problem(response, 401, "unauthenticated")
