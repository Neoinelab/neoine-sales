"""사용자 관리 API(`/api/v1/users`)의 HTTP 계약: 등록 응답·목록 조건·삭제 사유·권한·없는 경로.

FakeUseCases 위에서 라우터·스키마·오류 매핑을 확인한다(DB 없음). 규칙 판정 자체는
`unit/application/`이 맡고, 여기서는 HTTP 표현(상태 코드·헤더·키 집합·쿼리)을 본다.
"""

from typing import Any

import pytest

from app.domain.auth.principal import Role
from tests.fakes.use_cases import FakeUseCases
from tests.support.app_settings import USER_KEYS
from tests.unit.web.local_account_http import (
    PASSWORD,
    error_locations,
    local_system,
    signed_in_as,
)
from tests.unit.web.vendor_http import client_for, problem

USERS = "/api/v1/users"
ME = "/api/v1/auth/me"


def _logins(listed: dict[str, Any]) -> list[str]:
    return [u["login_id"] for u in listed["items"]]


@pytest.mark.parametrize("role", ["admin", "sales", "user"])
async def test_register_returns_201_with_location_and_the_documented_body(role: str) -> None:
    """AD 모드에서 아이디·역할로 등록하면 201과 Location·사용자가 돌아오고 등록자는 요청 admin이다.

    테스트 코드: US-001
    """
    # given: AD 모드 시스템과 로그인한 admin
    use_cases = FakeUseCases()
    async with client_for(use_cases) as http:
        me = (await http.get(ME)).json()
        # when: 아이디와 역할만으로 등록한다
        response = await http.post(USERS, json={"login_id": "kim", "role": role})
        listed = (await http.get(USERS)).json()

    # then: 201, Location, 문서화된 본문, 등록자는 요청 admin이고 목록 끝에 있다
    assert response.status_code == 201, response.text
    body = response.json()
    assert response.headers["Location"] == f"{USERS}/{body['id']}"
    assert set(body) == USER_KEYS
    assert (body["login_id"], body["role"], body["status"]) == ("kim", role, "active")
    assert body["created_by"]["id"] == me["user_id"]
    assert (body["last_login_at"], body["deleted_at"], body["delete_reason"]) == (None, None, None)
    assert _logins(listed)[-1] == "kim"


@pytest.mark.parametrize(
    "body",
    [
        {"role": "sales"},
        {"login_id": "kim"},
        {"login_id": "kim", "role": "superuser"},
        {"login_id": "kim", "role": None},
        {"login_id": 123, "role": "sales"},
        {"login_id": "kim", "role": "sales", "nickname": "k"},
        {"login_id": "kim", "role": "sales", "password": "x" * 257},
    ],
)
async def test_register_with_an_invalid_body_is_422_request_validation(
    body: dict[str, Any],
) -> None:
    """필수 값 누락·잘못된 역할·모르는 필드·너무 긴 비밀번호는 422 request-validation이다.

    테스트 코드: US-016
    """
    # given: 로그인한 admin
    use_cases = FakeUseCases()
    async with client_for(use_cases) as http:
        # when: 틀린 본문으로 등록한다
        response = await http.post(USERS, json=body)
        listed = (await http.get(USERS)).json()

    # then: 422 request-validation이고 사용자가 늘지 않는다
    problem(response, 422, "request-validation")
    assert _logins(listed) == ["root"]


@pytest.mark.parametrize("password", ["", "   ", "a\x00b"])
async def test_register_with_an_empty_or_nul_password_is_422_on_the_password(
    password: str,
) -> None:
    """local 모드에서 빈 값·NUL 비밀번호는 422이고 오류 위치가 password다.

    테스트 코드: US-021
    """
    # given: local 모드와 로그인한 admin
    use_cases = FakeUseCases()
    await local_system(use_cases)
    async with client_for(use_cases) as http:
        # when: 빈 값 또는 NUL이 든 비밀번호로 등록한다
        response = await http.post(
            USERS,
            json={
                "login_id": "kim",
                "role": "sales",
                "display_name": "김영업",
                "password": password,
            },
        )
        listed = (await http.get(USERS)).json()

    # then: 422 invalid-value, 위치 password, 사용자가 늘지 않는다
    body = problem(response, 422, "invalid-value")
    assert error_locations(body) == [["password"]]
    assert _logins(listed) == ["root"]


@pytest.mark.parametrize(
    ("query", "expected"),
    [
        ("", ["kim", "root"]),
        ("?status=active", ["kim", "root"]),
        ("?status=resigned", ["gone"]),
        ("?status=all", ["gone", "kim", "root"]),
    ],
)
async def test_list_status_filter_selects_active_resigned_or_everyone(
    query: str, expected: list[str]
) -> None:
    """status를 주지 않으면 재직자만, resigned는 퇴사자만, all은 모두 등록 순서로 보인다.

    테스트 코드: US-023, US-024, US-025
    """
    # given: 퇴사한 gone과 재직 kim, 그 뒤에 로그인한 admin root
    use_cases = FakeUseCases()
    gone = await use_cases.seed_user("gone", Role.SALES)
    await use_cases.resign_user(gone.id)
    await use_cases.seed_user("kim", Role.USER)
    async with client_for(use_cases) as http:
        # when: status 조건을 붙여 목록을 읽는다
        response = await http.get(f"{USERS}{query}")

    # then: 조건에 맞는 사용자가 등록 순서로 나오고 퇴사자는 퇴사 시각·사유를 가진다
    assert response.status_code == 200, response.text
    items = response.json()["items"]
    assert [u["login_id"] for u in items] == expected
    for item in items:
        if item["login_id"] == "gone":
            assert item["status"] == "resigned"
            assert item["delete_reason"] == "resigned"
            assert item["deleted_at"] is not None
        else:
            assert (item["status"], item["deleted_at"], item["delete_reason"]) == (
                "active",
                None,
                None,
            )


async def test_list_returns_the_requested_offset_and_limit_with_one_page() -> None:
    """offset·limit으로 한 페이지를 받고 요청한 값이 그대로 돌아온다.

    테스트 코드: US-026
    """
    # given: 사용자 둘과 로그인한 admin
    use_cases = FakeUseCases()
    await use_cases.seed_user("amy", Role.USER)
    await use_cases.seed_user("bob", Role.USER)
    async with client_for(use_cases) as http:
        # when: offset 1, limit 1로 읽고, 조건 없이도 읽는다
        paged = await http.get(f"{USERS}?status=all&offset=1&limit=1")
        default = await http.get(USERS)

    # then: 둘째 사용자 한 명과 요청 값이 돌아오고, 기본값은 0과 50이다
    assert paged.status_code == 200, paged.text
    assert [u["login_id"] for u in paged.json()["items"]] == ["bob"]
    assert (paged.json()["offset"], paged.json()["limit"]) == (1, 1)
    assert (default.json()["offset"], default.json()["limit"]) == (0, 50)


@pytest.mark.parametrize(
    "query", ["offset=-1", "limit=0", "limit=201", "offset=x", "status=bogus", "status=ALL"]
)
async def test_list_with_out_of_range_paging_or_unknown_status_is_422(query: str) -> None:
    """범위 밖 페이지 값이나 알 수 없는 상태 값은 422 request-validation이다.

    테스트 코드: US-027
    """
    # given: 로그인한 admin
    async with client_for(FakeUseCases()) as http:
        # when: 틀린 쿼리로 목록을 읽는다
        response = await http.get(f"{USERS}?{query}")

    # then: 422 request-validation이다
    problem(response, 422, "request-validation")


async def test_list_items_carry_only_the_documented_fields_and_no_password_values() -> None:
    """목록 항목은 문서화된 필드만 담고 비밀번호 관련 값이 없다.

    테스트 코드: US-028
    """
    # given: 비밀번호 해시가 있는 local 사용자와 로그인한 admin
    use_cases = FakeUseCases()
    await local_system(use_cases)
    await use_cases.seed_local_user("kim", PASSWORD, display_name="김영업")
    async with client_for(use_cases) as http:
        # when: 목록을 읽는다
        response = await http.get(USERS)

    # then: 모든 항목의 키가 문서와 같고 비밀번호·해시 문자열이 응답에 없다
    assert response.status_code == 200, response.text
    assert all(set(item) == USER_KEYS for item in response.json()["items"])
    assert PASSWORD not in response.text
    assert "hash" not in response.text.lower()
    assert "password" not in response.text.lower()


async def test_list_shows_last_login_for_signed_in_users_and_null_for_the_others() -> None:
    """로그인한 사용자는 마지막 로그인 시각이 있고 로그인한 적 없는 사용자는 null이다.

    테스트 코드: US-029
    """
    # given: 로그인한 적 없는 kim과 로그인한 admin root
    use_cases = FakeUseCases()
    await use_cases.seed_user("kim", Role.USER)
    async with client_for(use_cases) as http:
        # when: 목록을 읽는다
        items = (await http.get(USERS)).json()["items"]

    # then: root는 시각이 있고 kim은 null이다
    last_login = {u["login_id"]: u["last_login_at"] for u in items}
    assert last_login["root"] is not None
    assert last_login["kim"] is None


async def test_list_labels_the_creator_of_a_resigned_admin_with_the_resigned_suffix() -> None:
    """퇴사한 admin이 등록한 사용자의 등록자는 (퇴사) 표시와 함께 보인다.

    테스트 코드: US-030
    """
    # given: boss가 kim을 등록한 뒤 boss가 퇴사 처리된 상태
    use_cases = FakeUseCases()
    async with signed_in_as(use_cases, "boss", Role.ADMIN) as boss_http:
        registered = await boss_http.post(USERS, json={"login_id": "kim", "role": "sales"})
    assert registered.status_code == 201, registered.text
    await use_cases.resign_user(await use_cases.user_id_of("boss"))
    async with client_for(use_cases) as http:
        # when: 다른 admin이 모든 상태의 목록을 읽는다
        items = (await http.get(f"{USERS}?status=all")).json()["items"]

    # then: kim의 등록자 참조가 퇴사 표시와 (퇴사) 라벨을 가진다
    creator = next(u for u in items if u["login_id"] == "kim")["created_by"]
    assert (creator["name"], creator["resigned"], creator["label"]) == (
        "사용자 boss",
        True,
        "사용자 boss(퇴사)",
    )


async def test_delete_reports_the_outcome_and_accepts_the_resigned_reason() -> None:
    """reason=resigned를 받고, 생략해도 같다. 연결이 없으면 deleted가 돌아온다.

    테스트 코드: US-062
    """
    # given: 연결이 없는 사용자 둘
    use_cases = FakeUseCases()
    amy = await use_cases.seed_user("amy", Role.SALES)
    bob = await use_cases.seed_user("bob", Role.SALES)
    async with client_for(use_cases) as http:
        # when: reason을 주고, 그리고 생략하고 삭제한다
        with_reason = await http.delete(f"{USERS}/{amy.id}?reason=resigned")
        without_reason = await http.delete(f"{USERS}/{bob.id}")

    # then: 둘 다 200이고 결과는 deleted다
    assert with_reason.status_code == without_reason.status_code == 200
    assert with_reason.json() == without_reason.json() == {"outcome": "deleted"}


@pytest.mark.parametrize("reason", ["fired", "", "RESIGNED"])
async def test_delete_with_an_unknown_reason_is_422_and_keeps_the_user(reason: str) -> None:
    """알 수 없는 reason은 422 request-validation이고 사용자는 그대로다.

    테스트 코드: US-062
    """
    # given: 사용자 kim
    use_cases = FakeUseCases()
    kim = await use_cases.seed_user("kim", Role.SALES)
    async with client_for(use_cases) as http:
        # when: 알 수 없는 사유로 삭제한다
        response = await http.delete(f"{USERS}/{kim.id}?reason={reason}")
        listed = (await http.get(USERS)).json()

    # then: 422 request-validation이고 kim은 재직 그대로다
    problem(response, 422, "request-validation")
    assert "kim" in _logins(listed)


@pytest.mark.parametrize("bad_id", ["not-an-id", "abc", "1.5"])
async def test_delete_with_a_malformed_user_id_is_422_request_validation(bad_id: str) -> None:
    """정수가 아닌 사용자 id로 삭제하면 422 request-validation이다."""
    # given: 로그인한 admin
    use_cases = FakeUseCases()
    async with client_for(use_cases) as http:
        # when: 정수 형식이 아닌 id로 삭제한다
        response = await http.delete(f"{USERS}/{bad_id}")

    # then: 422 request-validation이다
    problem(response, 422, "request-validation")


def _admin_calls(target: object) -> list[tuple[str, str, dict[str, Any] | None]]:
    return [
        ("GET", USERS, None),
        ("POST", USERS, {"login_id": "new", "role": "sales"}),
        ("PATCH", f"{USERS}/{target}", {"phone": "02-123-4567"}),
        ("PUT", f"{USERS}/{target}/role", {"role": "admin"}),
        ("PUT", f"{USERS}/{target}/password", {"password": "Fresh-passw0rd"}),
        ("DELETE", f"{USERS}/{target}", None),
    ]


@pytest.mark.parametrize("role", [Role.SALES, Role.USER])
@pytest.mark.parametrize("call", range(6))
async def test_non_admins_get_403_on_every_user_management_api_and_nothing_changes(
    role: Role, call: int
) -> None:
    """admin이 아니면 사용자 관리 API는 403이고 대상은 바뀌지 않는다.

    테스트 코드: US-075
    """
    # given: sales kim과 두 종류의 로그인(대상 admin 관찰용, 요청자)
    use_cases = FakeUseCases()
    kim = await use_cases.seed_user("kim", Role.SALES)
    method, url, body = _admin_calls(kim.id)[call]
    async with client_for(use_cases, role=role) as http, client_for(use_cases) as admin:
        before = (await admin.get(f"{USERS}?status=all")).json()
        # when: admin이 아닌 사용자가 호출한다
        response = await http.request(method, url, json=body)
        after = (await admin.get(f"{USERS}?status=all")).json()

    # then: 403 forbidden(관리자 문구)이고 사용자 목록은 그대로다
    detail = problem(response, 403, "forbidden")["detail"]
    assert "관리자" in str(detail)
    assert after == before


@pytest.mark.parametrize("method", ["GET", "PUT", "POST"])
async def test_a_single_user_resource_has_no_read_or_replace_api(method: str) -> None:
    """사용자 한 명을 읽거나 통째로 바꾸는 API는 없어 405다.

    테스트 코드: US-076
    """
    # given: 사용자 kim과 로그인한 admin
    use_cases = FakeUseCases()
    kim = await use_cases.seed_user("kim", Role.SALES)
    async with client_for(use_cases) as http:
        before = (await http.get(f"{USERS}?status=all")).json()
        # when: /users/{id}를 읽거나 통째로 바꾸려 한다
        response = await http.request(method, f"{USERS}/{kim.id}", json={"role": "user"})
        after = (await http.get(f"{USERS}?status=all")).json()

    # then: 405이고 사용자는 그대로다
    assert response.status_code == 405, response.text
    assert after == before
