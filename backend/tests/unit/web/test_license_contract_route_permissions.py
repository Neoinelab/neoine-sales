"""계약 라우터의 권한(AC15·AC16).

읽기는 모든 역할, 쓰기는 sales·admin, 삭제는 admin만, 미로그인은 401.

쓰기 경로의 user 403은 본문·레코드 검사보다 먼저다. 계약 삭제는 admin 판정(403)이 존재 확인(404)
보다 먼저다(2026-11-09 결정): 없는 계약 404는 admin에게만 나온다.
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
    """user는 어떤 쓰기도 할 수 없고 아무것도 바뀌지 않는다.

    테스트 코드: LC-082
    """
    # given: 계약과 첨부, user·admin 요청자
    use_cases = FakeUseCases()
    contract = await seed_contract(use_cases)
    # when: user가 수정·발급·갱신·종료·삭제·첨부 삭제·업로드를 요청한다
    async with clients(use_cases, {"viewer": Role.USER, "boss": Role.ADMIN}) as c:
        responses = [
            await c["viewer"].request(method, url, json=body)
            for method, url, body in _writes(contract.id)
        ]
        upload = await c["viewer"].post(
            f"{BASE}/{contract.id}/attachments", files={"file": ("a.pdf", b"x", "application/pdf")}
        )
        detail = (await c["boss"].get(f"{BASE}/{contract.id}")).json()

    # then: 모두 403 읽기 전용 문구이고 계약은 not_issued·첨부 0 그대로
    for response in [*responses, upload]:
        assert problem(response, 403, "forbidden")["detail"] == READ_ONLY
    assert detail["status"] == "not_issued"
    assert detail["attachment_count"] == 0


async def test_a_read_only_user_is_forbidden_before_the_body_or_the_record_is_checked() -> None:
    """user의 쓰기는 본문 검증·존재 확인보다 먼저 403이다.

    테스트 코드: LC-082
    """
    # when: 엉터리 본문, 없는 id의 종료, 없는 id의 삭제를 요청한다
    async with clients(FakeUseCases(), {"viewer": Role.USER}) as c:
        garbage = await c["viewer"].put(f"{BASE}/{new_id()}", json={"unexpected": ["garbage"]})
        absent = await c["viewer"].post(f"{BASE}/{new_id()}/end")
        delete = await c["viewer"].delete(f"{BASE}/{new_id()}")

    # then: 모두 403 forbidden
    for response in (garbage, absent, delete):
        problem(response, 403, "forbidden")


@pytest.mark.parametrize("role", [Role.USER, Role.SALES, Role.ADMIN])
async def test_every_role_may_read_the_list_the_detail_and_the_attachment_list(
    role: Role,
) -> None:
    """모든 역할이 목록·상세·첨부 목록을 읽을 수 있다.

    테스트 코드: LC-082
    """
    # given: 계약
    use_cases = FakeUseCases()
    contract = await seed_contract(use_cases)
    # when: 각 역할이 세 조회를 요청한다
    async with clients(use_cases, {"someone": role}) as c:
        listed = await c["someone"].get(BASE)
        detail = await c["someone"].get(f"{BASE}/{contract.id}")
        files = await c["someone"].get(f"{BASE}/{contract.id}/attachments")

    # then: 모두 200
    assert listed.status_code == 200, listed.text
    assert detail.status_code == 200, detail.text
    assert files.status_code == 200, files.text


@pytest.mark.parametrize("role", [Role.SALES, Role.ADMIN])
async def test_sales_and_admin_may_change_the_contract_fields_and_end_it(role: Role) -> None:
    """sales와 admin은 계약 칸 수정과 종료를 할 수 있다.

    테스트 코드: LC-082
    """
    # given: 계약
    use_cases = FakeUseCases()
    contract = await seed_contract(use_cases)
    # when: 수정과 종료를 요청한다
    async with clients(use_cases, {"someone": role}) as c:
        updated = await c["someone"].put(f"{BASE}/{contract.id}", json={"tech_owner": "이기술"})
        ended = await c["someone"].post(f"{BASE}/{contract.id}/end")

    # then: 둘 다 200이고 종료 뒤 상태는 ended
    assert updated.status_code == 200, updated.text
    assert ended.status_code == 200, ended.text
    assert ended.json()["status"] == "ended"


async def test_delete_by_admin_is_204_and_by_sales_is_403_with_the_admin_only_message() -> None:
    """삭제는 admin만 204, sales는 관리자만 문구의 403이다.

    테스트 코드: LC-059, LC-058
    """
    # given: 발급(신규) 계약
    use_cases = FakeUseCases()
    contract = await seed_contract(use_cases, status="issued_new")
    # when: sales가 삭제하고, 이어 admin이 삭제한다
    async with clients(use_cases, {"kim": Role.SALES, "boss": Role.ADMIN}) as c:
        by_sales = await c["kim"].delete(f"{BASE}/{contract.id}")
        still_there = await c["boss"].get(f"{BASE}/{contract.id}")
        by_admin = await c["boss"].delete(f"{BASE}/{contract.id}")
        gone = await c["boss"].get(f"{BASE}/{contract.id}")

    # then: sales 403(계약 그대로), admin 204(본문 없음), 이후 조회는 404
    assert problem(by_sales, 403, "forbidden")["detail"] == "계약 삭제는 관리자만 할 수 있습니다."
    assert still_there.status_code == 200
    assert by_admin.status_code == 204
    assert by_admin.content == b""
    problem(gone, 404, "not-found")


async def test_delete_of_a_missing_contract_is_403_before_404_unless_admin() -> None:
    """없는 계약의 삭제는 admin만 404이고 sales·user는 먼저 403이다.

    테스트 코드: LC-083, LC-029
    """
    # given: 존재하지 않는 계약 id와 sales·user·admin
    # when: 각자 그 id의 계약을 삭제한다
    async with clients(
        FakeUseCases(), {"kim": Role.SALES, "viewer": Role.USER, "boss": Role.ADMIN}
    ) as c:
        by_sales = await c["kim"].delete(f"{BASE}/{new_id()}")
        by_user = await c["viewer"].delete(f"{BASE}/{new_id()}")
        by_admin = await c["boss"].delete(f"{BASE}/{new_id()}")

    # then: sales 403 관리자만 문구, user 403 읽기 전용 문구, admin 404
    assert problem(by_sales, 403, "forbidden")["detail"] == "계약 삭제는 관리자만 할 수 있습니다."
    assert problem(by_user, 403, "forbidden")["detail"] == READ_ONLY
    assert problem(by_admin, 404, "not-found")["detail"] == "라이선스 계약을 찾을 수 없습니다."


async def test_unauthenticated_requests_are_401() -> None:
    """로그인하지 않은 요청은 모두 401이다.

    테스트 코드: LC-082
    """
    # when: 로그인 없이 조회와 쓰기를 요청한다
    async with clients(FakeUseCases(), {"anon": Role.USER}) as c:
        responses = [await c["anon"].get(BASE), await c["anon"].get(f"{BASE}/{new_id()}")]
        for method, url, body in _writes(new_id()):
            responses.append(await c["anon"].request(method, url, json=body))

    # then: 모두 401 unauthenticated
    for response in responses:
        problem(response, 401, "unauthenticated")
