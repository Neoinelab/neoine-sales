"""생존·준비 확인(PL-027~PL-029): 로그인 없이 부르는 `/healthz`·`/readyz`.

의존 자원(DB) 확인은 FakeUseCases의 `ready_error`로 성공·실패를 만든다. 실제 DB를 지나는 준비
확인은 `unit/infra/test_readiness_database.py`가 맡는다.
"""

from tests.fakes.use_cases import FakeUseCases
from tests.unit.web.platform_http import ANONYMOUS, role_clients, then_problem_is

LEAKED_TOKENS = ("probe-secret-pw", "postgresql", "127.0.0.1")


async def test_liveness_answers_200_ok_without_login() -> None:
    """생존 확인은 로그인 없이 200 ok다.

    테스트 코드: PL-027
    """
    # given: 익명
    async with role_clients() as c:
        # when: GET /healthz
        response = await c[ANONYMOUS].get("/healthz")
    # then: 200 {"status": "ok"}
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


async def test_readiness_is_200_ready_when_the_dependency_answers() -> None:
    """의존 자원이 응답하면 준비 확인은 200 ready다.

    테스트 코드: PL-028
    """
    # given: 의존 자원 확인이 성공하는 앱
    async with role_clients(FakeUseCases()) as c:
        # when: GET /readyz
        response = await c[ANONYMOUS].get("/readyz")
    # then: 200 {"status": "ready"}
    assert response.status_code == 200
    assert response.json() == {"status": "ready"}


async def test_readiness_is_503_and_hides_the_cause_when_the_dependency_fails() -> None:
    """의존 자원이 실패하면 준비 확인은 503이고 원인을 감춘다.

    테스트 코드: PL-029
    """
    # given: 접속 정보(비밀번호·호스트)를 담은 예외로 실패하는 앱
    use_cases = FakeUseCases()
    use_cases.ready_error = RuntimeError("postgresql://probe:probe-secret-pw@127.0.0.1:1/db")
    async with role_clients(use_cases) as c:
        # when: GET /readyz
        response = await c[ANONYMOUS].get("/readyz")
    # then: 503 not-ready 고정 문구이고 비밀번호·postgresql·호스트 주소가 없다
    body = then_problem_is(response, 503, "not-ready")
    assert body["detail"] == "서비스가 아직 요청을 받을 수 없습니다"
    assert not [token for token in LEAKED_TOKENS if token in response.text]
