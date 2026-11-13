# Feature 명세(SDD)와 BDD 테스트 케이스

이 폴더는 feature마다 **명세(SDD, Spec-Driven Development)** 와 **주요 business use case의 BDD 테스트 케이스**를 한 파일로 둡니다. `feature-planner`가 작성하고, 사용자가 확인(컨펌)한 뒤에만 테스트·구현 단계로 넘어갑니다. `test-engineer`는 이 문서의 테스트 케이스를 그대로 테스트 코드로 옮깁니다(2026-11-09 하네스 변경).

## 규칙

- 파일: `docs/features/<feature-slug>.md` (feature 하나 = 파일 하나, slug는 영문 소문자·하이픈).
- feature 코드: 영문 대문자 2~4자(아래 색인에 등록, 중복 금지). 예: `LC`(계약관리).
- 테스트 코드 번호: `<feature 코드>-<세 자리 번호>` (예: `LC-001`). 한 번 붙인 번호는 다른 케이스에 다시 쓰지 않습니다(케이스를 없애면 "폐기"로 표시하고 번호는 비워 둠).
- 규칙 번호: `<feature 코드>-R<번호>` (예: `LC-R3`), use case 번호: `<feature 코드>-UC<번호>`. 테스트 케이스는 검증하는 규칙·use case 번호를 적습니다.
- 테스트 케이스는 Given/When/Then 한국어 문장으로 씁니다. Given이 없으면 생략합니다. When은 하나(한 케이스 = 한 행동)입니다.
- 테스트 코드에는 같은 번호를 주석으로 남깁니다(`테스트 코드: LC-001`). 문서의 "테스트 위치" 칸은 `test-engineer`가 채웁니다.
- 문서가 바뀌면(규칙 변경) 영향을 받는 테스트 케이스 번호를 변경 이력에 적습니다.

## 파일 형식 (템플릿)

```markdown
# <Feature 이름>   (feature 코드: XX, 상태: 초안 | 확정(YYYY-MM-DD 사용자 확인))

## 1. 개요
- 목적, 사용자(역할), 범위 / 범위 밖, 관련 화면·메뉴

## 2. 명세 (SDD)
### 2.1 용어
### 2.2 데이터 모델     (엔티티·필드·제약, 관련 테이블)
### 2.3 비즈니스 규칙   (XX-R1, XX-R2 … 관찰 가능한 문장)
### 2.4 상태와 전이     (있으면 표 또는 다이어그램)
### 2.5 권한           (역할 × 행동 표)
### 2.6 API 계약       (경로·메서드·요청·응답·오류 type·상태 코드)
### 2.7 화면 동작       (frontend 규칙)
### 2.8 오류와 메시지

## 3. Business use case
### XX-UC1 <이름>
- 행위자 / 사전 조건 / 기본 흐름 / 대안·예외 흐름 / 결과

## 4. BDD 테스트 케이스

| 코드 | 케이스 | 규칙·UC | 층 | 테스트 위치 |
| --- | --- | --- | --- | --- |
| XX-001 | Won인 Deal의 미발급 계약을 발급하면 발급(신규)가 된다 | XX-R2, XX-UC2 | backend | (test-engineer가 채움) |

### XX-001 <케이스 이름>
- Given <사전 상태>
- When <행동 하나>
- Then <관찰 가능한 결과>

## 5. 변경 이력
| 날짜 | 변경 | 영향 테스트 코드 |
```

`층`은 `backend`(Fake를 쓰는 유스케이스 단위 테스트), `frontend`(Fake 게이트웨이를 쓰는 Vitest 화면 테스트), `both`(양쪽에 각각 구현) 중 하나입니다.

## 색인

feature 목록은 2026-11-09 사용자 확인(질문 Q1~Q6 추천안 채택: 경로별 권한은 각 feature 2.5·PL은 전체 경로 검사, 하네스·배포 도구 테스트는 feature 대상 제외(주석 형식은 적용), DE·DL은 넘칠 때만 분할, Dashboard 코드 DSH, UI는 별도 feature, 확인은 묶음 단위). 진행 순서·묶음은 `artifacts/10-analysis/feature-catalog-plan.md`를 봅니다.

| feature 코드 | 문서 | 상태 |
| --- | --- | --- |
| PL | [platform-common.md](platform-common.md) (플랫폼 공통: 권한 표·HTTP 관례·API 계약·화면 접근) | 확정(2026-11-09) |
| TM | [server-time.md](server-time.md) (서버 시간·업무 날짜) | 확정(2026-11-09) |
| SC | [schema-migration.md](schema-migration.md) (DB 스키마·마이그레이션 기준선) | 확정(2026-11-13 사용자 확인) |
| AU | [login-session.md](login-session.md) (로그인·세션·대체 로그인) | 확정(2026-11-09) |
| SU | [initial-setup.md](initial-setup.md) (최초 설정) | 확정(2026-11-13) |
| IN | [integration-settings.md](integration-settings.md) (연동 설정: AD 서버·저장 위치) | 확정(2026-11-09) |
| US | [user-management.md](user-management.md) (사용자 관리) | 확정(2026-11-13 사용자 확인) |
| ME | [my-account.md](my-account.md) (내 정보) | 확정(2026-11-09) |
| CD | [status-forecast-codes.md](status-forecast-codes.md) (Status·Forecast 코드) | 확정(2026-11-10) |
| CL | [choice-catalogs.md](choice-catalogs.md) (선택 목록: BANT Label·Action 유형·Vendor) | 확정(2026-11-13 사용자 확인) |
| CT | [contacts.md](contacts.md) (고객·파트너 연락처) | 확정(2026-11-10) |
| DE | [deal-entry.md](deal-entry.md) (Deal 등록·수정) | 확정(2026-11-13 사용자 확인) |
| DD | [deal-detail.md](deal-detail.md) (Deal 상세·변경 적용·이력·삭제) | 확정(2026-11-13 사용자 확인) |
| DL | [deal-list.md](deal-list.md) (Deal 목록·검색) | 확정(2026-11-10) |
| RK | [deal-risk.md](deal-risk.md) (경고·파생 값·경고 기준) | 확정(2026-11-10) |
| AC | [deal-actions.md](deal-actions.md) (Action 등록·수정·삭제) | 확정(2026-11-13 사용자 확인) |
| NA | [next-action.md](next-action.md) (Next Action 상태·Action 검색) | 확정(2026-11-10) |
| AT | [deal-attachments.md](deal-attachments.md) (Deal 첨부 파일) | 확정(2026-11-10) |
| FC | [forecast.md](forecast.md) (Forecast: 실시간·월말 스냅숏) | 확정(2026-11-13 사용자 확인) |
| DSH | [dashboard.md](dashboard.md) (Dashboard) | 확정(2026-11-11) |
| RQ | [report-query.md](report-query.md) (Reports 조회 엔진·디자이너 작성) | 확정(2026-11-13 사용자 확인) |
| RS | [saved-reports.md](saved-reports.md) (저장 리포트·결과 배치) | 확정(2026-11-11) |
| RC | [report-charts.md](report-charts.md) (Reports 차트) | 확정(2026-11-11) |
| PA | [partner-activity.md](partner-activity.md) (파트너 Activity) | 확정(2026-11-11) |
| LC | [license-contracts.md](license-contracts.md) (계약관리) | 확정(2026-11-13 사용자 확인) |
| UI | [ui-common.md](ui-common.md) (공통 입력·표시 컴포넌트, frontend 전용) | 확정(2026-11-11) |

## feature 경계

API 경로는 `/api/v1/` 접두어를 뺀 값입니다. "범위 밖" 칸은 그 동작을 맡는 feature입니다. 여러 feature가 함께 쓰는 규칙은 소유 feature의 규칙 번호(`XX-R번호`)를 다른 문서가 가리킵니다(복사하지 않음).

| 코드 | 이름 | 범위(메뉴·API 경로 접두어) | 범위 밖 / 다른 feature로 |
| --- | --- | --- | --- |
| PL | 플랫폼 공통 | 라우트 가드(`RequireAuth`·`RequireWrite`·`RequireAdmin`)·상단 메뉴·Admin 레이아웃, 역할 3종 권한 표의 전체 경로 검사, CSRF 헤더·`problem+json` 오류 형식·id 경로 파라미터·NUL 문자 거부, `/healthz`·`/readyz`, `openapi.json` 드리프트·역할/인증 표기, 프로파일 설정 검증 | 각 경로의 역할별 허용 여부(각 feature 2.5), 하네스 도구·배포 스크립트(feature 아님) |
| TM | 서버 시간·업무 날짜 | `/time`, 응답 시각 오프셋(`ServerDateTime`), 업무 날짜·업무 시각, 프런트 서버 동기 시계·`useToday`·시각 표기(`shared/format.ts`) | 각 화면의 기본 날짜 사용(각 feature) |
| SC | DB 스키마·마이그레이션 | 기준선 리비전, 빈 DB `upgrade head`, 리비전 그래프, head = ORM, bigint identity PK 공통 규칙, 기본 시드 | 테이블별 컬럼·제약(소유 feature 2.2와 스키마 테스트), product 적용(사람 승인) |
| AU | 로그인·세션 | `/login` 화면, `/auth/login`·`/auth/logout`·`/auth/me`·`/auth/config`, AD search-then-bind·앱 계정 로그인·대체 로그인·admin AD 경고 팝업, 시도 제한, 세션 쿠키, 요청마다 활성·역할 재확인, 예약 아이디 | 최초 설정(SU), AD 설정 저장(IN), 비밀번호 변경(ME)·재설정(US) |
| SU | 최초 설정 | `/setup` 화면, `/auth/setup/*`(인증 방식 → AD → 저장 위치 → 첫 admin) | 설정 뒤 AD·저장 위치 변경(IN) |
| IN | 연동 설정 | Admin > 연동 설정, `/settings/directory*`·`/settings/storage*`, Base DN 자동 탐색, 바인드 비밀번호 암호화·마스크, local 모드 거부 | 첨부 저장·다운로드 동작(AT·LC) |
| US | 사용자 관리 | Admin > 사용자, `/users*`(등록·목록·상태 필터·역할 변경·정보 수정·비밀번호 재설정·퇴사/삭제), `/user-options` | 내 정보(ME), 로그인(AU) |
| ME | 내 정보 | 우측 상단 사용자 메뉴, `/me` 화면, `/me/profile`·`/me/password` | admin의 다른 사용자 수정(US) |
| CD | Status·Forecast 코드 | Admin > Deal 관리의 코드, `/codes*`(등록·이름·순서·삭제·사용 현황), 기본 시드 | Status↔Forecast 동기화 규칙(DD) |
| CL | 선택 목록 | Admin > Deal 관리의 BANT Label·Action 유형·Vendor, `/bant-labels*`·`/action-types*`·`/vendors*`, `{id}`/`{name}` 선택(`CatalogChoice`) 규칙 | Deal·Action 저장 때 이름으로 생성되는 결과(DE·AC) |
| CT | 연락처 | Admin > 연락처, `/contacts*`, 같은 사람 판정, 연락처 선택기(`ContactPicker`), 참조 중 삭제 거부 | Deal에 연락처 연결(DE), 파트너 회사 목록 사용(PA) |
| DE | Deal 등록·수정 | `/deals/new`·`/deals/:code/edit` 폼, `POST /deals`·`PATCH /deals/{code}`, 필드 검증·Deal code 발급·Owner 자격·Vendor(필수)·Solution(선택)·BANT 선택·고객/파트너 연결 | Won 진입·이탈 계약 처리(LC), 동기화 규칙(DD), `status_changed_on`(RK) |
| DD | Deal 상세·변경 적용·이력·삭제 | `/deals/:code` 상세(요약 바·정보/연락처/BANT 카드·인라인 수정·탭 틀), `GET /deals/{code}`, `/deals/{code}/changes`·`/history`·`/deletion-impact`, `DELETE /deals/{code}`, Status·Forecast 동기화 규칙, 변경 이력 기록 | Actions 탭(AC·NA), 첨부 패널(AT), 계약 건수·계약 함께 삭제(LC) |
| DL | Deal 목록·검색 | `/deals` 목록(필터·Quarter/Forecast 다중 선택·정렬·키워드·조건 기억·Quick View·인라인 편집 진입), `GET /deals`, `/deals/years`, `/deals/updated-periods` | 인라인 변경 적용 자체(DD), 경고 판정식(RK), Dashboard 이동 주소 생성(DSH) |
| RK | 경고·파생 값 | 기한 초과·미업데이트 판정과 범례, Status 체류 일수·`status_changed_on`, 최종 업데이트·Next Action 기준 행, `/alert-settings`(Admin > 경고 기준) | Next Action 상태 변경(NA), 목록 필터 UI(DL) |
| AC | Action 등록·수정·삭제 | 상세 Actions 탭 입력·목록, `/deals/{code}/actions`(등록·기본 목록), `/deal-actions/{id}`(수정·삭제), Status 변경 동반·이전 Next Action 종료, Action 유형 선택, 등록·수정의 수행일 지정 | Next Action 상태·검색 조건(NA), 계약 처리(LC) |
| NA | Next Action 상태·Action 검색 | `/deal-actions/{id}/next-action-status`, Action 목록 검색 조건(`next_action_status`·기간 등), Actions 탭 상태 표시·검색 바 | Deal 목록의 Next Action 상태 필터(DL) |
| AT | Deal 첨부 파일 | 상세 첨부 패널, `/deals/{code}/attachments`, `/attachments/{id}`·`/download`, 파일 이름·확장자 규칙, 같은 이름 처리, 저장 실패 정리 | 계약 첨부(LC), 저장 위치 설정(IN) |
| FC | Forecast | `/forecast` 화면, `/forecast/summary`, `/forecast/snapshots*`, 월말 스냅숏 스케줄러(`PeriodicTask`·`JobLock`) | Deal 조건 해석(DL) |
| DSH | Dashboard | `/dashboard` Status·Forecast 탭, `/dashboard/summary`, Drill-down 주소 | 이동한 Deal 목록의 조건 해석(DL) |
| RQ | Reports 조회·디자이너 | `/reports/new` 작성 탭(필드·컬럼·조건·범위·결과 표·SQL 보기), `/reports/fields`, `/reports/query`, 정의 검증·SQL 생성·시간 제한·합계, 저장 정의 JSON 읽기·예전 형식 변환 | 저장·목록·보기·깨진 정의 응답(RS), 차트(RC) |
| RS | 저장 리포트 | `/reports` 목록, `/reports/:id` 보기·`/reports/:id/edit`, `/reports`·`/reports/{id}`·`/copy`·`/run`·`/layout`, 권한·revision·결과 타일 배치(차트 없는 리포트 포함) | 정의 검증·저장 정의 읽기 변환(RQ), 차트 검증과 저장·복제 때의 차트 값·`chart_kind`·`chart_problem`(RC) |
| RC | Reports 차트 | 차트 타일·설정 패널(33종), 요청 `chart` 검증, 저장·덮어쓰기·복제 때의 차트 값·`chart_kind`·`chart_problem`, 저장 차트 읽기 변환, 편집 화면 저장 안 됨·되돌리기의 차트 부분 | 차트를 싣는 저장 API의 경로·권한·판정 순서와 결과 배치(RS) |
| PA | 파트너 Activity | `/partner-activities`, `/partner-meetings*` | 파트너 연락처 관리(CT) |
| LC | 계약관리 | `/contracts`, `/license-contracts*`, `/license-contract-attachments*`, Deal Won 진입·이탈 계약 처리, Deal 응답·삭제 영향의 계약 필드 | (확정 문서 1장 참고) |
| UI | 공통 입력·표시 | `DateInput`(yyyymmdd 입력)·금액 입력·금액 표시·콤보박스·다중 선택·모달·확인 대화상자·페이저·무한 스크롤·정렬 머리글·탭·알림 줄·화면 이동 알림·기본 입력 필드·키·값 격자와 본문 여백 CSS·빈 첫 실행 확인(UI-R1~R39) | 각 화면의 사용 규칙(각 feature), 사용자 선택 `UserSelect`(DE·US), 기간 선택 `PeriodField`(NA-R26), 오류 배너·레이아웃(PL) |
