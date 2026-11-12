import pytest

from tests.support.skips import skip_or_fail


def test_skips_when_the_database_is_optional(monkeypatch: pytest.MonkeyPatch) -> None:
    """DB가 필수가 아니면 skip_or_fail은 건너뛴다."""
    # given: REQUIRE_INTEGRATION_DB 환경 변수 없음
    monkeypatch.delenv("REQUIRE_INTEGRATION_DB", raising=False)

    # when·then: skip_or_fail을 부르면 skip 예외다
    with pytest.raises(pytest.skip.Exception):
        skip_or_fail("DB 없음")


def test_fails_when_the_database_is_required(monkeypatch: pytest.MonkeyPatch) -> None:
    """DB가 필수이면 skip_or_fail은 건너뛰지 않고 실패한다."""
    # given: REQUIRE_INTEGRATION_DB가 켜져 있다
    monkeypatch.setenv("REQUIRE_INTEGRATION_DB", "1")

    # when·then: skip_or_fail을 부르면 메시지를 담은 실패 예외다
    with pytest.raises(pytest.fail.Exception, match="DB 없음"):
        skip_or_fail("DB 없음")
