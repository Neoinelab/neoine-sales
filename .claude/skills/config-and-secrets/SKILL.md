---
name: config-and-secrets
description: 환경변수, 프로파일(local/dev/product) 설정, 비밀 값, 새 설정 항목(Settings 필드) 추가, app.config 모듈, .env.example을 다루거나 설정 때문에 기동이 실패하는 문제를 진단할 때 사용한다. .env 파일은 읽지 않고 변수 이름과 절차만 다룬다. 비즈니스 로직 구현, 계층 설계, 배포 스크립트 작성에는 사용하지 않는다.
---

# 설정과 비밀 관리

프로파일 `local` / `dev` / `product`마다 달라지는 값은 환경변수로 관리합니다. 정본은 `docs/dev-guide.html` 3.5장과 `backend/src/app/config/` 코드입니다. 변수 목록과 값 예시는 `references/env-vars.md`에 있습니다.

## 사용 조건

- 사용: 새 설정 항목 추가, 프로파일별 기본 동작 변경, `.env.example` 수정, 설정 검증 실패 진단, 설정 코드 리뷰
- 사용하지 않음: 비즈니스 로직, 계층/Port 설계(`layer-architecture-rules`), `deploy.sh`·systemd·Nginx 같은 서버 구성(사람이 담당)

## 절대 규칙

1. **`.env*` 파일은 읽지도 쓰지도 않는다.** 비밀이 들어 있다. 필요한 변수 이름과 형식은 `backend/.env.example`과 `references/env-vars.md`로 확인한다. (`.claude/hooks/guard.py`와 권한 설정이 차단한다. 막히면 우회하지 말고 사용자에게 알린다.)
2. **비밀 값을 코드, 테스트, 산출물, 로그, 대화에 쓰지 않는다.** 더미 값만 쓴다. 비밀 필드는 `SecretStr`로 선언한다.
3. **서버(`dev`/`product`)의 `.env` 값 입력은 사람이 한다.** 필요한 키 이름과 절차만 안내한다.
4. `domain`/`application`에서 `app.config`를 import하지 않는다. 설정은 `container.py`와 앱 팩토리에서만 읽고 필요한 값만 생성자로 주입한다.
5. 코드에서 프로파일 이름으로 분기(`if profile == ...`)하지 않는다. 프로파일별 차이는 `profiles.py`의 설정 클래스 기본값으로 표현한다.

## 새 설정 항목을 추가하는 절차

1. **필요성 확인**: 값이 환경마다 달라지는가? 아니면 상수/기본값으로 충분한가? 비밀인가(`SecretStr`)?
2. **Settings 필드 추가**: `config/base.py`에 타입, 기본값(비밀은 기본값 없음 = 필수), 제약(`Field(ge=...)`)을 선언한다. 프로파일별 기본값이 다르면 `config/profiles.py`의 해당 클래스에서 덮어쓴다.
3. **product 안전 조건 검토**: 운영에서 위험한 값(디버그, 문서 노출, 와일드카드 등)이면 `ProductSettings`의 검증기에 조건을 추가한다.
4. **`backend/.env.example` 갱신**: 변수 이름과 안전한 예시 값(비밀은 더미)을 추가하고 필수 여부를 주석으로 적는다.
5. **문서 갱신**: `docs/dev-guide.html` 3.5.3의 변수 표와 `references/env-vars.md`를 같이 고친다.
6. **테스트**: `backend/tests/unit/test_settings.py`에 정상·누락·위반 케이스를 추가한다(`tdd-python-testing`).
7. **사람에게 안내(필수)**: "dev/product 서버 `.env`에 `APP_<NAME>`을 먼저 추가해야 한다"는 사실을 최종 보고에 적는다. 필수 변수를 코드보다 늦게 반영하면 기동 단계(fail-fast)에서 실패한다. 서버 값 입력은 승인·수행 모두 사람이다.

## 진단 절차 (기동 실패)

- `Field required`: 필수 변수 누락. 이름만 확인한다(`APP_` 접두어 포함). 값은 묻거나 보지 않는다.
- `profile` 검증 오류: `APP_PROFILE`이 `local`/`dev`/`product` 밖의 값(오타, 예: `prod`).
- product 검증 실패 메시지(디버그/문서/DB echo, 쿠키, CORS `*`, JWT 길이, Sentry): 값을 고치도록 사람에게 안내한다. 검증을 완화해서 통과시키지 않는다.
- `list` 타입 변수(`APP_CORS_ALLOWED_ORIGINS`)는 JSON 배열 문자열이어야 한다.

## 출력과 품질 기준

- 변경 파일: `config/*.py`, `.env.example`, `tests/unit/test_settings.py`, 문서(변수 표)
- 통과 기준: 설정 테스트 통과 + `uv run python scripts/run_gates.py` 통과 + 비밀 값이 diff에 없음 + 서버 `.env` 선반영 안내 포함
- 사람 승인 필요: 비밀·서버 `.env` 값 변경, product 안전 조건 완화

## 참조 (필요할 때만 읽는다)

- `references/env-vars.md`: 변수 목록(설명, 비밀 여부, 프로파일별 권장값), 설정 코드 구조
