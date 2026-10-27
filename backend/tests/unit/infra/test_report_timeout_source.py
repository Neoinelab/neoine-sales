"""Reports 시간 제한의 단일 출처: 화면 안내·실제 적용·오류 문구가 domain 상수 하나에서 나온다."""

import inspect

from app.domain.report.vocabulary import STATEMENT_TIMEOUT_SECONDS
from app.infra.db import report_runner
from app.infra.db.report_runner import SqlReportQueryRunner


def test_runner_default_timeout_is_the_domain_constant_in_milliseconds() -> None:
    default = inspect.signature(SqlReportQueryRunner.__init__).parameters["timeout_ms"].default

    assert default == STATEMENT_TIMEOUT_SECONDS * 1000


def test_runner_module_does_not_hardcode_the_timeout_number() -> None:
    assert "10_000" not in inspect.getsource(report_runner)
    assert "10000" not in inspect.getsource(report_runner)
