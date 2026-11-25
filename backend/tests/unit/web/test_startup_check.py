"""앱 기동 검사(AU-R7c) 연결: lifespan이 요청을 받기 전, 스케줄러를 시작하기 전에
`check_startup()`을 부른다.

AU-104. 유스케이스 규칙(AU-103·AU-105)은 `tests/unit/application/test_check_ad_login_domain.py`다.
"""

import asyncio
import logging
from typing import TYPE_CHECKING, Any

import pytest
from fastapi.testclient import TestClient

import app.main as main_module
from app.domain.directory.errors import DirectoryLoginDomainMissingError
from app.main import create_app
from tests.fakes.use_cases import FakeUseCases
from tests.support.app_settings import make_settings

if TYPE_CHECKING:
    from collections.abc import Iterator

UNUSED_DATABASE_URL = "postgresql+asyncpg://user:pw@localhost:5432/none"  # 접속하지 않는다
MISSING_TEXT = (
    "인증 방식이 AD 연동인데 서버 환경변수 APP_AD_LOGIN_DOMAIN이 설정되지 않았습니다. "
    "값을 설정한 뒤 다시 시작하세요"
)


def test_a_failed_startup_check_stops_the_app_before_serving_and_logs_one_critical_line(
    caplog: pytest.LogCaptureFixture,
) -> None:
    """기동 검사가 실패하면 시작이 같은 오류로 실패하고 CRITICAL 로그 한 줄에 문구가 남는다.

    테스트 코드: AU-104
    """
    # given: check_startup()이 DirectoryLoginDomainMissingError를 내는 Fake UseCaseProvider
    use_cases = FakeUseCases()
    use_cases.startup_error = DirectoryLoginDomainMissingError()
    app = create_app(settings=make_settings(UNUSED_DATABASE_URL), use_cases=use_cases)
    caplog.set_level(logging.DEBUG)

    # when: 앱을 시작한다(TestClient 진입)
    with pytest.raises(DirectoryLoginDomainMissingError) as caught, TestClient(app):
        pass

    # then: 시작이 같은 오류로 실패하고 검사는 한 번 불렸다
    assert str(caught.value) == MISSING_TEXT
    assert use_cases.startup_calls == 1
    # then: CRITICAL 로그 한 줄에 문구가 있고 환경변수 값·DB 주소는 없다
    critical = [r for r in caplog.records if r.levelno == logging.CRITICAL]
    assert [r.getMessage() for r in critical] == [MISSING_TEXT]
    assert "postgresql" not in caplog.text


def test_a_passing_startup_check_lets_the_app_start_and_serve() -> None:
    """기동 검사가 통과하면 앱이 시작되고 /healthz가 200이다.

    테스트 코드: AU-104
    """
    # given: check_startup()이 통과하는 Fake UseCaseProvider
    use_cases = FakeUseCases()
    app = create_app(settings=make_settings(UNUSED_DATABASE_URL), use_cases=use_cases)

    # when: 앱을 시작하고 /healthz를 부른다
    with TestClient(app) as client:
        response = client.get("/healthz")

    # then: 200이고 검사는 한 번 불렸다
    assert response.status_code == 200
    assert use_cases.startup_calls == 1


class _StubContainer:
    """create_app이 만드는 Container 대역: 기동 검사 결과와 스케줄러 생성 여부를 기록한다."""

    instances: list[_StubContainer]

    def __init__(self, _settings: object) -> None:
        self.scheduler_created = 0
        self.disposed = 0
        _StubContainer.instances.append(self)

    async def check_startup(self) -> None:
        if _StubContainer.error is not None:
            raise _StubContainer.error

    def forecast_snapshot_scheduler(self) -> Any:  # noqa: ANN401
        self.scheduler_created += 1

        class _Scheduler:
            async def run_forever(self) -> None:
                await asyncio.sleep(3600)

        return _Scheduler()

    async def dispose(self) -> None:
        self.disposed += 1

    async def check_ready(self) -> None:
        return None

    error: Exception | None = None


@pytest.fixture
def stub_container(monkeypatch: pytest.MonkeyPatch) -> Iterator[type[_StubContainer]]:
    _StubContainer.instances = []
    _StubContainer.error = None
    monkeypatch.setattr(main_module, "Container", _StubContainer)
    yield _StubContainer
    _StubContainer.error = None


def test_the_scheduler_is_not_created_when_the_startup_check_fails(
    stub_container: type[_StubContainer],
) -> None:
    """기동 검사가 실패하면 스케줄러 작업이 만들어지지 않는다(검사가 스케줄러보다 먼저다).

    테스트 코드: AU-104
    """
    # given: 스케줄러가 켜진 설정과, 검사가 실패하는 조립 대역
    stub_container.error = DirectoryLoginDomainMissingError()
    settings = make_settings(UNUSED_DATABASE_URL, scheduler_enabled=True)
    app = create_app(settings=settings)

    # when: 앱을 시작한다
    with pytest.raises(DirectoryLoginDomainMissingError), TestClient(app):
        pass

    # then: 스케줄러 생성이 한 번도 없었다
    assert [c.scheduler_created for c in stub_container.instances] == [0]


def test_the_scheduler_starts_after_the_startup_check_passes(
    stub_container: type[_StubContainer],
) -> None:
    """기동 검사가 통과하면 그 뒤에 스케줄러 작업을 만든다.

    테스트 코드: AU-104
    """
    # given: 스케줄러가 켜진 설정과, 검사가 통과하는 조립 대역
    settings = make_settings(UNUSED_DATABASE_URL, scheduler_enabled=True)
    app = create_app(settings=settings)

    # when: 앱을 시작하고 끝낸다
    with TestClient(app):
        pass

    # then: 스케줄러를 한 번 만들었고 조립은 정리되었다
    assert [(c.scheduler_created, c.disposed) for c in stub_container.instances] == [(1, 1)]
