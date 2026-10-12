"""도달 불가 DC가 여러 개여도 LDAP 호출은 제한 시간 안에 CONNECT 단계 오류로 끝난다(리뷰 Blocker).

ldap3 ServerPool(active=True, exhaust=True)은 서버가 모두 제외되면 영원히 기다린다.
무한 대기가 재발해도 러너가 멈추지 않도록 어댑터 호출은 별도 프로세스에서 하고 상한 뒤 종료한다.
구현 방식(풀 사용 여부)에는 묶이지 않고 동작만 검증한다.
"""

import json
import os
import socket
import subprocess
import sys
import threading
from pathlib import Path
from typing import TYPE_CHECKING

import pytest

if TYPE_CHECKING:
    from collections.abc import Iterator

BACKEND = Path(__file__).resolve().parents[3]
HARD_LIMIT_SECONDS = 12  # 이 안에 프로세스가 끝나지 않으면 무한 대기로 본다
EXPECTED_WITHIN_SECONDS = 8  # 연결 타임아웃 1초 설정에서 정상 구현이 끝나는 상한(여유 포함)

SCRIPT = """
import asyncio, json, sys, time
from app.application.ports.directory import DirectoryError
from app.domain.auth.credentials import LoginId, Password
from app.domain.directory.settings import DirectoryUrl
from app.infra.auth.ldap import LdapDirectoryAuthenticator
from tests.factories_auth import make_directory_settings

urls, method = json.loads(sys.argv[1]), sys.argv[2]
settings = make_directory_settings(
    server_urls=tuple(DirectoryUrl.parse(u) for u in urls),
    connect_timeout_seconds=1,
    receive_timeout_seconds=1,
)

async def main():
    adapter = LdapDirectoryAuthenticator()
    started = time.monotonic()
    try:
        if method == "probe":
            await adapter.probe(settings)
        else:
            await adapter.authenticate(settings, LoginId("kim"), Password("pw-dummy"))
        outcome = {"error": None, "stage": None}
    except DirectoryError as error:
        outcome = {"error": type(error).__name__, "stage": getattr(error.stage, "value", None)}
    outcome["elapsed"] = time.monotonic() - started
    print(json.dumps(outcome))

asyncio.run(main())
"""


def _closed_port() -> int:
    with socket.socket() as probe:
        probe.bind(("127.0.0.1", 0))
        return int(probe.getsockname()[1])


class _Listener:
    """연결을 받자마자 닫는 TCP 서버. TLS 핸드셰이크는 실패하지만 '도달했는지'는 센다."""

    def __init__(self) -> None:
        self.server = socket.socket()
        self.server.bind(("127.0.0.1", 0))
        self.server.listen()
        self.port = int(self.server.getsockname()[1])
        self.accepted = 0
        self._thread = threading.Thread(target=self._serve, daemon=True)
        self._thread.start()

    def _serve(self) -> None:
        while True:
            try:
                connection, _ = self.server.accept()
            except OSError:
                return
            self.accepted += 1
            connection.close()

    def close(self) -> None:
        self.server.close()


@pytest.fixture
def listener() -> Iterator[_Listener]:
    active = _Listener()
    try:
        yield active
    finally:
        active.close()


def _run(urls: list[str], method: str) -> dict[str, object]:
    env = {**os.environ, "PYTHONPATH": os.pathsep.join([str(BACKEND / "src"), str(BACKEND)])}
    try:
        done = subprocess.run(  # noqa: S603 - 고정 인자, 신뢰된 로컬 스크립트
            [sys.executable, "-c", SCRIPT, json.dumps(urls), method],
            cwd=BACKEND,
            env=env,
            capture_output=True,
            text=True,
            timeout=HARD_LIMIT_SECONDS,
            check=False,
        )
    except subprocess.TimeoutExpired:
        pytest.fail(f"도달 불가 서버 호출이 {HARD_LIMIT_SECONDS}초 안에 끝나지 않았다(무한 대기)")
    assert done.returncode == 0, done.stderr[-2000:]
    result: dict[str, object] = json.loads(done.stdout.strip().splitlines()[-1])
    return result


@pytest.mark.parametrize("method", ["probe", "authenticate"])
def test_two_unreachable_servers_fail_fast_with_a_connect_stage_error(method: str) -> None:
    urls = [f"ldaps://127.0.0.1:{_closed_port()}", f"ldaps://127.0.0.1:{_closed_port()}"]

    outcome = _run(urls, method)

    assert outcome["error"] == "DirectoryUnavailableError"
    assert outcome["stage"] == "connect"
    assert float(str(outcome["elapsed"])) < EXPECTED_WITHIN_SECONDS


def test_one_unreachable_server_still_fails_fast_with_a_connect_stage_error() -> None:
    outcome = _run([f"ldaps://127.0.0.1:{_closed_port()}"], "probe")

    assert (outcome["error"], outcome["stage"]) == ("DirectoryUnavailableError", "connect")


def test_the_next_server_is_tried_when_the_first_one_is_unreachable(listener: _Listener) -> None:
    urls = [f"ldaps://127.0.0.1:{_closed_port()}", f"ldaps://127.0.0.1:{listener.port}"]

    outcome = _run(urls, "probe")

    assert listener.accepted >= 1, "첫 서버가 닫혀 있으면 다음 서버를 시도해야 한다"
    assert outcome["error"] == "DirectoryUnavailableError"  # 두 번째는 TLS가 아니라 실패한다
    assert float(str(outcome["elapsed"])) < EXPECTED_WITHIN_SECONDS
