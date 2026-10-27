/**
 * 게이트웨이 인터페이스(A-0 계약). 계획 4.1·4.4장.
 * 화면은 `data/*` 훅만 쓰고, 훅은 이 인터페이스만 안다. 구현은 HTTP(`gateway/http`)이며, 테스트는 Fake(`src/test/fake`)로 바꿔 끼운다.
 *
 * ── 오류 규약 ─────────────────────────────────────────────
 * 실패는 모두 `ApiError`(shared/api/problem.ts)를 **throw**(reject)한다. 반환값에 오류를 싣지 않는다.
 * - problem 필드: `type = 'https://sales.neoine.test/problems/<kind>'`, `title`, `status`, `detail`.
 *   `detail`에 사용자에게 보일 한국어 문구 **그대로**를 넣는다(ErrorBanner는 `error.message`=detail을 표시).
 *   `errors` 배열은 쓰지 않는다(쓰면 message에 '필드: 문구'가 덧붙는다).
 * - 상태 코드: 401 미로그인/잘못된 로그인, 403 권한 없음(또는 퇴사자 로그인), 404 없음, 409 충돌·참조 중·순서 위반,
 *   422 검증 실패, 503 저장소 장애.
 * - 알려진 kind: `unauthorized` `forbidden` `not-found` `validation` `conflict` `file-exists`(409, 같은 이름 파일)
 *   `storage-unavailable`(503) `directory-verification-failed`(422, `stage` 포함) `csrf`(403, 요청 헤더 누락)
 *   `too-many-attempts`(429, 로그인 시도 제한) `network`(상태 0, 서버에 닿지 못함) `malformed-response`(502, 응답이 계약과 다름)
 *   `not-implemented`(501, HTTP 어댑터에 아직 없는 기능) `directory-unavailable`(503, AD 장애) `not-ready`(503) `http-error`
 *   `domain-error`(400). HTTP 어댑터는 서버 kind 중 변환표에 없는 것을 그대로 통과시키므로 화면은 알 수 없는 kind도
 *   `error.message`로 보여 줄 수 있어야 한다. 화면은 `error.kind`로 분기한다.
 * - 모든 메서드는 **로그인 사용자(session)** 가 필요하다(auth.login/quickLogin, setup.* 제외). 없으면 401.
 *
 * ── 공통 불변식 ───────────────────────────────────────────
 * 1. 쓰기는 sales/admin만(user는 403). `shared/model/permissions.ts`의 함수와 같은 규칙으로 판단한다.
 * 2. **모든 변경은 Deal History를 기록한다**(R02): Deal 등록, Status/Forecast/금액/Expected Close/Owner/파트너/
 *    고객 연락처/BANT Label/기타 필드, Action 등록·수정·삭제, Next Action 상태 변경, 첨부 업로드·교체·삭제. 변경자는 현재 로그인 사용자,
 *    시각은 서버 시각(Fake는 시계의 now()). 값이 바뀌지 않은 요청은 기록하지 않는다. 실패한 요청은 아무것도 바꾸지 않는다(원자적).
 * 3. Deal의 `updatedAt`은 Deal 자신의 필드/연결 정보(파트너·연락처·Label·첨부)가 바뀔 때 갱신된다.
 *    `DealRow.lastUpdatedAt` = 모든 Action(진행사항만 있는 것 포함)의 가장 최근 수행시각, Action이 없으면 `createdAt`.
 *    Deal 자체의 수정(`updatedAt`)은 반영하지 않으므로 인라인 수정으로 미업데이트가 풀리지 않는다.
 * 4. Status ⇄ Forecast 불변식: `contract_completed` ⇔ `won`. 단일 변경은 `applyChange`/`ActionInput.statusChanges`(최대 2개, 순서대로 판정)의
 *    sync 규칙(`planChange`/`finalizePlan`)으로, 폼 저장(`create`/`update`)은 최종 값이 불변식을 만족해야 한다
 *    (어긋나면 422 "Status와 Forecast의 동기화가 맞지 않습니다.").
 * 5. Action은 **등록 시점의 Status/Forecast key를 저장**한다(statusChanges가 있으면 적용 후 값). 수정은 이 값을 바꾸지 않는다.
 * 6. 연락처 입력: 회사명·담당자명·이메일·전화에 공백 문자가 있으면 422 "공백은 입력할 수 없습니다."; 이메일·전화 형식 오류 422; 회사/이름은
 *    대소문자 구분 없이 같은 것으로 본다. 같은 사람 판정은 `findSamePerson`.
 * 7. Deal code는 `YYYYMMDD-XXXX`(`DEAL_CODE_PATTERN`), 등록일(오늘) + 대문자/숫자 4자리, 기존 code와 겹치면 재추출.
 * 8. 목록 조회는 읽기 전용이며 부수효과가 없다. 반환 객체는 호출자가 바꿔도 저장소에 영향이 없다(복사본).
 */

import type {
  ActionInput,
  ActionQuery,
  NextActionStatusInput,
  ActionTypeWithUsage,
  ActionUpdateInput,
  AlertSettings,
  ApplyChangeRequest,
  Attachment,
  BantCategory,
  BantLabelWithUsage,
  CodeCreateInput,
  CodeKind,
  CodeSet,
  CodeWithUsage,
  Contact,
  ContactInput,
  ContactKind,
  ContactListQuery,
  ContactRow,
  DashboardQuery,
  DashboardSummary,
  DealAction,
  DealDeletionImpact,
  DealDetail,
  DealInput,
  DealListQuery,
  DealPatch,
  DealRow,
  DirectorySettings,
  DirectorySettingsInput,
  DownloadedFile,
  ForecastQuery,
  ForecastSnapshotInfo,
  ForecastSummary,
  HistoryEntry,
  HistoryQuery,
  Me,
  Page,
  UpdatedPeriods,
  DealYears,
  SetupState,
  StorageSettings,
  UploadInput,
  User,
  UserCreateInput,
  Role,
  UserListFilter,
  UserOptionsQuery,
  UserRef,
  UserRemoveResult,
  Vendor,
} from '../shared/model/types'
import type { CoChange } from '../shared/model/sync'
import type { ReportCatalog, ReportQueryInput, ReportResult } from '../shared/model/reportTypes'

/** `deals.applyChange` 결과. */
export interface ApplyChangeResult {
  deal: DealDetail
  /** 요청 필드 외에 함께 바뀐 값. */
  coChanged: CoChange[]
  /** 알림 문구(함께 바뀐 값이 있을 때만). 예: "Status가 '계약완료'로, Forecast가 'Won'으로 함께 변경되었습니다." */
  notice: string | null
}

/** `attachments.upload` 결과. onExists='skip'이고 같은 이름이 있으면 skipped(변화 없음, History 없음). */
export type UploadResult =
  | { outcome: 'uploaded'; attachment: Attachment }
  | { outcome: 'replaced'; attachment: Attachment }
  | { outcome: 'skipped' }

export interface AuthGateway {
  /** 현재 세션 사용자. 로그인 전이면 401. */
  me(): Promise<Me>
  /**
   * 빈 아이디/비밀번호 422 "아이디와 비밀번호를 입력하세요.", 없는 아이디 401
   * "아이디 또는 비밀번호가 올바르지 않습니다.", 퇴사자 403 "퇴사한 사용자는 로그인할 수 없습니다."
   * 성공 시 lastLoginAt 갱신(서버가 세션 쿠키를 설정한다).
   */
  login(loginId: string, password: string): Promise<Me>
  /** 빠른 로그인(`QUICK_LOGIN_USERS`). 퇴사자·없는 id는 login과 같은 오류. */
  quickLogin(userId: number): Promise<Me>
  logout(): Promise<void>
  /** 로그인 화면용 서버 설정(로그인 전에도 읽는다). `quickLogin`이 true일 때만 빠른 로그인 버튼을 그린다. */
  config(): Promise<AuthConfig>
}

export interface AuthConfig {
  quickLogin: boolean
  /** 최초 설정(AD 서버 또는 첫 관리자)이 아직 끝나지 않았다. 서버 `needs_directory_setup || needs_admin_setup`. */
  needsSetup: boolean
}

export interface SetupGateway {
  status(): Promise<SetupState>
  /** 1단계. 항상 가능(재저장 허용). directoryDone=true. */
  saveDirectory(input: DirectorySettingsInput): Promise<void>
  /** 2단계. directoryDone이 false면 409. 검증은 settings.storage.save와 같다. */
  saveStorage(path: string): Promise<void>
  /** 2단계 쓰기 테스트. 로그인·1단계 불필요, 저장 없이 검증만(저장소 장애 시뮬레이션 시 503). */
  testStorage(path: string): Promise<void>
  /** 3단계. storageDone이 false면 409, 이미 adminDone이면 409. 성공하면 그 관리자로 로그인된 상태가 된다. */
  registerAdmin(loginId: string, password: string): Promise<Me>
}

export interface DealsGateway {
  list(query: DealListQuery): Promise<Page<DealRow>>
  /** 최종 업데이트 기간 프리셋을 서버 업무 날짜 기준으로 푼 범위. 로그인한 누구나 읽는다. */
  updatedPeriods(): Promise<UpdatedPeriods>
  /** 모든 로그인 사용자. Deal이 없으면 earliestYear null. */
  years(): Promise<DealYears>
  /** 없으면 404 "Deal을 찾을 수 없습니다." */
  get(code: string): Promise<DealDetail>
  /** 삭제 확인 팝업의 연쇄 삭제 건수. */
  impact(code: string): Promise<DealDeletionImpact>
  /**
   * 등록. owner는 재직 sales여야 한다(아니면 422 "Owner는 재직 중인 영업 담당자여야 합니다.").
   * customer 필수(연락처 규칙 적용), partner 선택. History 'Deal 등록' 1건. 연락처는 contacts 규칙으로 갱신/생성.
   */
  create(input: DealInput): Promise<DealDetail>
  /**
   * 폼/카드 단위 수정(보낸 필드만). Owner를 퇴사자로 바꾸려는 시도·유지 저장은 422
   * "퇴사한 사용자는 Owner로 지정할 수 없습니다. 다른 담당자를 선택하세요." (Owner 필드를 보낸 경우만 검사).
   * partner 교체/제거는 이전 링크를 비활성(unlinkedAt)으로 남긴다. 변경된 필드마다 History.
   */
  update(code: string, patch: DealPatch): Promise<DealDetail>
  /**
   * 단일 필드 변경(Inline Update, 상세 현재값 바). 4개 필드만. Status/Forecast는 sync 규칙 적용:
   * 사용자 답(resolution)이 필요한데 없거나 틀리면 422 "함께 바꿀 값을 선택하세요." /
   * "Won·계약완료로 바꾸려면 매출금액과 매출일이 필요합니다." 금액은 1 이상 정수(422 "매출금액은 1원 이상의 정수로 입력하세요."),
   * 날짜 필수(422 "Expected Close를 입력하세요."). needRevenue의 revenue는 Deal의 revenueAmount/revenueDate로 저장한다.
   */
  applyChange(code: string, request: ApplyChangeRequest): Promise<ApplyChangeResult>
  /**
   * 삭제. canDeleteDeal 아니면 403. confirmCode가 code와 정확히 같지 않으면 422 "Deal code가 일치하지 않습니다."
   * 성공하면 Deal·History·Action·첨부를 모두 제거한다(History 보존 없음).
   */
  remove(code: string, confirmCode: string): Promise<void>
}

export interface ContactsGateway {
  /** 구분별 distinct 회사명(대소문자 무시, `distinctCompanies`). */
  companies(kind: ContactKind): Promise<string[]>
  /** 회사명(대소문자 무시)의 담당자 목록(`contactsOfCompany`) + 연결 Deal 수. */
  byCompany(kind: ContactKind, company: string): Promise<ContactRow[]>
  /** admin만(sales·user 403). 관리 화면 전용이며 Deal 화면의 선택은 `companies`·`byCompany`를 쓴다. */
  list(query: ContactListQuery): Promise<Page<ContactRow>>
  /** admin만. 규칙 위반 422(공백·이메일 형식·필수), 같은 사람이 이미 있으면 409 "이미 등록된 연락처입니다." */
  create(kind: ContactKind, input: ContactInput): Promise<Contact>
  /** admin만(Deal 화면의 연락처 수정은 deals.create/update의 ContactDraft 경로). 이 연락처를 쓰는 모든 Deal에 반영. */
  update(id: number, input: ContactInput): Promise<Contact>
  /** admin만. 참조 Deal이 있으면 409 "연결된 Deal이 N건 있어 삭제할 수 없습니다." */
  remove(id: number): Promise<void>
}

export interface ActionsGateway {
  /** 해당 Deal의 Action. 기본 정렬 수행일시 최신순. Deal이 없으면 404. */
  list(dealCode: string, query: ActionQuery): Promise<DealAction[]>
  /**
   * 등록. 진행사항·Next Action은 각각 선택이고 둘 다 비면 422 "진행사항 또는 Next Action을 입력하세요."
   * Next Action이 있으면 Due Date 필수(422 "Due Date를 입력하세요."), 없는데 Due Date를 주면 422 "Next Action 없이 Due Date를 입력할 수 없습니다.".
   * statusChanges가 있으면(순서대로 각각 판정) applyChange와 같은 규칙으로 Deal도 갱신하고, Action에는 **적용 후** Status/Forecast key를 저장.
   * History: Action 1건 + (바뀌었으면) Status/Forecast 변경.
   */
  create(dealCode: string, input: ActionInput): Promise<DealAction>
  /**
   * 이전 Action도 수정 가능하나 **담당자 본인(sales)과 admin만** 가능하다.
   * 다른 sales·user는 403 "본인 Action 또는 admin만 수정할 수 있습니다."(user는 기본 403 문구).
   * 등록 시점 Status/Forecast·수행일시·담당자는 유지. 내용이 바뀌었을 때만 History 기록.
   */
  update(actionId: number, input: ActionUpdateInput): Promise<DealAction>
  /** 담당자 본인(sales)과 admin만. 다른 sales는 403 "본인 Action 또는 admin만 삭제할 수 있습니다.". History 기록. */
  remove(actionId: number): Promise<void>
  /**
   * Next Action 상태 변경(작성자 본인·admin만, 아니면 403). 종료할 때 memo가 있으면 Memo 뒤에 덧붙는다.
   * 같은 상태 409, Next Action이 없는 Action 409, Open으로 되돌리면서 memo를 주면 422.
   */
  changeNextActionStatus(actionId: number, input: NextActionStatusInput): Promise<DealAction>
}

export interface ActionTypesGateway {
  /** 기본 유형(통화·미팅·이메일·데모·제안·협상·계약·기타) 먼저, 직접 만든 유형은 이름순. 읽기: 모든 역할. */
  list(): Promise<ActionTypeWithUsage[]>
  /** sales/admin. 이름 규칙·대소문자 무시 중복(409)은 서버 문구 그대로. */
  create(name: string): Promise<ActionTypeWithUsage>
  /** admin만(sales 403). 기본 유형도 가능. 중복 규칙 동일. */
  rename(id: number, name: string): Promise<ActionTypeWithUsage>
  /** admin만(sales 403). 사용 중이면 409 "사용 중인 유형은 삭제할 수 없습니다. (Action N건)" */
  remove(id: number): Promise<void>
}

export interface HistoryGateway {
  /** 최신순(at 내림차순, 같은 시각이면 나중에 만든 것이 위). */
  list(dealCode: string, query: HistoryQuery): Promise<HistoryEntry[]>
}

export interface AttachmentsGateway {
  /** 업로드 시각 최신순. 모든 역할 조회 가능. */
  list(dealCode: string): Promise<Attachment[]>
  /**
   * 검증은 `validateUpload`(422, 문구는 fileRules.ts). 저장소 장애 시뮬레이션이 켜져 있으면 503
   * "파일 저장 위치를 사용할 수 없어 업로드할 수 없습니다. 관리자에게 문의하세요." (kind `storage-unavailable`).
   * 같은 파일명이 있을 때: 'ask' → 409(kind `file-exists`, detail "같은 이름의 파일이 이미 있습니다: <이름>"),
   * 'replace' → 교체(`replaced`, History "첨부 파일: 교체 …"), 'skip' → `skipped`(아무 변화 없음).
   */
  upload(dealCode: string, input: UploadInput): Promise<UploadResult>
  /** canDeleteAttachment 아니면 403 "본인이 올린 파일만 삭제할 수 있습니다." History 기록. */
  remove(attachmentId: number): Promise<void>
  download(attachmentId: number): Promise<DownloadedFile>
}

export interface CodesGateway {
  /** 전체 코드(읽기: 모든 역할). order 오름차순. */
  all(): Promise<CodeSet>
  /** 한 종류 + 사용 중 Deal 수(관리 화면용). */
  list(kind: CodeKind): Promise<CodeWithUsage[]>
  /** admin만. key는 자동 생성(영문 소문자/숫자/밑줄, 유일). order는 맨 끝. forecast는 outcome 'open'. 빈 이름 422 "이름을 입력하세요." */
  create(input: CodeCreateInput): Promise<CodeWithUsage>
  /** admin만. locked 포함 가능. 같은 종류 안 중복 이름은 409 "같은 이름의 코드가 이미 있습니다." */
  rename(id: number, name: string): Promise<CodeWithUsage>
  /** admin만. orderedIds는 해당 종류 전체 id를 새 순서로. order는 1부터 다시 매긴다. */
  reorder(kind: CodeKind, orderedIds: number[]): Promise<CodeWithUsage[]>
  /**
   * admin만. locked → 409 "시스템과 연결된 코드는 삭제할 수 없습니다. 이름과 순서는 변경할 수 있습니다."
   * 사용 중 → 409 "사용 중인 코드는 삭제할 수 없습니다. (Deal N건)". (Action이 참조해도 사용 중으로 본다)
   */
  remove(id: number): Promise<void>
}

export interface LabelsGateway {
  /** 전체 Label(구분별 이름순, 기본 Label 먼저). 읽기: 모든 역할. */
  list(): Promise<BantLabelWithUsage[]>
  /**
   * sales/admin. 이름은 trim, 빈 값 422 "Label 이름을 입력하세요.", 50자 초과 422 "Label 이름은 50자 이내로 입력하세요.",
   * 같은 구분 안 중복(대소문자 무시) 409 "같은 구분에 이미 있는 Label 이름입니다."
   */
  create(category: BantCategory, name: string): Promise<BantLabelWithUsage>
  /** admin만(sales 403). 사용 중 Label도 가능. 중복 규칙 동일. */
  rename(id: number, name: string): Promise<BantLabelWithUsage>
  /** admin만(sales 403). 사용 중이면 409 "사용 중인 Label은 삭제할 수 없습니다. (Deal N건)" */
  remove(id: number): Promise<void>
}

export interface ForecastGateway {
  /**
   * Expected Close(revenueDate)의 연/분기로 분류(`inPeriod`). 담당자(퇴사 포함, Deal 있는 사용자만)별
   * 코드 컬럼 셀 + Total(Open 합). Lost는 제외. 합계 행 = rows 합 = 같은 조건의 Deal 원장 합.
   */
  summary(query: ForecastQuery): Promise<ForecastSummary>
  /** 저장된 월말 스냅숏 목록(최근 기준 월 먼저). */
  snapshots(): Promise<ForecastSnapshotInfo[]>
  /** 월말 스냅숏 기준 요약. Vendor 조건은 없다. 기준 월이 없으면 404. */
  snapshotSummary(period: string, query: Omit<ForecastQuery, 'vendorId'>): Promise<ForecastSummary>
}

export interface DashboardGateway {
  /**
   * Dashboard 요약. 기간은 Expected Close 기준. Forecast 타일·Status(Lost 제외)는 기간·담당자·Vendor,
   * 분기(Q1~Q4)는 연도·담당자·Vendor, 주의 필요 Deal은 담당자·Vendor만 적용한다. 모든 로그인 사용자가 조회한다.
   */
  summary(query: DashboardQuery): Promise<DashboardSummary>
}

export interface ReportsGateway {
  /** 로그인한 모든 역할. 리포트 필드 카탈로그(서버가 DB를 읽지 않는다). */
  fields(): Promise<ReportCatalog>
  /**
   * 로그인한 모든 역할. 설계를 실행하고 저장하지 않는다. 정의 위반은 422 kind `invalid-report`(`problem.reportErrors`),
   * 제한 시간 초과는 503 `report-timeout`, 요청 모양 오류는 422 `validation`, 서버에 닿지 못하면 `network`.
   */
  query(input: ReportQueryInput): Promise<ReportResult>
}

export interface VendorsGateway {
  /** 모든 로그인 사용자. Vendor 이름순, 사용 중 Deal 수 포함. */
  list(): Promise<Vendor[]>
  /** admin만. 이름 규칙·대소문자 무시 중복(409)은 서버 문구 그대로. */
  create(name: string): Promise<Vendor>
  rename(id: number, name: string): Promise<Vendor>
  /** admin만. 사용 중이면 409. */
  remove(id: number): Promise<void>
}

export interface UsersGateway {
  /** admin만. 등록일 최신순. */
  list(filter: UserListFilter): Promise<User[]>
  /** 모든 로그인 사용자. 선택 목록용(이름순). 퇴사자는 includeResigned일 때만. */
  options(query: UserOptionsQuery): Promise<UserRef[]>
  /** admin만. 같은 loginId 재직자가 있으면 409 "이미 사용 중인 아이디입니다." (퇴사자와는 겹쳐도 됨). 검증 422. */
  create(input: UserCreateInput): Promise<User>
  /**
   * admin만. 본인은 403 "본인 계정은 삭제할 수 없습니다.". 연결(Deal 담당·Action·History·첨부 등)이 있으면
   * 퇴사 처리(status 'resigned', resignedAt), 없으면 물리 삭제.
   */
  remove(id: number): Promise<UserRemoveResult>
  /** admin만. 본인·마지막 admin·퇴사자·개발 전용 사용자는 409. 같은 역할이면 그대로 돌려준다. */
  changeRole(id: number, role: Role): Promise<User>
}

export interface SettingsGateway {
  /** admin만. 설정이 없으면 null. */
  getDirectory(): Promise<DirectorySettings | null>
  /**
   * revision +1, updatedBy/updatedAt 갱신. 검증 422(서버 URL 1개 이상, 필수 필드).
   * `auth.password`는 현재 관리자 비밀번호(새 설정으로 인증을 확인한다, 개발용 로그인은 null), `expectedRevision`은
   * 화면이 읽은 설정 버전(낙관적 잠금, 어긋나면 409). Fake는 값을 받기만 한다.
   */
  saveDirectory(input: DirectorySettingsInput, auth: DirectorySaveAuth): Promise<DirectorySettings>
  /**
   * 서버 URL 중 'fail'이 들어간 것이 있으면 422(kind `directory-verification-failed`, stage 'connect', detail "연결 단계에서 실패했습니다").
   * `password`는 현재 관리자 비밀번호(개발용 로그인은 null).
   */
  testDirectory(input: DirectorySettingsInput, password: string | null): Promise<void>
  getStorage(): Promise<StorageSettings | null>
  /** 절대 경로 아니면 422 "절대 경로를 입력하세요.", '/readonly'로 시작하면 422 "해당 위치에 쓸 수 없습니다." */
  saveStorage(path: string): Promise<StorageSettings>
  /** 저장 없이 같은 검증만 수행(쓰기 테스트). */
  testStorage(path: string): Promise<void>
}

export interface AlertsGateway {
  /** 로그인한 모든 역할. 저장된 적이 없으면 기본 14, updatedAt/updatedBy null. */
  get(): Promise<AlertSettings>
  /** admin만(403). 1~365 정수가 아니면 422 "미업데이트 기준은 1~365일 사이의 정수로 입력하세요." */
  save(staleDays: number): Promise<AlertSettings>
}

export interface DirectorySaveAuth {
  password: string | null
  expectedRevision: number
}

/** 서버 시각. now는 서버 오프셋 ISO, today는 서버 업무 날짜(YYYY-MM-DD). */
export interface ServerTime {
  now: string
  today: string
}

export interface TimeGateway {
  get(): Promise<ServerTime>
}

export interface Gateway {
  auth: AuthGateway
  setup: SetupGateway
  deals: DealsGateway
  contacts: ContactsGateway
  actions: ActionsGateway
  actionTypes: ActionTypesGateway
  history: HistoryGateway
  attachments: AttachmentsGateway
  codes: CodesGateway
  labels: LabelsGateway
  vendors: VendorsGateway
  forecast: ForecastGateway
  dashboard: DashboardGateway
  reports: ReportsGateway
  users: UsersGateway
  settings: SettingsGateway
  alerts: AlertsGateway
  time: TimeGateway
}

/** 앱의 지금. 화면은 `useToday()`로만 읽는다. */
export interface Clock {
  /** 오프셋 포함 ISO(예: 2026-10-17T09:00:00+09:00). 첫 동기 전에는 브라우저 시각. */
  now(): string
  /**
   * `fetch` 앞뒤 브라우저 시각의 중간을 서버 now에 맞춘다. 성공하면 받은 값을 돌려준다.
   * 실패하거나 서버 now에 오프셋이 없으면 reject하고 직전 상태를 유지한다.
   */
  syncWith(fetch: () => Promise<ServerTime>): Promise<ServerTime>
}
