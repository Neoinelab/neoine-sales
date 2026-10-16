# 실제 DB가 필요한 테스트용 임시 DB fixture

## 목차

1. 현재 상태
2. 동작 방식
3. 사용법
4. 건너뛰기와 실패의 기준
5. 새 Repository 구현에 계약 테스트 적용하기
6. 주의

## 1. 현재 상태

**구현되어 있다.** 파일 위치는 아래와 같다.

| 파일 | 역할 |
| --- | --- |
| `backend/tests/support/database.py` | 임시 DB 생성·삭제, 마이그레이션 적용, 롤백되는 세션, 관리자 접속 URL 결정 |
| `backend/tests/conftest.py` | 세션당 한 번 임시 DB를 만들고 마이그레이션을 적용하는 `test_database_url` fixture |
| `backend/tests/unit/infra/conftest.py` (구 `tests/integration/conftest.py`) | 테스트마다 롤백되는 `session` fixture(infra 어댑터 클래스 단위 테스트용) |
| `backend/tests/unit/repositories/conftest.py` (구 `tests/contracts/conftest.py`) | 같은 계약 단위 테스트를 Fake와 SQL 구현 양쪽에 적용하는 `case` fixture |
| `backend/tests/functional/conftest.py` | feature end-to-end용 ASGI 클라이언트(`api`)와 임시 DB 연결 |

> 테스트 재배치(2026-10-15) 중에는 구 경로(`tests/contracts`, `tests/integration`, `tests/e2e`)가 남아 있을 수 있다. 새 테스트는 구 경로에 만들지 않는다.

## 2. 동작 방식

- 컨테이너(Testcontainers)는 쓰지 않는다. **실제로 설치된 PostgreSQL**에서 테스트 전용 DB를 임시로 만들고 지운다.
- **관리자 접속 URL 결정**(`resolve_admin_url`)
  1. 환경변수 `TEST_DATABASE_ADMIN_URL`이 있으면 그것을 쓴다(CI).
  2. 없고 앱 프로파일이 `local`이면, 앱 설정의 접속 정보에서 DB 이름만 maintenance DB(`postgres`)로 바꿔 쓴다. 로컬 개발자는 추가 설정이 필요 없다.
  3. 그 외(프로파일이 dev/product이거나 설정이 없음)는 통합 테스트를 건너뛴다. **dev/product DB에는 절대 접속하지 않는다.**
- 세션마다 `app_test_<무작위>` DB를 `CREATE DATABASE`로 만들고, **Alembic 마이그레이션을 `head`까지 적용**(마이그레이션도 같이 검증된다)하고, 세션이 끝나면 `DROP DATABASE`한다. 이름이 매번 달라 병렬 빌드가 충돌하지 않는다.
- 테스트마다 바깥 트랜잭션을 열고(SAVEPOINT 모드) 끝나면 롤백해 서로 격리한다. Repository의 `add`/`update`는 SAVEPOINT 안에서 flush하므로 제약 위반이 나도 같은 세션을 계속 쓸 수 있다.
- 개발 DB(`neoinesales`)의 데이터는 읽지도 쓰지도 않는다.

## 3. 사용법

```
cd backend
uv run pytest                          # 단위 + 통합 전체
uv run pytest -m integration           # 실제 PostgreSQL이 필요한 테스트만
uv run pytest -m "not integration"     # 빠른 단위 테스트만(DB 불필요)
uv run pytest -rs                      # 건너뛴 테스트와 그 이유를 표시
```

- 필요한 것: PostgreSQL 실행, 접속 role에 `CREATEDB` 권한(`ALTER ROLE <role> CREATEDB;`).
- 실제 DB가 필요한 테스트는 `pytestmark = pytest.mark.integration`을 붙인다. infra 어댑터 클래스 하나는 `tests/unit/infra/`(`session` fixture로 Repository 생성), feature 전체는 `tests/functional/`(BDD, `references/bdd.md`).
- 마이그레이션이 필요한 변경(테이블·제약)은 마이그레이션 파일을 먼저 만들고, 제약 동작은 해당 Repository 단위 테스트(`tests/unit/infra/`)에, 업그레이드·다운그레이드 왕복은 functional `tests/functional/schema/test_migrations.py` 시나리오로 추가한다.

## 4. 건너뛰기와 실패의 기준

- **건너뜀**: 관리자 접속 정보가 없을 때, DB에 접속할 수 없을 때(`OSError`), DB 오류/권한 부족(`SQLAlchemyError`). 이유는 `-rs`로 확인한다.
- **실패**: 그 밖의 모든 예외(코드 버그, 이벤트 루프 문제 등). 예전에 `asyncio.run`이 실행 중인 루프에서 호출되어 `RuntimeError`가 났을 때 **통합 테스트 68개가 조용히 건너뛰어진 적이 있다.** 그래서 광범위한 예외를 건너뜀으로 처리하지 않는다.
- 완료 보고에는 **건너뛴 테스트 수가 0인지** 반드시 확인한다. 건너뛴 채로 "통과"라고 보고하지 않는다.

## 5. 새 Repository 구현에 계약 테스트 적용하기

1. `tests/unit/repositories/conftest.py`의 `IMPLEMENTATIONS`와 `build_case`/`build_sql_case` 계열에 새 구현을 추가한다.
2. 선행 데이터가 필요하면(예: Deal이 참조하는 고객) `RepositoryCase.prepare`로 만든다.
3. 같은 계약 테스트(`test_repository_contract.py`, `test_deal_repository_contract.py`)가 새 구현에도 그대로 돌아야 한다. 테스트를 구현에 맞춰 약하게 고치지 않는다.

## 6. 주의

- 동기 fixture에서 코루틴을 실행할 때는 `run_async`(별도 스레드)를 쓴다. 직접 `asyncio.run`을 쓰면 pytest-asyncio가 만든 루프와 충돌할 수 있다.
- 임시 DB 이름은 코드가 생성한 값만 SQL에 넣는다(사용자 입력 금지).
- Windows 개발자는 WSL2의 PostgreSQL 사용을 권장한다(개발 가이드 3.4절).
