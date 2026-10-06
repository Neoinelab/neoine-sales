---
name: layer-architecture-rules
description: backend 코드를 domain, application, infra, web 계층 중 어디에 둘지 정하거나, Port(인터페이스)·유스케이스·Repository/어댑터·라우터를 설계·구현·검토할 때 사용한다. 계층 의존 방향, Port 소유 위치(application/ports), SOLID 위반 판단 기준을 제공한다. 오타·포맷 수정, 프론트엔드 전용 작업, 설정/환경변수 작업(config-and-secrets 사용)에는 사용하지 않는다.
---

# 계층 아키텍처 규칙

이 프로젝트는 DDD 4계층에 의존성 역전을 적용합니다. 규칙의 정본은 `docs/dev-guide.html` 4·7·8·9장이며, 이 Skill은 작업 중에 바로 쓰는 판단 기준입니다. 숫자 제한(파일 줄 수, 복잡도 등)은 여기 적지 않고 `backend/pyproject.toml`과 `backend/scripts/`가 정본입니다.

## 사용 조건

- 사용: 새 유스케이스·엔티티·Port·Repository·라우터를 만들 때, 코드가 어느 계층에 속하는지 애매할 때, 계층 위반이나 SOLID 위반을 리뷰할 때
- 사용하지 않음: 오타·포맷 수정, 프론트엔드만 바꾸는 작업, 환경변수·비밀 작업, 테스트 작성법(`tdd-python-testing`)

## 핵심 규칙 (한 장 요약)

```
web  ──┐
       ├──▶ application ──▶ domain        (화살표 = import 방향)
infra ─┘
```

- `domain`: 순수 파이썬. 프레임워크·IO 라이브러리·`app.config`를 import하지 않는다.
- `application`: 유스케이스와 **Port(외부 통신 인터페이스)를 소유**한다. `infra`·`web`·구체 기술(`sqlalchemy`, `httpx`, `redis`, `fastapi`)을 import하지 않는다.
- `infra`: application의 Port를 **구현**한다(`from app.application.ports... import ...`). 비즈니스 규칙을 판단하지 않는다.
- `web`: HTTP ↔ 유스케이스 변환만 한다. `infra`를 import하지 않고, 유스케이스는 `container`에서 받는다.
- `container.py`(Composition Root)만 모든 계층을 import해 Port와 구현체를 연결한다.

## 절차

1. **계층 결정**: 변경 내용을 `references/layers.md`의 "어디에 두나" 표로 분류한다. 한 변경이 여러 계층에 걸치면 계층별로 나눠 생각한다.
2. **외부 통신이 있나?** DB, 메일, 외부 API, 파일, 시계, ID 생성이 필요하면 `application/ports`에 Port를 먼저 정의한다(`references/ports.md`). 유스케이스가 구체 클라이언트를 직접 만들거나 import하면 안 된다.
3. **규칙은 어디에 두나**: 비즈니스 규칙은 엔티티·값 객체·도메인 서비스 메서드에 둔다. 유스케이스는 Port를 호출해 조율만 한다(빈약한 도메인 모델 금지).
4. **SOLID 점검**: `references/solid-checklist.md`의 위반 신호를 변경분에 대조한다.
5. **검증**: 변경 후 `uv run lint-imports`와 `uv run python scripts/run_gates.py`를 실행한다. 계층 위반은 도구가 잡지만, Port 설계의 적절성과 책임 분리는 도구가 못 잡으므로 직접 점검한다.

## 위반 신호 (이런 코드를 쓰려 하면 멈춘다)

| 신호 | 의미 | 대신 |
| --- | --- | --- |
| `application`에서 SQL 문자열, ORM 모델, `httpx` 호출 | 구체 기술 의존 | Port로 정의하고 infra에서 구현 |
| Port 메서드 시그니처에 ORM 모델·HTTP 응답·Pydantic 스키마 | 기술이 계약에 샘 | 도메인 객체·DTO·원시 타입 사용 |
| 라우터에서 SQL 실행·트랜잭션 처리·비즈니스 분기 | web이 두꺼움 | 유스케이스로 이동 |
| 유스케이스 안에서 `SqlRepo()` 같은 구현체 직접 생성 | DIP 위반 | 생성자 주입, 조립은 container |
| 엔티티는 getter/setter뿐이고 규칙이 서비스에 | 빈약한 도메인 모델 | 규칙을 엔티티 메서드로 |
| `domain`/`application`에서 `app.config` import | 설정 의존 | 필요한 값을 생성자로 주입 |
| 한 클래스·모듈이 규칙+영속화+알림을 모두 처리 | SRP 위반 | 책임별로 분리 |

## 출력과 품질 기준

- 새 Port: `application/ports/<이름>.py`(역할별로 작게), 구현: `infra/...`, 조립: `container.py`
- 통과 기준: `lint-imports` 통과 + 변경분이 위 위반 신호에 없음 + 새 Port마다 Fake 구현이 테스트에 존재(`tdd-python-testing`)
- 판단이 애매하면 구현을 진행하지 말고 선택지와 영향을 사용자에게 묻는다(계층 구조 변경, 새 Aggregate 도입은 사람 승인 대상)

## 참조 (필요할 때만 읽는다)

- `references/layers.md`: 계층별 책임, 어디에 두나 결정표, 디렉터리 구조
- `references/ports.md`: Port 설계 규칙과 코드 예(Repository, UoW, Gateway, 조립)
- `references/solid-checklist.md`: SOLID 원칙별 위반 신호와 수정 예
