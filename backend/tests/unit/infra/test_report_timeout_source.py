"""Reports 시간 제한의 단일 출처: 화면 안내·실제 적용·오류 문구가 domain 상수 하나에서 나온다."""

import inspect

from app.domain.report.vocabulary import STATEMENT_TIMEOUT_SECONDS
from app.infra.db import report_runner
from app.infra.db.report_runner import SqlReportQueryRunner


def test_runner_default_timeout_is_the_domain_constant_in_milliseconds() -> None:
    """실행기의 기본 시간 제한은 도메인 상수(초)를 밀리초로 바꾼 값이다.

    테스트 코드: RQ-061
    """
    # when: 실행기 생성자의 기본 시간 제한 값을 읽는다
    default = inspect.signature(SqlReportQueryRunner.__init__).parameters["timeout_ms"].default

    # then: 도메인 상수 x 1000이다
    assert default == STATEMENT_TIMEOUT_SECONDS * 1000


def test_runner_module_does_not_hardcode_the_timeout_number() -> None:
    """실행기 모듈 소스에 시간 제한 숫자를 직접 적지 않는다.

    테스트 코드: RQ-061
    """
    # when: 실행기 소스를 읽는다
    source = inspect.getsource(report_runner)
    # then: 10_000과 10000이 없다
    assert "10_000" not in source
    assert "10000" not in source
