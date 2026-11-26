import pytest

from app.application.ports.directory import DirectoryUnavailableError, VerificationStage
from tests.factories_auth import BIND_ACCOUNT, BIND_PASSWORD, USER_FILTER
from tests.fakes.use_cases import FakeUseCases
from tests.unit.web.platform_http import (
    ADMIN_DENIED,
    ANONYMOUS,
    BOSS,
    CSRF_DETAIL,
    KIM,
    LOGIN_REQUIRED,
    VIEWER,
    role_clients,
    then_problem_is,
)

DIRECTORY = "/api/v1/settings/directory"
DIRECTORY_TEST = f"{DIRECTORY}/test"
STORAGE = "/api/v1/settings/storage"
STORAGE_TEST = f"{STORAGE}/test"
CONNECTION = {
    "host": "dc1.corp.test",
    "port": 636,
    "security": "ssl",
    "user_filter": USER_FILTER,
    "connect_timeout_seconds": 5,
}


def _update_body() -> dict[str, object]:
    return {**CONNECTION, "test_token": "invalid-proof", "expected_revision": 1}


def _test_body(**extra: object) -> dict[str, object]:
    return {**CONNECTION, "bind_account": BIND_ACCOUNT, "bind_password": BIND_PASSWORD, **extra}


async def _given_saved_settings() -> FakeUseCases:
    use_cases = FakeUseCases()
    await use_cases.seed_directory()
    return use_cases


# 테스트 코드: IN-034, IN-035
async def test_get_and_update_never_contain_test_credentials(
    caplog: pytest.LogCaptureFixture,
) -> None:
    use_cases = await _given_saved_settings()
    async with role_clients(use_cases) as clients:
        http = clients[BOSS]
        tested = await http.post(DIRECTORY_TEST, json=_test_body())
        assert tested.json()["success"] is True
        saved = await http.put(
            DIRECTORY,
            json={
                **CONNECTION,
                "test_token": tested.json()["test_token"],
                "expected_revision": 1,
            },
        )
        found = await http.get(DIRECTORY)
        assert (await http.get("/api/v1/auth/me")).status_code == 200
    assert saved.status_code == 200
    assert found.json() == saved.json()
    assert found.json()["revision"] == 2
    assert set(found.json()) == {
        *CONNECTION,
        "base_dn",
        "revision",
        "updated_at",
        "updated_by",
    }
    assert BIND_ACCOUNT not in found.text
    assert BIND_PASSWORD not in found.text
    assert BIND_PASSWORD not in caplog.text


@pytest.mark.parametrize("stage", ["connect", "tls", "service_bind", "base_dn"])
async def test_failures_are_sanitized_and_do_not_issue_proof(stage: str) -> None:
    use_cases = await _given_saved_settings()
    use_cases.directory.discover_fails_with = DirectoryUnavailableError(
        "private-banner",
        stage=VerificationStage(stage),
    )
    async with role_clients(use_cases) as clients:
        failed = await clients[BOSS].post(DIRECTORY_TEST, json=_test_body())
    assert failed.status_code == 200
    assert failed.json()["success"] is False
    assert failed.json()["stage"] == stage
    assert failed.json()["test_token"] is None
    assert "private-banner" not in failed.text
    assert BIND_PASSWORD not in failed.text


@pytest.mark.parametrize(
    "change",
    [
        {"bind_account": ""},
        {"bind_password": ""},
        {"port": 0},
        {"host": ""},
        {"bind_password": None},
        {"port": "636"},
        {"password": "legacy-admin-password"},
        {"expected_revision": 1},
    ],
)
async def test_invalid_test_requests_do_not_reach_ldap(change: dict[str, object]) -> None:
    use_cases = await _given_saved_settings()
    async with role_clients(use_cases) as clients:
        response = await clients[BOSS].post(DIRECTORY_TEST, json=_test_body(**change))
    assert response.status_code == 422
    assert use_cases.directory.discover_calls == []


async def test_update_requires_a_proof_and_checks_revision() -> None:
    use_cases = await _given_saved_settings()
    async with role_clients(use_cases) as clients:
        http = clients[BOSS]
        invalid = await http.put(DIRECTORY, json=_update_body())
        assert invalid.status_code == 422
        tested = await http.post(DIRECTORY_TEST, json=_test_body())
        stale = await http.put(
            DIRECTORY,
            json={
                **CONNECTION,
                "test_token": tested.json()["test_token"],
                "expected_revision": 2,
            },
        )
        assert stale.status_code == 409
        assert (await http.get(DIRECTORY)).json()["revision"] == 1


_SIX_ROUTES = [
    ("get", DIRECTORY),
    ("put", DIRECTORY),
    ("post", DIRECTORY_TEST),
    ("get", STORAGE),
    ("put", STORAGE),
    ("post", STORAGE_TEST),
]


async def test_only_admin_may_use_the_six_integration_routes() -> None:
    """연동 설정 6개 경로는 admin만 쓰고 sales·user는 본문 검사 전에 403, 미인증은 401이다.

    테스트 코드: IN-040
    """
    # given: 예시 AD 설정과 저장 위치
    use_cases = await _given_saved_settings()
    await use_cases.seed_storage("/data/a")
    async with role_clients(use_cases) as c:
        # when: 각 역할이 6개 경로를 (형식이 틀린 본문으로) 부른다
        rejected = {
            role: [
                await c[role].request(
                    method, path, json={"garbage": 1} if method != "get" else None
                )
                for method, path in _SIX_ROUTES
            ]
            for role in (KIM, VIEWER)
        }
        anonymous = [
            await c[ANONYMOUS].request(method, path, json={"x": 1} if method != "get" else None)
            for method, path in _SIX_ROUTES
        ]
        stored = await c[BOSS].get(STORAGE)

    # then: sales·user는 403 forbidden 관리자 문구, 미인증은 401, 저장 위치는 그대로
    for responses in rejected.values():
        for response in responses:
            assert then_problem_is(response, 403, "forbidden")["detail"] == ADMIN_DENIED
    for response in anonymous:
        assert then_problem_is(response, 401, "unauthenticated")["detail"] == LOGIN_REQUIRED
    assert stored.json()["path"] == "/data/a"


async def test_changes_without_the_csrf_header_are_403_and_change_nothing() -> None:
    """AD 저장·연결 테스트·저장 위치 변경은 CSRF 헤더가 없으면 403 csrf이고 아무것도 바뀌지 않는다.

    테스트 코드: IN-041
    """
    # given: 예시 AD 설정, 저장 위치, 헤더 없는 BOSS 클라이언트
    use_cases = await _given_saved_settings()
    await use_cases.seed_storage("/data/a")
    async with role_clients(use_cases, csrf=False) as c:
        # when: 헤더 없이 AD 저장, 연결 테스트, 저장 위치 변경을 부른다
        responses = [
            await c[BOSS].put(DIRECTORY, json=_update_body()),
            await c[BOSS].post(DIRECTORY_TEST, json=_test_body()),
            await c[BOSS].put(STORAGE, json={"path": "/data/b"}),
        ]
        directory = await c[BOSS].get(DIRECTORY)
        storage = await c[BOSS].get(STORAGE)

    # then: 모두 403 csrf, AD 호출 0회, 설정과 위치는 그대로
    for response in responses:
        assert then_problem_is(response, 403, "csrf")["detail"] == CSRF_DETAIL
    assert use_cases.directory.discover_calls == []
    assert (directory.json()["revision"], storage.json()["path"]) == (1, "/data/a")
