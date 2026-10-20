/** 게이트웨이 입력(Input)과 목록 질의 타입(A-0 계약). `types.ts`가 전부 재export한다. */

import type { CatalogChoice } from './catalogChoice'
import type { BantCategory } from './constants'
import type {
  CodeKind,
  ContactKind,
  HistoryCategory,
  Poc,
  Quote,
  Role,
  UserStatus,
} from './types'
import type { SyncChange, SyncResolution } from './sync'

// ───────────────────────── 연락처 ─────────────────────────

/**
 * 연락처 입력. 공백 규칙: company/name/email/phone에는 공백 문자가 하나도 있을 수 없다(입력 차단 +
 * 게이트웨이 422 "공백은 입력할 수 없습니다."). title은 앞뒤 공백만 제거하고 내부 공백은 허용한다.
 * company/name은 필수(빈 문자열 불가). email/phone은 없으면 null(빈 문자열 금지).
 */
export interface ContactInput {
  company: string
  name: string
  title: string
  email: string | null
  phone: string | null
}

/**
 * Deal 화면의 연락처 선택 결과.
 * - contactId가 있으면 그 연락처를 fields로 **갱신**한다(변경 없으면 no-op). 갱신 결과가 다른 연락처와
 *   같은 사람이 되면 409.
 * - contactId가 null이면 `findSamePerson` 규칙으로 같은 사람을 찾아 갱신하고, 없으면 새로 만든다.
 */
export interface ContactDraft extends ContactInput {
  contactId: string | null
}

export interface ContactListQuery {
  kind?: ContactKind
  /** 회사명·담당자명·이메일 부분 일치(대소문자 무시). */
  keyword?: string
  offset?: number
  limit?: number
}

// ───────────────────────── Deal ─────────────────────────

/**
 * Deal 등록 입력. 불변식: `statusKey === 'contract_completed'` ⇔ `forecastKey === 'won'`
 * (어긋나면 422 "Status와 Forecast의 동기화가 맞지 않습니다."). 매출금액은 1 이상의 정수, 매출일 필수.
 * customer 필수, partner는 선택(null=파트너 없음). owner는 재직 sales여야 한다.
 */
export interface DealInput {
  name: string
  ownerId: string
  /** Vendor/Solution id. 선택 안 함은 null. */
  vendorId: string | null
  solutionId: string | null
  users: number | null
  statusKey: string
  forecastKey: string
  revenueAmount: number
  revenueDate: string
  customer: ContactDraft
  partner: ContactDraft | null
  quote: Quote
  poc: Poc
  procurement: string
  /** 구분별 선택: 있는 Label은 `{id}`, 목록에 없는 이름은 `{name}`(서버가 저장 때 만든다), 선택 안 함은 null. */
  bant: Record<BantCategory, CatalogChoice | null>
}

/** Deal 수정 입력. 보낸 필드만 바꾼다(미포함=유지). `partner: null`은 활성 파트너 제거. 불변식은 DealInput과 같다. */
export type DealPatch = Partial<DealInput>

/** 단일 필드 변경(목록 Inline Update·상세 현재값 바). 4개 필드만 허용한다. */
export type DealChange =
  | SyncChange
  | { field: 'revenueAmount'; value: number }
  | { field: 'revenueDate'; value: string }

export interface ApplyChangeRequest {
  change: DealChange
  /** needRevenue/askStatus/askForecast에 필요한 사용자 답. 필요 없는데 보내면 무시. */
  resolution?: SyncResolution
}

export type DealSortKey = 'name' | 'revenueAmount' | 'revenueDate' | 'lastUpdatedAt' | 'statusKey'
export type SortOrder = 'asc' | 'desc'

export interface DealListQuery {
  /** Deal 이름·고객사·파트너사·Deal code 부분 일치(대소문자 무시). */
  keyword?: string
  ownerId?: string
  vendorId?: string
  solutionId?: string
  statusKey?: string
  forecastKey?: string
  /** Expected Close(revenueDate) 기준 연도/분기. quarter만 있으면 서버가 올해로 본다. */
  year?: number
  quarter?: 1 | 2 | 3 | 4
  /** Expected Close 기간(포함). year/quarter와 함께 오면 교집합. */
  revenueFrom?: string
  revenueTo?: string
  /** 구분별 Label(AND). */
  bantLabelIds?: Partial<Record<BantCategory, string>>
  /** true면 현재 로그인 사용자가 Owner인 Deal만. */
  mine?: boolean
  sort?: DealSortKey
  order?: SortOrder
  offset?: number
  /** 기본 20(`DEAL_PAGE_SIZE`). */
  limit?: number
}

// ───────────────────────── Action / History / 첨부 ─────────────────────────

/** Status·Forecast 변경을 함께 요청하는 Action 등록의 항목 하나. Deal에 `applyChange`와 같은 규칙으로 적용된다. */
export interface StatusChangeRequest {
  change: SyncChange
  resolution?: SyncResolution
}

/**
 * Action 등록 입력. progress/nextAction/dueDate 필수(422), memo는 빈 문자열 가능, dueDate는 과거 허용.
 * 수행일시·담당자는 서버(게이트웨이)가 현재 시각·로그인 사용자로 채운다.
 */
export interface ActionInput {
  /** 있는 유형은 `{id}`, 목록에 없는 이름은 `{name}`(서버가 저장 때 만든다). */
  type: CatalogChoice
  progress: string
  nextAction: string
  dueDate: string
  memo: string
  /** 사용자가 바꾼 순서대로 최대 2개(Status·Forecast 각 1개). 없으면 보내지 않는다. */
  statusChanges?: StatusChangeRequest[]
}

/** Action 수정 입력. 등록 시점 Status/Forecast와 수행일시·담당자는 바꿀 수 없다. */
export type ActionUpdateInput = Omit<ActionInput, 'statusChanges'>

export type ActionSort = 'actedDesc' | 'actedAsc' | 'dueAsc'

export interface ActionQuery {
  typeId?: string
  actorId?: string
  /** 진행사항·Next Action·Memo 부분 일치. */
  keyword?: string
  actedFrom?: string
  actedTo?: string
  dueFrom?: string
  dueTo?: string
  /** 기본 'actedDesc'. */
  sort?: ActionSort
}

export interface HistoryQuery {
  category?: HistoryCategory
}

/** 이미 같은 파일명이 있을 때 동작. 'ask'면 409(`file-exists`)로 거절해 화면이 사용자에게 묻게 한다. */
export type OnExists = 'ask' | 'replace' | 'skip'

export interface UploadInput {
  file: File
  description: string
  onExists: OnExists
}

// ───────────────────────── 코드 / Label ─────────────────────────

export interface CodeCreateInput {
  kind: CodeKind
  name: string
  /** forecast 전용 참고 문자열. */
  probabilityHint?: string | null
}

// ───────────────────────── 사용자 / 설정 ─────────────────────────

export interface UserCreateInput {
  loginId: string
  name: string
  role: Role
}

export type UserListFilter = UserStatus | 'all'

export interface UserOptionsQuery {
  /** 'sales'면 Owner 후보용(재직 sales만). 지정하지 않으면 재직자 전체. */
  role?: Role
  /** true면 퇴사자도 포함(필터용). 기본 false. */
  includeResigned?: boolean
}

/** 삭제 결과: 연결(Deal 담당·Action·History 등)이 있으면 퇴사 처리, 없으면 물리 삭제. */
export interface UserRemoveResult {
  outcome: 'resigned' | 'deleted'
}

export interface DirectorySettingsInput {
  serverUrls: string[]
  useStarttls: boolean
  caCertPem: string | null
  bindTemplate: string
  baseDn: string
  userFilter: string
  displayNameAttribute: string
  emailAttribute: string
  connectTimeoutSeconds: number
  receiveTimeoutSeconds: number
}

// ───────────────────────── Forecast ─────────────────────────

export interface ForecastQuery {
  year: number
  quarter?: 1 | 2 | 3 | 4
  vendorId?: string
  ownerId?: string
}

export interface ForecastCell {
  count: number
  /** KRW 정수 합계. */
  amount: number
}

export interface ForecastColumn {
  key: string
  name: string
  outcome: 'open' | 'won'
}

export interface ForecastSummaryRow {
  /** 합계 행이면 null. */
  ownerId: string | null
  ownerName: string
  /** forecastKey → 셀. columns의 모든 key가 존재한다(없으면 {0,0}). */
  cells: Record<string, ForecastCell>
  /** Open(outcome 'open') 합. Won·Lost 제외. */
  total: ForecastCell
}

/**
 * Forecast 요약. 분류 기준은 Expected Close(revenueDate)의 연/분기. Lost는 columns·total에서 제외.
 * rows는 Deal이 있는 담당자(퇴사 포함)만, totalRow는 rows의 합이며 Deal 목록 원장 합과 같아야 한다.
 */
export interface ForecastSummary {
  query: ForecastQuery
  /** Forecast 코드 order 순, Lost 제외. */
  columns: ForecastColumn[]
  rows: ForecastSummaryRow[]
  totalRow: ForecastSummaryRow
}
