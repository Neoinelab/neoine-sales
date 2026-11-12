"""인증 라우터의 local 모드: 설정 상태, 인증 방식 선택, 최초 설정, 로그인.

FakeUseCases 위에서 라우터·스키마·오류 매핑을 확인한다.
유스케이스 규칙은 `tests/unit/application/`의
Fake 단위 테스트가 본다.
"""

from typing import Any

import pytest

from app.application.auth.messages import LOGIN_FAILED
from app.domain.auth.mode import AuthMode
from app.domain.auth.principal import Role
from tests.fakes.auth_stack import MAX_PER_ACCOUNT
from tests.fakes.use_cases import FakeUseCases
from tests.unit.web.local_account_http import (
    CONFIG,
    LOGIN,
    ME,
    PASSWORD,
    SETUP,
    SETUP_MODE,
    anonymous,
    local_system,
    problem,
)

FLAGS = {
    "directory_login",
    "needs_directory_setup",
    "needs_storage_setup",
    "needs_admin_setup",
    "auth_mode",
}


def _setup_body(**overrides: Any) -> dict[str, Any]:  # noqa: ANN401
    return {"login_id": "kim", "password": PASSWORD, "display_name": "김관리", **overrides}


# ---- GET /auth/config ----


async def test_auth_config_has_exactly_the_setup_keys_and_no_mode() -> None:
    """새 시스템의 /auth/config 응답 키는 진행 상태 다섯 개뿐이고 방식은 아직 없다."""
    # given: 새 시스템이다
    async with anonymous(FakeUseCases()) as http:
        # when: /auth/config를 조회한다
        body = (await http.get(CONFIG)).json()

    # then: 키는 FLAGS뿐이고 auth_mode는 null이다
    assert set(body) == FLAGS
    assert body["auth_mode"] is None
    assert (body["needs_directory_setup"], body["needs_storage_setup"]) == (True, True)


# ---- PUT /auth/setup/auth-mode ----


async def test_choosing_a_mode_needs_the_csrf_header() -> None:
    """인증 방식 선택은 CSRF 헤더가 없으면 403이다."""
    # given: 새 시스템
    async with anonymous(FakeUseCases()) as http:
        # when: CSRF 헤더 없이 local 방식을 선택한다
        response = await http.request(
            "PUT", SETUP_MODE, json={"mode": "local"}, headers={"X-Requested-With": ""}
        )

    # then: 403 csrf다
    problem(response, 403, "csrf")


# ---- PUT /auth/setup/storage 선행 조건 ----


# ---- POST /auth/setup ----


async def test_local_setup_creates_the_admin_and_signs_in() -> None:
    """local 첫 admin 등록은 응답에 비밀번호 없이 세션 쿠키를 심고 로그인 상태가 된다."""
    # given: local 방식에 저장 위치가 등록되었다
    use_cases = FakeUseCases()
    await local_system(use_cases)
    async with anonymous(use_cases) as http:
        # when: 프로필을 담아 첫 admin을 등록하고 내 정보·진행 상태를 조회한다
        response = await http.post(
            SETUP, json=_setup_body(email="Kim@Corp.test", phone="010-1234-5678")
        )
        me = await http.get(ME)
        config = (await http.get(CONFIG)).json()

    # then: 200, 쿠키, /auth/me 200, 진행 상태 끝남, AD 호출 없음
    assert response.status_code == 200, response.text
    body = response.json()
    assert (body["subject"], body["role"], body["name"], body["email"]) == (
        "kim",
        "admin",
        "김관리",
        "kim@corp.test",
    )
    assert "password" not in response.text
    assert "neoine_session" in response.headers["set-cookie"]
    assert me.status_code == 200
    assert (config["needs_admin_setup"], config["needs_storage_setup"]) == (False, False)
    assert use_cases.directory.authenticate_calls == []


async def test_setup_password_is_a_required_field() -> None:
    """비밀번호 없이 보낸 첫 admin 등록은 422 request-validation이다."""
    # given: local 방식에 저장 위치가 등록되었다
    use_cases = FakeUseCases()
    await local_system(use_cases)
    async with anonymous(use_cases) as http:
        # when: password 키 없이 등록한다
        response = await http.post(SETUP, json={"login_id": "kim", "display_name": "김관리"})

    # then: 422 request-validation이다
    problem(response, 422, "request-validation")


# ---- POST /auth/login ----


async def _local_login_system(use_cases: FakeUseCases) -> None:
    await use_cases.seed_auth_mode(AuthMode.LOCAL)
    await use_cases.seed_local_user("kim", PASSWORD, Role.SALES, display_name="김영업")


async def test_local_login_with_the_right_password_is_200_without_a_warning() -> None:
    """맞는 비밀번호로 local 로그인하면 경고 없이 200이다."""
    # given: local 방식에 kim(sales) 계정이 있다
    use_cases = FakeUseCases()
    await _local_login_system(use_cases)
    async with anonymous(use_cases) as http:
        # when: kim으로 로그인하고 내 정보를 조회한다
        response = await http.post(LOGIN, json={"login_id": "kim", "password": PASSWORD})
        me = await http.get(ME)

    # then: 200, 경고 없음, 쿠키, 내 정보 200, AD 호출 없음
    assert response.status_code == 200, response.text
    body = response.json()
    assert (body["subject"], body["role"], body["directory_warning"]) == ("kim", "sales", None)
    assert "neoine_session" in response.headers["set-cookie"]
    assert me.status_code == 200
    assert use_cases.directory.authenticate_calls == []


@pytest.mark.parametrize("login_id", ["kim", "ghost"])
async def test_local_login_wrong_password_and_unknown_id_get_the_same_401(login_id: str) -> None:
    """틀린 비밀번호와 없는 아이디는 같은 401을 받는다."""
    # given: local 방식에 kim(sales) 계정이 있다
    use_cases = FakeUseCases()
    await _local_login_system(use_cases)
    async with anonymous(use_cases) as http:
        # when: 틀린 비밀번호로 로그인한다
        response = await http.post(LOGIN, json={"login_id": login_id, "password": "wrong-pass-1"})

    # then: 같은 문구의 401이고 쿠키가 없다
    body = problem(response, 401, "unauthenticated")
    assert body["detail"] == LOGIN_FAILED
    assert "neoine_session" not in response.headers.get("set-cookie", "")


async def test_local_login_of_a_resigned_user_is_the_same_401() -> None:
    """퇴사한 사용자의 로그인은 같은 401이다."""
    # given: local 방식에 퇴사 처리된 gone 계정이 있다
    use_cases = FakeUseCases()
    await use_cases.seed_auth_mode(AuthMode.LOCAL)
    gone = await use_cases.seed_local_user("gone", PASSWORD)
    await use_cases.resign_user(gone.id)
    async with anonymous(use_cases) as http:
        # when: gone으로 로그인한다
        response = await http.post(LOGIN, json={"login_id": "gone", "password": PASSWORD})

    # then: 같은 문구의 401이다
    assert problem(response, 401, "unauthenticated")["detail"] == LOGIN_FAILED


async def test_local_login_failures_lock_the_account_with_429() -> None:
    """로그인 실패가 쌓이면 계정이 잠겨 429다."""
    # given: local 방식에 kim(sales) 계정이 있다
    use_cases = FakeUseCases()
    await _local_login_system(use_cases)
    async with anonymous(use_cases) as http:
        # when: 틀린 비밀번호로 한도까지 실패한 뒤 맞는 비밀번호로 로그인한다
        for _ in range(MAX_PER_ACCOUNT):
            await http.post(LOGIN, json={"login_id": "kim", "password": "wrong-pass-1"})
        locked = await http.post(LOGIN, json={"login_id": "kim", "password": PASSWORD})

    # then: 429 too-many-attempts다
    problem(locked, 429, "too-many-attempts")
