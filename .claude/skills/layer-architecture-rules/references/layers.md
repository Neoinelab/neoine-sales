# 계층별 책임과 배치 기준

## 목차

1. 계층별 책임표
2. 어디에 두나 (결정표)
3. 디렉터리 구조
4. DDD 구성요소 매핑

## 1. 계층별 책임표

| 계층 | 책임 | 둘 수 있는 것 | 둘 수 없는 것 |
| --- | --- | --- | --- |
| `domain` | 비즈니스 규칙·불변식, 유비쿼터스 언어 | Entity, Value Object, Aggregate, Domain Service, Domain Event, 도메인 예외 | 프레임워크, DB, HTTP, 설정, 바깥 계층 import |
| `application` | 유스케이스 조율, 트랜잭션 경계, 권한 확인, 이벤트 발행 | 유스케이스(Application Service), Command/Query/DTO, **Port(인터페이스)** | SQL, HTTP 호출, 구체 기술 클래스, infra·web import |
| `infra` | 외부 세계와의 실제 통신 구현 | Port 구현체(Repository, UoW, Gateway, Notifier), ORM 모델, 외부 API 클라이언트, 마이그레이션 | 비즈니스 규칙 판단, web import |
| `web` | 프로토콜 변환(HTTP ↔ 유스케이스) | Router, Pydantic 요청/응답 스키마, 인증 미들웨어, 오류→HTTP 매핑 | 비즈니스 규칙, SQL, infra import |

공통: `app.config`는 `container.py`와 앱 팩토리에서만 읽고, 필요한 값만 생성자로 주입한다.

## 2. 어디에 두나 (결정표)

| 만들려는 것 | 위치 | 이유 |
| --- | --- | --- |
| "주문은 빈 상태로 확정할 수 없다" 같은 규칙 | `domain/<context>/entities.py` 메서드 | 규칙은 엔티티가 지킨다 |
| 금액·기간 같은 값 개념 | `domain/<context>/value_objects.py` (`frozen dataclass`) | 불변·값 동등 |
| 한 엔티티에 속하지 않는 순수 규칙(IO 없음) | `domain/<context>/services.py` | Domain Service |
| "주문을 확정한다" 같은 사용자 시나리오 | `application/<context>/<use_case>.py` (파일당 유스케이스 1개) | 조율만 한다 |
| DB 저장/조회 계약 | `application/ports/repositories.py` | Port는 application이 소유 |
| 트랜잭션 계약 | `application/ports/unit_of_work.py` | 〃 |
| 메일/결제 등 외부 시스템 계약 | `application/ports/<이름>.py` (예: `notifier.py`) | 〃 |
| SQLAlchemy Repository/UoW 구현 | `infra/db/` | 구현 세부 |
| 외부 API 클라이언트와 응답 번역(ACL) | `infra/external/` | 외부 모델을 도메인 언어로 번역 |
| ORM 모델 | `infra/db/models.py` | 도메인 엔티티와 분리 |
| Alembic 마이그레이션 | `backend/alembic/` | infra 관심사 |
| 라우터, 요청/응답 스키마, 오류 매핑 | `web/` | 프로토콜 변환 |
| 구현체 선택·연결 | `container.py` | 유일한 조립 지점 |

## 3. 디렉터리 구조

```
backend/src/app/
├─ domain/<context>/       entities.py value_objects.py services.py events.py errors.py
├─ application/
│  ├─ ports/               repositories.py unit_of_work.py notifier.py ...
│  └─ <context>/           commands.py <use_case>.py
├─ infra/                  db/ (models.py repositories.py uow.py)  messaging/  external/
├─ web/                    routers/ schemas.py dependencies.py error_handlers.py
├─ config/                 base.py profiles.py
├─ container.py            조립(모든 계층 import 가능)
└─ main.py                 FastAPI 앱 팩토리
```

Bounded Context(`customer`, `order` 등)는 `domain/<context>`와 `application/<context>`로 세로 분할한다. 컨텍스트 간 통신은 Domain Event나 application의 Port로만 한다.

## 4. DDD 구성요소 매핑

| 요소 | 위치 | 메모 |
| --- | --- | --- |
| Aggregate Root | domain | 외부는 Root를 통해서만 접근, 트랜잭션 1개 = Aggregate 1개 |
| Factory | domain (`@classmethod create`) | 복잡한 생성과 불변식 보장 |
| Domain Event | domain(정의) / application(핸들러) | 후속 처리는 느슨하게 |
| Repository | application/ports(인터페이스) + infra(구현) | Aggregate Root 단위로만 정의 |
| Unit of Work | application/ports + infra | 여러 Repository의 원자적 커밋 |
| Anti-Corruption Layer | infra/external 어댑터 내부 | 외부 모델이 안쪽으로 새지 않게 |

모든 모듈에 전술 패턴을 다 적용하지 않는다. 규칙이 복잡한 핵심 도메인은 엄격히, 단순 CRUD 지원 도메인은 Port/UoW만 유지하고 가볍게 구현한다.
