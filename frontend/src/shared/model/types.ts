/**
 * 도메인 모델(화면·게이트웨이 계약). 계획 4.2장 기준.
 *
 * 공통 약속
 * - 금액은 KRW 정수(number). 소수·통화 필드는 없다(통화는 KRW 고정 표시).
 * - 날짜는 'YYYY-MM-DD'(달력 날짜), 시각은 오프셋 포함 ISO 8601 문자열('2026-10-15T09:00:00+09:00').
 * - id는 서버가 발급하는 양의 정수(number, 1~2^53-1), Deal은 id 대신 `code`(`DEAL_CODE_PATTERN`)가 기본키다.
 * - Status/Forecast는 **내부 key**(문자열)로 참조한다. 이름(`Code.name`)은 admin이 바꿀 수 있으므로
 *   로직은 항상 key로 판단하고, 화면 표시만 이름을 쓴다.
 * - 게이트웨이가 돌려주는 객체는 이 파일의 타입 그대로이며, 사용자는 `UserRef`로 풀어서(이름·역할·재직 여부) 준다.
 */

import type { BantCategory } from './constants'

export type { BantCategory } from './constants'
export type * from './inputs'
export type * from './settings'

// ───────────────────────── 사용자 ─────────────────────────

/** 최종 업데이트 기간 프리셋 키(서버가 정한다). */
export type UpdatedPeriodKey = '2w' | '1m' | '2m' | '3m' | '6m'
/** 향후 기간 프리셋 키(서버가 정한다). */
export type UpcomingPeriodKey = '1m' | '2m'
export interface UpdatedPeriods {
  /** 서버 업무 날짜('YYYY-MM-DD'). */
  today: string
  /** 프리셋별 양끝 포함 날짜 범위. */
  periods: { key: UpdatedPeriodKey; from: string; to: string }[]
  /** 향후 프리셋: 오늘부터 N개월 뒤까지(양끝 포함). */
  upcoming: { key: UpcomingPeriodKey; from: string; to: string }[]
}

export type Role = 'admin' | 'sales' | 'user'
export type UserStatus = 'active' | 'resigned'

/** 화면 표시용 사용자 참조. 표시명은 `userLabel`을 쓴다(퇴사자는 `이름(퇴사)`). */
export interface UserRef {
  id: number
  name: string
  role: Role
  status: UserStatus
}

/** 로그인한 사용자. */
export interface Me {
  id: number
  loginId: string
  name: string
  role: Role
}

export interface User extends UserRef {
  loginId: string
  email: string | null
  createdAt: string
  /** 등록자(시드 최초 사용자는 null). */
  createdBy: UserRef | null
  lastLoginAt: string | null
  resignedAt: string | null
  resignReason: string | null
}

// ───────────────────────── 코드 / Label ─────────────────────────

export type CodeKind = 'status' | 'forecast'
export type ForecastOutcome = 'open' | 'won' | 'lost'

/**
 * Status/Forecast 코드. key는 불변(내부 고유 코드), name·order는 admin이 변경한다.
 * locked=true(`LOCKED_KEYS` 5개: Status `prospecting`·`contract_completed`, Forecast `pipeline`·`won`·`lost`)는 삭제 불가(이름·순서 변경은 가능).
 * outcome/probabilityHint는 forecast에서만 의미가 있다(status는 outcome='open', probabilityHint=null 고정).
 * probabilityHint는 "0–50" 같은 참고 문자열이며 저장·집계에 쓰지 않는다.
 */
export interface Code {
  id: number
  kind: CodeKind
  key: string
  name: string
  order: number
  locked: boolean
  outcome: ForecastOutcome
  probabilityHint: string | null
}

/** 관리 화면용: 코드 + 사용 중인 Deal 수. */
export interface CodeWithUsage extends Code {
  usageCount: number
}

/** Status/Forecast 코드 전체(order 오름차순). 배지·select·동기화 규칙의 입력. */
export interface CodeSet {
  statuses: readonly Code[]
  forecasts: readonly Code[]
}

export interface BantLabel {
  id: number
  category: BantCategory
  name: string
  isDefault: boolean
  createdBy: UserRef | null
  createdAt: string
}

export interface BantLabelWithUsage extends BantLabel {
  usageCount: number
}

/** Action 유형(관리 화면용). 기본 유형은 isDefault, createdBy는 기본 유형이면 null. */
export interface ActionTypeWithUsage {
  id: number
  name: string
  isDefault: boolean
  createdBy: UserRef | null
  usageCount: number
  createdAt: string
  updatedAt: string
}

// ───────────────────────── 연락처 ─────────────────────────

export type ContactKind = 'customer' | 'partner'

export interface Contact {
  id: number
  kind: ContactKind
  company: string
  name: string
  title: string
  email: string | null
  phone: string | null
  createdAt: string
  updatedAt: string
}

/** 연결된 Deal 수를 포함한 연락처(공유 안내·contacts 관리용). */
export interface ContactRow extends Contact {
  dealCount: number
}

export interface PartnerLink {
  contactId: number
  /** Deal당 active=true는 최대 1건. 교체되면 이전 링크는 active=false. */
  active: boolean
  linkedAt: string
  unlinkedAt: string | null
}

/** 상세 화면의 파트너 교체 이력용(연락처를 풀어 둔 링크). */
export interface PartnerLinkView extends Omit<PartnerLink, 'contactId'> {
  contact: Contact
}

// ───────────────────────── Deal ─────────────────────────

/** id와 표시 이름만 가진 참조(Vendor·Solution). */
export interface NamedRef {
  id: number
  name: string
}

/** 관리 화면의 Solution. */
export interface Solution {
  id: number
  vendorId: number
  name: string
  /** 이 Solution을 쓰는 Deal 수. */
  usageCount: number
}

/** 관리 화면의 Vendor와 소속 Solution(서버 정렬 그대로). */
export interface Vendor {
  id: number
  name: string
  usageCount: number
  solutions: Solution[]
}

export type QuoteSubmitted = 'YES' | 'NO'
export type PocState = 'YES' | 'ING' | 'NO'

export interface Quote {
  submitted: QuoteSubmitted | null
  submittedDate: string | null
}

export interface Poc {
  state: PocState | null
  completedDate: string | null
}

export type BantSelection = Record<BantCategory, number | null>

export interface Deal {
  /** `YYYYMMDD-XXXX`. 등록 시 자동 채번, 변경 불가. */
  code: string
  name: string
  ownerId: number
  /** Vendor/Solution 참조(id). 선택 안 함이면 null. 화면용 이름은 `DealRow.vendor`/`solution`. */
  vendorId: number | null
  solutionId: number | null
  /** 견적 단위 사용자 수(Users). 필수, 0 이상. */
  users: number
  statusKey: string
  forecastKey: string
  /** 매출금액(KRW 정수 ≥ 1). Won이면 실제 값. */
  revenueAmount: number
  /** 매출일 = Expected Close. Won이면 실제 매출일. */
  revenueDate: string
  customerContactId: number
  partnerLinks: PartnerLink[]
  quote: Quote
  poc: Poc
  procurement: string
  bant: BantSelection
  /** 현재 Status에 진입한 시각(등록 시 또는 Status key가 바뀐 시각). */
  statusChangedAt: string
  createdAt: string
  updatedAt: string
}

/** Next Action 상태: Open / 종료(수행) / 종료(미수행). */
export type NextActionStatus = 'open' | 'done' | 'notDone'

/** 상태 필터. `closed`는 종료(수행)·종료(미수행) 둘 다. */
export type NextActionStatusFilter = NextActionStatus | 'closed'

/** Next Action이 있는 가장 최근 Action(수행시각 기준)의 Next Action 요약. */
export interface NextActionSummary {
  text: string
  dueDate: string
  status: NextActionStatus
}

/** 기한초과(due < 오늘) / 미업데이트(마지막 갱신 14일 이상) / 둘 다 / 없음. 종결(Won·Lost) Deal은 항상 null. */
export type Risk = 'overdue' | 'stale' | 'overdue_stale' | null

/** 목록 행. Deal + 화면용 파생값. */
export interface DealRow extends Omit<Deal, 'vendorId' | 'solutionId'> {
  owner: UserRef
  /** 서버가 풀어 준 Vendor/Solution(id+이름). 없으면 null. */
  vendor: NamedRef | null
  solution: NamedRef | null
  customer: Contact
  /** 활성 파트너 연락처(없으면 null). */
  activePartner: Contact | null
  nextAction: NextActionSummary | null
  /** 모든 Action 중 가장 최근 수행시각. Action이 없으면 Deal 등록 시각(Deal 수정은 반영하지 않는다). */
  lastUpdatedAt: string
  /** 현재 Status 체류 일수(달력 날짜 차, 당일 0). */
  statusDays: number
  risk: Risk
}

export interface DealDetail extends DealRow {
  /** 활성·비활성 파트너 링크 전체(최신 연결 순). 화면 기본은 활성만 보여준다. */
  partnerHistory: PartnerLinkView[]
}

/** Deal 삭제 확인 팝업에 보여줄 연쇄 삭제 대상 건수. */
export interface DealDeletionImpact {
  historyCount: number
  actionCount: number
  attachmentCount: number
}

// ───────────────────────── Action / History / 첨부 ─────────────────────────

/**
 * 불변식: statusKey/forecastKey는 **등록 시점**의 값을 저장한다(이후 Deal이 바뀌어도 그대로).
 * Action 수정은 이 두 값을 바꾸지 않는다.
 */
export interface DealAction {
  id: number
  dealCode: string
  actedAt: string
  actor: UserRef
  /** 현재 유형 이름(이름이 바뀌면 다음 조회부터 새 이름). */
  type: string
  typeId: number
  /** 진행사항·Next Action은 각각 선택(둘 중 하나는 있다). Due Date는 Next Action이 있을 때만 있다. */
  progress: string | null
  nextAction: string | null
  dueDate: string | null
  /** Next Action이 있는 행만 상태가 있다. */
  nextActionStatus: NextActionStatus | null
  nextActionClosedAt: string | null
  memo: string
  statusKey: string
  forecastKey: string
}

export type HistoryCategory =
  | 'created'
  | 'status'
  | 'forecast'
  | 'amount'
  | 'expectedClose'
  | 'owner'
  | 'partner'
  | 'contact'
  | 'bant'
  | 'action'
  | 'attachment'
  | 'other'

/** Deal 및 연결 정보의 모든 변경 1건. before/after는 표시용 text. 등록은 before='' after='Deal 등록'. */
export interface HistoryEntry {
  id: number
  dealCode: string
  at: string
  by: UserRef
  category: HistoryCategory
  /** 변경 대상 표시 문구(예: 'Status', '파트너', '첨부 파일'). */
  target: string
  before: string
  after: string
}

export interface Attachment {
  id: number
  dealCode: string
  fileName: string
  size: number
  mime: string
  /** 100자 이내. */
  description: string
  uploadedBy: UserRef
  uploadedAt: string
}

/** 다운로드 결과. */
export interface DownloadedFile {
  fileName: string
  blob: Blob
}

// ───────────────────────── 목록 공통 ─────────────────────────

export interface Page<T> {
  items: T[]
  /** 필터 적용 후 전체 건수. */
  total: number
  offset: number
  limit: number
}

/** 경고 기준(미업데이트 일수) 설정. 저장된 적이 없으면 updatedAt/updatedBy가 null. */
export interface AlertSettings {
  staleDays: number
  updatedAt: string | null
  updatedBy: UserRef | null
}
