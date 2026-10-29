# 환경변수 목록과 설정 코드 구조

## 목차

1. 설정 코드 구조
2. 백엔드 변수 목록
3. 프론트엔드 변수
4. 프로파일별 기본 동작 차이

## 1. 설정 코드 구조

```
backend/src/app/config/
├─ base.py       Profile(StrEnum), Settings(BaseSettings, env_prefix="APP_")  공통 필드
├─ profiles.py   LocalSettings, DevSettings, ProductSettings(+안전 검증)       프로파일별 기본 동작
└─ __init__.py   get_settings()  APP_PROFILE(환경변수 또는 .env)로 클래스 선택, 미설정 시 local
```

- `get_settings()`는 `lru_cache`로 프로세스당 한 번 로드한다. 테스트는 `get_settings.cache_clear()`를 쓴다.
- 환경변수가 `.env` 파일보다 우선한다. 서버에서는 systemd `WorkingDirectory`의 `.env`를 읽는다.
- `list[str]` 같은 복합 타입은 환경변수에서 **JSON 문자열**로 파싱된다.
- 정본은 코드(`config/*.py`)다. 이 문서와 어긋나면 코드가 맞다.

## 2. 백엔드 변수 목록 (접두어 `APP_`)

비밀 ●: Git·산출물·로그에 쓰지 않고 서버 `.env`에서만 관리한다.

| 변수 | 설명 | 비밀 | 기본/제약 | local | dev | product |
| --- | --- | --- | --- | --- | --- | --- |
| `APP_PROFILE` | 프로파일 선택 | | 미설정 시 local | local | dev | product |
| `APP_DEBUG` | 디버그 | | local만 true | true | false | **false 필수** |
| `APP_ENABLE_DOCS` | Swagger/ReDoc 노출 | | local, dev만 true | true | true | **false 필수** |
| `APP_LOG_LEVEL` | DEBUG/INFO/WARNING/ERROR | | INFO | DEBUG | DEBUG | INFO |
| `APP_LOG_FORMAT` | console/json | | json | console | json | json |
| `APP_WORKERS` | Uvicorn 워커 수(≥1). systemd 유닛의 `--workers`와 같은 값 유지 | | 2 | 1 | 2 | 4 |
| `APP_CORS_ALLOWED_ORIGINS` | 허용 Origin(JSON 배열 문자열) | | `[]` | `["http://localhost:5173"]` | dev 도메인 | 운영 도메인, **`*` 금지** |
| `APP_COOKIE_SECURE` | 쿠키 Secure | | true | false | true | **true 필수** |
| `APP_JWT_SECRET` | JWT 서명 키 | ● | 필수 | 로컬 전용 값 | dev 전용 키 | product 전용 키(**32자 이상**) |
| `APP_ACCESS_TOKEN_TTL_MINUTES` | 액세스 토큰 수명(분, ≥1) | | 15 | | | |
| `APP_REFRESH_TOKEN_TTL_DAYS` | 리프레시 토큰 수명(일, ≥1) | | 7 | | | |
| `APP_SETTINGS_ENCRYPTION_KEY` | DB에 저장하는 설정 비밀(AD 바인드 비밀번호)을 암호화하는 Fernet 키(URL-safe base64, 32바이트, `Fernet.generate_key()`로 생성). 형식이 틀리면 기동 실패(값은 오류 메시지에 안 나옴). 서버는 `infra/server/bootstrap.sh`가 줄이 없을 때만 무작위로 만들어 `.env`에 넣으며(값 출력 없음, 있으면 보존), 코드 배포 전에 있어야 하고 **DB 백업과 분리 보관**. 분실·변경 시 저장된 바인드 비밀번호를 풀 수 없어 admin이 외부연동 설정에서 다시 입력(2026-10-29) | ● | **모든 프로파일 필수** | 개발용 키 | dev 전용 키 | product 전용 키(**`.env.example` 예시 키 거부**) |
| `APP_DATABASE_URL` | PostgreSQL URL(`postgresql+asyncpg://…`) | ● | 필수 | localhost | dev DB | product DB |
| `APP_DB_POOL_SIZE` | 커넥션 풀(≥1) | | 10 | 5 | 10 | 워커·DB 한도에 맞춤 |
| `APP_DB_ECHO` | SQL 로그 | | false | true | false | **false 필수** |
| `APP_REDIS_URL` | Redis URL. **선택, 현재 미사용**(큐·캐시를 도입할 때 필수로 전환) | ● | 없음 | 비움 | 비움 | 비움 |
| `APP_SENTRY_DSN` | 오류 추적 DSN | ● | 없음 | 비움 | dev 프로젝트 | **필수** |
| `APP_SENTRY_TRACES_SAMPLE_RATE` | 0.0~1.0 | | 0.0 | | 1.0 | 0.1 |
| `APP_OTEL_EXPORTER_ENDPOINT` | OTel Collector 주소 | | 없음 | | | |

아직 코드에 없는 연동 변수(SMTP, 결제 API 등)는 해당 Port/어댑터를 만들 때 3장 절차대로 함께 추가한다.

인프라/CI용 변수(애플리케이션 코드가 읽지 않음): `TEST_DATABASE_ADMIN_URL`(통합 테스트용 임시 DB 생성, 로컬/CI 전용), `HTTPS_PROXY`/`NO_PROXY`(프록시 환경).

## 3. 프론트엔드 변수

- `VITE_` 접두어 변수만 클라이언트에 노출되며 **빌드 결과(JS)에 그대로 포함되어 누구나 볼 수 있다. 비밀을 넣지 않는다.**
- API는 같은 오리진 `/api`를 쓰도록 해 환경별 URL 변수를 없앤다(`VITE_API_BASE_URL=/api`, 모든 프로파일 동일).
- 프로파일마다 달라야 하는 소수의 값은 서버가 제공하는 런타임 `/config.json`으로 주입한다.

## 4. 프로파일별 기본 동작 차이 (`profiles.py`)

| 프로파일 | 기본 동작 |
| --- | --- |
| `LocalSettings` | debug=True, enable_docs=True, log DEBUG+console, cookie_secure=False, db_pool_size=5, db_echo=True, workers=1 |
| `DevSettings` | enable_docs=True, log DEBUG, sentry_traces_sample_rate=1.0 |
| `ProductSettings` | workers=4, sentry_traces_sample_rate=0.1, **기동 시 안전 검증**: debug/enable_docs/db_echo 꺼짐, cookie_secure, CORS `*` 금지, JWT 32자 이상, Sentry DSN 필수, `APP_SETTINGS_ENCRYPTION_KEY`가 예시 키(`EXAMPLE_SETTINGS_ENCRYPTION_KEY`)가 아님 |
