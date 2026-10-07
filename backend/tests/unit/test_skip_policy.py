import pytest

from tests.support.skips import skip_or_fail


def test_skips_when_the_database_is_optional(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("REQUIRE_INTEGRATION_DB", raising=False)

    with pytest.raises(pytest.skip.Exception):
        skip_or_fail("DB 없음")


def test_fails_when_the_database_is_required(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("REQUIRE_INTEGRATION_DB", "1")

    with pytest.raises(pytest.fail.Exception, match="DB 없음"):
        skip_or_fail("DB 없음")
