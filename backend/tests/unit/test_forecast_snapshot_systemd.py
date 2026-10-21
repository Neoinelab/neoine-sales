"""AC-20: 월말 Forecast 스냅숏 systemd timer·service와 bootstrap.sh 설치 계약.

기존 API 서비스 파일과 같은 값(User, WorkingDirectory, 환경 지정 방식)은 하드코딩하지 않고
API 서비스 파일에서 읽어 비교한다.
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[3]
SYSTEMD = ROOT / "infra" / "server" / "systemd"
BOOTSTRAP = ROOT / "infra" / "server" / "bootstrap.sh"
API_SERVICE = SYSTEMD / "neoine-sales-api.service"
SNAP_SERVICE = SYSTEMD / "neoine-sales-forecast-snapshot.service"
SNAP_TIMER = SYSTEMD / "neoine-sales-forecast-snapshot.timer"
TIMER_NAME = "neoine-sales-forecast-snapshot.timer"

Unit = dict[str, dict[str, list[str]]]


def _parse(path: Path) -> Unit:
    """systemd unit 파일을 {섹션: {키: [값...]}}로 읽는다(주석 제외, 역슬래시 줄 이음 처리)."""
    text = path.read_text(encoding="utf-8").replace("\\\n", " ")
    result: Unit = {}
    section = ""
    for raw in text.splitlines():
        line = raw.strip()
        if not line or line.startswith(("#", ";")):
            continue
        if line.startswith("[") and line.endswith("]"):
            section = line[1:-1]
            result.setdefault(section, {})
            continue
        key, _, value = line.partition("=")
        result[section].setdefault(key.strip(), []).append(" ".join(value.split()))
    return result


def _one(unit: Unit, section: str, key: str) -> str:
    values = unit.get(section, {}).get(key, [])
    assert len(values) == 1, f"[{section}] {key} must be set exactly once: {values}"
    return values[0]


@pytest.fixture(scope="module")
def api() -> Unit:
    return _parse(API_SERVICE)


@pytest.fixture(scope="module")
def service() -> Unit:
    assert SNAP_SERVICE.is_file(), f"missing {SNAP_SERVICE}"
    return _parse(SNAP_SERVICE)


@pytest.fixture(scope="module")
def timer() -> Unit:
    assert SNAP_TIMER.is_file(), f"missing {SNAP_TIMER}"
    return _parse(SNAP_TIMER)


def test_timer_on_calendar_is_first_day_0005(timer: Unit) -> None:
    assert _one(timer, "Timer", "OnCalendar") == "*-*-01 00:05:00"


def test_timer_is_persistent(timer: Unit) -> None:
    assert _one(timer, "Timer", "Persistent") == "true"


def test_timer_targets_snapshot_service(timer: Unit) -> None:
    explicit = timer["Timer"].get("Unit")
    assert explicit in (None, [SNAP_SERVICE.name])
    assert SNAP_SERVICE.is_file()


def test_timer_is_wanted_by_timers_target(timer: Unit) -> None:
    assert _one(timer, "Install", "WantedBy") == "timers.target"


def test_service_is_oneshot(service: Unit) -> None:
    assert _one(service, "Service", "Type") == "oneshot"


def test_service_has_a_30_minute_start_timeout(service: Unit) -> None:
    assert _one(service, "Service", "TimeoutStartSec") == "30min"


def test_service_has_no_restart_loop(service: Unit) -> None:
    assert "Restart" not in service["Service"] or _one(service, "Service", "Restart") == "no"


def test_service_runs_as_same_user_and_group_as_api(service: Unit, api: Unit) -> None:
    assert _one(service, "Service", "User") == "neoine"
    assert _one(service, "Service", "User") == _one(api, "Service", "User")
    assert _one(service, "Service", "Group") == _one(api, "Service", "Group")


def test_service_working_directory_matches_api(service: Unit, api: Unit) -> None:
    assert _one(service, "Service", "WorkingDirectory") == "/opt/neoine-sales"
    assert _one(service, "Service", "WorkingDirectory") == _one(api, "Service", "WorkingDirectory")


def test_service_environment_selection_matches_api(service: Unit, api: Unit) -> None:
    for key in ("EnvironmentFile", "Environment", "PassEnvironment"):
        assert service["Service"].get(key, []) == api["Service"].get(key, []), key


def test_service_exec_start_runs_job_module_with_release_venv_python(
    service: Unit, api: Unit
) -> None:
    exec_start = _one(service, "Service", "ExecStart")
    api_exec = _one(api, "Service", "ExecStart")
    venv_bin = api_exec.split()[0].rsplit("/", 1)[0]
    assert exec_start == f"{venv_bin}/python -m app.jobs.forecast_snapshot"
    assert "/current/backend/.venv/bin/" in exec_start


def test_bootstrap_installs_timer_and_service_files() -> None:
    text = BOOTSTRAP.read_text(encoding="utf-8")
    install_lines = [
        ln
        for ln in text.splitlines()
        if ln.lstrip().startswith("install ") and "/etc/systemd/system" in ln
    ]
    joined = "\n".join(install_lines)
    assert re.search(r"systemd/(\*\.timer|neoine-sales-forecast-snapshot\.timer)", joined), joined
    assert re.search(r"systemd/(\*\.service|neoine-sales-forecast-snapshot\.service)", joined), (
        joined
    )


def test_bootstrap_enables_snapshot_timer() -> None:
    text = BOOTSTRAP.read_text(encoding="utf-8")
    enable_lines = [ln for ln in text.splitlines() if re.match(r"\s*systemctl\s+enable\b", ln)]
    assert any(TIMER_NAME in ln for ln in enable_lines), "enable the .timer unit, not the service"
