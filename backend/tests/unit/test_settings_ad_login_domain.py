"""APP_AD_LOGIN_DOMAIN: AD 사용자 바인드 도메인 설정 검증(AU-R7a, AU-094·097·098).

선택 항목이고 모든 프로파일에서 같은 규칙이다. 앞뒤 공백을 지우고 소문자로 바꾸며
빈 값은 '없음'이다. 형식이 틀리면 설정 로드(기동)가 실패하고 오류에 입력값이 나오지 않는다.
"""

import os
from typing import TYPE_CHECKING

import pytest
from pydantic import ValidationError

from app.config import get_settings
from tests.support.crypto_keys import TEST_FERNET_KEY

if TYPE_CHECKING:
    from collections.abc import Iterator
    from pathlib import Path

MESSAGE = "ad_login_domain은 도메인 형식(예: neoine.co.kr)이어야 합니다"
PROFILE_ENVS = {
    "local": {},
    "dev": {"APP_PROFILE": "dev"},
    "product": {
        "APP_PROFILE": "product",
        "APP_SENTRY_DSN": "https://key@sentry.internal.example.com/1",
        "APP_CORS_ALLOWED_ORIGINS": '["https://sales.internal.example.com"]',
    },
}
LABEL63 = "a" * 63
VALID_253 = ".".join([LABEL63, LABEL63, LABEL63, "a" * 61])  # 63*3 + 61 + 점 3개 = 253
INVALID = [
    "@neoine.co.kr",
    "kim@neoine.co.kr",
    "neoine .co.kr",
    "neoine..co.kr",
    "neoine.co.kr.",
    "-neoine.co.kr",
    "neoine-.co.kr",
    "네오인.kr",
    "neo\u0001ine.kr",
    "a" * 64 + ".kr",
    VALID_253 + "b",  # 254자
]


@pytest.fixture(autouse=True)
def _isolated_env(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> Iterator[None]:
    monkeypatch.chdir(tmp_path)
    for key in [k for k in os.environ if k.startswith("APP_")]:
        monkeypatch.delenv(key)
    monkeypatch.setenv("APP_DATABASE_URL", "postgresql+asyncpg://u:p@localhost:5432/app")
    monkeypatch.setenv("APP_JWT_SECRET", "x" * 40)
    monkeypatch.setenv("APP_SETTINGS_ENCRYPTION_KEY", TEST_FERNET_KEY)
    get_settings.cache_clear()
    yield
    get_settings.cache_clear()


def _load(monkeypatch: pytest.MonkeyPatch, profile: str, value: str | None) -> str | None:
    for key, item in PROFILE_ENVS[profile].items():
        monkeypatch.setenv(key, item)
    if value is not None:
        monkeypatch.setenv("APP_AD_LOGIN_DOMAIN", value)
    get_settings.cache_clear()
    return get_settings().ad_login_domain


@pytest.mark.parametrize("value", [None, "", "   "], ids=["unset", "empty", "blank"])
def test_missing_or_blank_domain_means_no_domain(
    monkeypatch: pytest.MonkeyPatch, value: str | None
) -> None:
    """변수가 없거나 비어 있거나 공백뿐이면 도메인 없음(None)이다.

    테스트 코드: AU-094
    """
    # given: 변수가 없거나 비어 있다
    # when: 설정을 읽는다
    result = _load(monkeypatch, "local", value)

    # then: 도메인 없음이다
    assert result is None


@pytest.mark.parametrize("profile", list(PROFILE_ENVS))
def test_domain_is_trimmed_and_lowercased(monkeypatch: pytest.MonkeyPatch, profile: str) -> None:
    """앞뒤 공백을 지우고 소문자로 바꾼 값이 남는다.

    테스트 코드: AU-097
    """
    # given: "  NEOINE.Co.KR "
    # when: 설정을 읽는다
    result = _load(monkeypatch, profile, "  NEOINE.Co.KR ")

    # then: neoine.co.kr이다
    assert result == "neoine.co.kr"


@pytest.mark.parametrize("profile", list(PROFILE_ENVS))
@pytest.mark.parametrize("value", INVALID, ids=[f"invalid-{i}" for i in range(len(INVALID))])
def test_malformed_domain_fails_startup_without_echoing_it(
    monkeypatch: pytest.MonkeyPatch, profile: str, value: str
) -> None:
    """도메인 형식이 틀리면 모든 프로파일에서 기동이 실패하고 오류에 값이 나오지 않는다.

    테스트 코드: AU-098
    """
    # given: 형식이 틀린 값
    # when: 설정을 읽는다
    with pytest.raises(ValidationError) as caught:
        _load(monkeypatch, profile, value)

    # then: 문구는 있고 입력값은 오류 문자열에 없다
    text = str(caught.value)
    assert MESSAGE in text
    assert value.strip() not in text


@pytest.mark.parametrize("profile", list(PROFILE_ENVS))
@pytest.mark.parametrize(
    "value",
    ["neoine.co.kr", "corp", "a-b.example.com", LABEL63 + ".kr", VALID_253],
    ids=["normal", "single-label", "hyphen", "label-63", "total-253"],
)
def test_well_formed_domains_are_accepted(
    monkeypatch: pytest.MonkeyPatch, profile: str, value: str
) -> None:
    """형식에 맞는 도메인(단일 라벨, 63자 라벨, 253자)은 통과하고 값이 그대로 남는다.

    테스트 코드: AU-098
    """
    # given: 형식에 맞는 값
    # when: 설정을 읽는다
    result = _load(monkeypatch, profile, value)

    # then: 그대로 남는다
    assert result == value
