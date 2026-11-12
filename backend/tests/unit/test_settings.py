"""프로파일 설정 선택·검증(PL-R24~R28, PL-041~PL-050). 환경은 tmp 디렉터리로 격리한다."""

import os
from typing import TYPE_CHECKING

import pytest
from pydantic import ValidationError

from app.config import Profile, get_settings
from app.config.profiles import DevSettings, LocalSettings, ProductSettings
from tests.support.crypto_keys import TEST_FERNET_KEY

if TYPE_CHECKING:
    from collections.abc import Iterator
    from pathlib import Path

JWT_SECRET = "x" * 40
BASE_ENV = {
    "APP_DATABASE_URL": "postgresql+asyncpg://u:p@localhost:5432/app",
    "APP_JWT_SECRET": JWT_SECRET,
    "APP_SETTINGS_ENCRYPTION_KEY": TEST_FERNET_KEY,
}
PRODUCT_ENV = {
    "APP_PROFILE": "product",
    "APP_SENTRY_DSN": "https://key@sentry.internal.example.com/1",
    "APP_CORS_ALLOWED_ORIGINS": '["https://sales.internal.example.com"]',
}
PRODUCT_WORKERS = 4


@pytest.fixture(autouse=True)
def _isolated_env(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> Iterator[None]:
    """실제 환경변수와 .env 파일의 영향을 받지 않도록 격리한다."""
    monkeypatch.chdir(tmp_path)
    for key in [k for k in os.environ if k.startswith("APP_")]:
        monkeypatch.delenv(key)
    for key, value in BASE_ENV.items():
        monkeypatch.setenv(key, value)
    get_settings.cache_clear()
    yield
    get_settings.cache_clear()


def _set(monkeypatch: pytest.MonkeyPatch, env: dict[str, str]) -> None:
    for key, value in env.items():
        monkeypatch.setenv(key, value)


def test_defaults_to_local_profile_when_profile_is_not_set() -> None:
    """프로파일을 정하지 않으면 local 설정을 읽는다.

    테스트 코드: PL-041
    """
    # when: APP_PROFILE 없이 설정을 읽는다
    settings = get_settings()
    # then: local 설정이다
    assert isinstance(settings, LocalSettings)
    assert settings.profile is Profile.LOCAL
    assert settings.debug is True
    assert settings.log_format == "console"


def test_dev_profile_uses_json_logs_and_debug_off(monkeypatch: pytest.MonkeyPatch) -> None:
    """dev 프로파일은 JSON 로그와 debug 꺼짐을 기본으로 한다.

    테스트 코드: PL-050
    """
    # given: APP_PROFILE=dev
    monkeypatch.setenv("APP_PROFILE", "dev")
    # when: 설정을 읽는다
    settings = get_settings()
    # then: dev 설정이고 debug가 꺼지고 로그는 json이다
    assert isinstance(settings, DevSettings)
    assert settings.debug is False
    assert settings.log_format == "json"


def test_product_accepts_valid_settings(monkeypatch: pytest.MonkeyPatch) -> None:
    """안전한 product 설정은 통과한다.

    테스트 코드: PL-046
    """
    # given: 안전한 product 환경(문서 꺼짐, 보안 쿠키, 긴 jwt_secret, 예시 아닌 키, sentry)
    _set(monkeypatch, PRODUCT_ENV)
    # when: product 설정을 읽는다
    settings = get_settings()
    # then: 통과한다
    assert isinstance(settings, ProductSettings)
    assert settings.enable_docs is False
    assert settings.workers == PRODUCT_WORKERS


@pytest.mark.parametrize(
    ("override", "message"),
    [
        ({"APP_DEBUG": "true"}, "debug"),
        ({"APP_ENABLE_DOCS": "true"}, "enable_docs"),
        ({"APP_DB_ECHO": "true"}, "db_echo"),
        ({"APP_COOKIE_SECURE": "false"}, "cookie_secure"),
        ({"APP_CORS_ALLOWED_ORIGINS": '["*"]'}, "CORS"),
        ({"APP_JWT_SECRET": "short"}, "jwt_secret"),
        ({"APP_JWT_SECRET": "x" * 31}, "jwt_secret은 32자 이상"),
    ],
)
def test_product_rejects_unsafe_settings(
    monkeypatch: pytest.MonkeyPatch, override: dict[str, str], message: str
) -> None:
    """위험한 product 설정은 어긴 항목을 알리며 거부된다.

    테스트 코드: PL-047
    """
    # given: 안전한 product 환경에서 한 항목만 위험하게 바꾼다
    _set(monkeypatch, {**PRODUCT_ENV, **override})
    # when·then: product 설정을 읽는다 → 해당 항목 문구를 담은 검증 오류로 실패한다
    with pytest.raises(ValidationError, match=message):
        get_settings()


def test_product_requires_sentry_dsn(monkeypatch: pytest.MonkeyPatch) -> None:
    """product는 sentry_dsn이 없으면 거부된다.

    테스트 코드: PL-047
    """
    # given: sentry_dsn이 없는 product 환경
    _set(monkeypatch, PRODUCT_ENV)
    monkeypatch.delenv("APP_SENTRY_DSN")
    # when·then: 설정을 읽는다 → "sentry_dsn이 필요합니다"를 담은 검증 오류로 실패한다
    with pytest.raises(ValidationError, match="sentry_dsn이 필요합니다"):
        get_settings()


def test_unknown_profile_fails_fast(monkeypatch: pytest.MonkeyPatch) -> None:
    """잘못된 프로파일 값은 기동 즉시 실패한다.

    테스트 코드: PL-041
    """
    # given: APP_PROFILE=prod(없는 프로파일)
    monkeypatch.setenv("APP_PROFILE", "prod")
    # when·then: 설정을 읽는다 → 검증 오류로 실패한다
    with pytest.raises(ValidationError, match="profile"):
        get_settings()


def test_profile_can_be_read_from_dotenv_file(tmp_path: Path) -> None:
    """env 파일에 둔 APP_PROFILE로 프로파일을 고른다.

    테스트 코드: PL-041
    """
    # given: .env에 APP_PROFILE=dev
    (tmp_path / ".env").write_text("APP_PROFILE=dev\n", encoding="utf-8")
    # when: 설정을 읽는다
    settings = get_settings()
    # then: dev 설정이다
    assert isinstance(settings, DevSettings)


@pytest.mark.parametrize("profile", ["local", "dev", "product"])
@pytest.mark.parametrize(
    "missing", ["APP_DATABASE_URL", "APP_JWT_SECRET", "APP_SETTINGS_ENCRYPTION_KEY"]
)
def test_missing_required_variable_fails_in_every_profile(
    monkeypatch: pytest.MonkeyPatch, profile: str, missing: str
) -> None:
    """필수 값이 하나라도 없으면 모든 프로파일에서 기동이 실패한다.

    테스트 코드: PL-044
    """
    # given: 필수 값 하나를 뺀 환경
    _set(monkeypatch, {**PRODUCT_ENV, "APP_PROFILE": profile})
    monkeypatch.delenv(missing)
    # when·then: 그 프로파일 설정을 읽는다 → 빠진 변수 이름을 담은 검증 오류로 실패한다
    with pytest.raises(ValidationError, match=missing.removeprefix("APP_").lower()):
        get_settings()


def test_secret_values_are_not_exposed_in_repr() -> None:
    """설정 객체의 표현에 jwt_secret이 나오지 않는다.

    테스트 코드: PL-049
    """
    # given: jwt_secret을 넣은 설정
    settings = get_settings()
    # when: 문자열로 바꾼다
    text = repr(settings)
    # then: 비밀 값이 나오지 않는다
    assert JWT_SECRET not in text


def test_every_secret_stays_out_of_the_product_settings_text(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """jwt_secret·암호화 키·sentry_dsn은 설정의 repr과 str에 나오지 않는다.

    테스트 코드: PL-049
    """
    # given: 세 비밀 값을 모두 넣은 product 설정
    _set(monkeypatch, PRODUCT_ENV)
    settings = get_settings()
    # when: 설정 객체를 문자열로 바꾼다
    text = repr(settings) + str(settings)
    # then: 세 값 모두 나오지 않는다
    assert JWT_SECRET not in text
    assert TEST_FERNET_KEY not in text
    assert PRODUCT_ENV["APP_SENTRY_DSN"] not in text


def test_redis_is_not_required() -> None:
    """APP_REDIS_URL은 없어도 된다.

    테스트 코드: PL-044
    """
    # when: Redis 주소 없이 설정을 읽는다
    redis_url = get_settings().redis_url
    # then: 비어 있다
    assert redis_url is None


def test_redis_url_is_parsed_when_given(monkeypatch: pytest.MonkeyPatch) -> None:
    """APP_REDIS_URL을 주면 Redis 주소로 해석한다.

    테스트 코드: PL-044
    """
    # given: Redis DSN
    monkeypatch.setenv("APP_REDIS_URL", "redis://localhost:6379/0")
    # when: 설정을 읽는다
    redis_url = get_settings().redis_url
    # then: 호스트가 해석된다
    assert redis_url is not None
    assert redis_url.host == "localhost"


def test_invalid_redis_url_is_rejected(monkeypatch: pytest.MonkeyPatch) -> None:
    """형식이 틀린 APP_REDIS_URL은 거부된다.

    테스트 코드: PL-044
    """
    # given: Redis DSN이 아닌 값
    monkeypatch.setenv("APP_REDIS_URL", "not-a-redis-url")
    # when·then: 설정을 읽는다 → redis_url 검증 오류로 실패한다
    with pytest.raises(ValidationError, match="redis_url"):
        get_settings()


@pytest.mark.parametrize("profile", ["local", "dev", "product"])
@pytest.mark.parametrize("flag", ["true", "false"])
def test_dev_login_variable_is_ignored_in_every_profile(
    monkeypatch: pytest.MonkeyPatch, profile: str, flag: str
) -> None:
    """폐지된 APP_DEV_LOGIN_ENABLED는 어느 프로파일에서도 무시한다.

    테스트 코드: PL-043
    """
    # given: 폐지된 변수가 남아 있는 환경
    _set(monkeypatch, {**PRODUCT_ENV, "APP_PROFILE": profile, "APP_DEV_LOGIN_ENABLED": flag})
    # when: 설정을 읽는다
    settings = get_settings()
    # then: 오류 없이 읽히고 해당 필드가 없다
    assert settings.profile.value == profile
    assert not hasattr(settings, "dev_login_enabled")
    assert "dev_login_enabled" not in type(settings).model_fields


# 예전 OIDC 배포 환경의 잔여 변수. 값이 JSON이 아니어도 무시해야 한다(CFG-2).
STALE_OIDC_ENV = {
    "APP_OIDC_ISSUER": "https://adfs.example.com/adfs",
    "APP_OIDC_CLIENT_ID": "neoine-sales",
    "APP_OIDC_CLIENT_SECRET": "client-secret-value",
    "APP_OIDC_REDIRECT_URI": "https://sales.example.com/api/v1/auth/callback",
    "APP_OIDC_ADMIN_GROUPS": "not-json-at-all",
    "APP_OIDC_SALES_GROUPS": "[broken",
    "APP_OIDC_SCOPES": "{",
}


def test_settings_have_no_oidc_fields_or_properties() -> None:
    """설정에 예전 OIDC 필드가 없다.

    테스트 코드: PL-043
    """
    # when: 설정을 읽는다
    settings = get_settings()
    # then: oidc로 시작하는 필드와 oidc_enabled가 없다
    assert not [name for name in type(settings).model_fields if name.startswith("oidc")]
    assert not hasattr(settings, "oidc_enabled")


@pytest.mark.parametrize("profile", ["local", "dev", "product"])
def test_oidc_variables_left_in_the_environment_are_ignored(
    monkeypatch: pytest.MonkeyPatch, profile: str
) -> None:
    """환경변수에 남은 예전 OIDC 변수는 무시한다.

    테스트 코드: PL-043
    """
    # given: 예전 OIDC 변수가 남은 환경
    _set(monkeypatch, {**PRODUCT_ENV, "APP_PROFILE": profile, **STALE_OIDC_ENV})
    # when: 설정을 읽는다
    settings = get_settings()
    # then: 오류 없이 읽히고 값이 노출되지 않는다
    assert settings.profile.value == profile
    assert not hasattr(settings, "oidc_issuer")
    assert "client-secret-value" not in repr(settings)


def test_oidc_variables_in_a_dotenv_file_are_ignored(tmp_path: Path) -> None:
    """env 파일에 남은 예전 OIDC 변수도 무시한다.

    테스트 코드: PL-043
    """
    # given: .env에 예전 OIDC 변수
    lines = [f"{key}={value}" for key, value in STALE_OIDC_ENV.items()]
    (tmp_path / ".env").write_text("\n".join(lines) + "\n", encoding="utf-8")
    # when: 설정을 읽는다
    settings = get_settings()
    # then: local 설정으로 읽힌다
    assert isinstance(settings, LocalSettings)


def test_product_starts_without_any_login_variables(monkeypatch: pytest.MonkeyPatch) -> None:
    """product는 로그인 관련 변수 없이도 기동한다.

    테스트 코드: PL-046
    """
    # given: 로그인 관련 변수가 없는 product 환경
    _set(monkeypatch, PRODUCT_ENV)
    # when: 설정을 읽는다
    settings = get_settings()
    # then: product 설정이다
    assert settings.profile is Profile.PRODUCT


def test_local_starts_without_any_login_variables() -> None:
    """local도 로그인 관련 변수 없이 기동한다."""
    # when: 로그인 변수 없이 설정을 읽는다
    settings = get_settings()
    # then: local 설정이다
    assert isinstance(settings, LocalSettings)


def test_session_ttl_default_and_secrets_stay_hidden() -> None:
    """세션 유지 기본값은 8시간이고 비밀은 표현에 나오지 않는다.

    테스트 코드: PL-050
    """
    # when: 기본 설정을 읽는다
    settings = get_settings()
    # then: 8시간이고 jwt_secret이 보이지 않는다
    assert settings.session_ttl_hours == 8
    assert JWT_SECRET not in repr(settings)


@pytest.mark.parametrize(
    ("profile", "expected"),
    [
        (
            "local",
            {
                "debug": True,
                "enable_docs": True,
                "log_level": "DEBUG",
                "log_format": "console",
                "cookie_secure": False,
                "db_echo": True,
                "db_pool_size": 5,
                "workers": 1,
            },
        ),
        (
            "dev",
            {
                "debug": False,
                "enable_docs": True,
                "log_level": "DEBUG",
                "log_format": "json",
                "sentry_traces_sample_rate": 1.0,
                "db_pool_size": 10,
            },
        ),
        (
            "product",
            {
                "debug": False,
                "enable_docs": False,
                "log_level": "INFO",
                "log_format": "json",
                "cookie_secure": True,
                "workers": 4,
                "sentry_traces_sample_rate": 0.1,
                "db_pool_size": 10,
            },
        ),
    ],
)
def test_each_profile_has_its_documented_defaults(
    monkeypatch: pytest.MonkeyPatch, profile: str, expected: dict[str, object]
) -> None:
    """프로파일마다 정해진 기본값을 쓴다.

    테스트 코드: PL-050
    """
    # given: 값을 따로 주지 않은 프로파일(product는 안전 검사를 통과할 최소 값만)
    _set(monkeypatch, {**PRODUCT_ENV, "APP_PROFILE": profile})
    # when: 설정을 읽는다
    settings = get_settings()
    # then: PL-R28의 기본값이다
    actual = {name: getattr(settings, name) for name in expected}
    assert actual == expected
    assert settings.session_ttl_hours == 8
