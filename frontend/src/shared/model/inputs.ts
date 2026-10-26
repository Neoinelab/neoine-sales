/** 게이트웨이 입력(Input)과 목록 질의 타입(A-0 계약). `types.ts`가 전부 재export한다. */

import type { CatalogChoice } from './catalogChoice'
import type { BantCategory } from './constants'
import type {
  CodeKind,
  ContactKind,
  HistoryCategory,
  NextActionStatus,
  NextActionStatusFilter,
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
  contactId: number | null
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
  ownerId: number
  /** Vendor id. 선택 안 함은 null. */
  vendorId: number | null
  /** Solution 자유 텍스트. 필수(서버가 공백·200자 초과를 거절한다). */
  solution: string
  users: number
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

export type DealSortKey =
  | 'name'
  | 'revenueAmount'
  | 'revenueDate'
  | 'lastUpdatedAt'
  | 'statusKey'
  | 'owner'
  | 'customer'
  | 'partner'
  | 'vendor'
  | 'forecastKey'
export type SortOrder = 'asc' | 'desc'

/** Deal 목록의 Forecast 구분 필터 값(서버 `forecast_outcome`. 목록 화면은 쓰지 않는다). */
export type ForecastOutcomeFilter = 'open' | 'won' | 'lost' | 'not_lost'

export interface DealListQuery {
  /** Deal 이름·고객사·파트너사·Deal code 부분 일치(대소문자 무시). */
  keyword?: string
  ownerId?: number
  vendorId?: number
  /** Solution 텍스트 부분 일치(대소문자 무시). */
  solution?: string
  statusKey?: string
  /** 이 중 하나와 일치(OR). 비면 보내지 않는다. */
  forecastKeys?: readonly string[]
  /** Forecast 코드의 구분(outcome) 기준. `not_lost` = Open + Won. forecastKeys와 함께 쓰면 둘 다 만족해야 한다(AND). */
  forecastOutcome?: ForecastOutcomeFilter
  /** Expected Close(revenueDate) 기준 연도/분기. quarter만 있으면 서버가 올해로 본다. */
  year?: number
  quarter?: 1 | 2 | 3 | 4
  /** Expected Close의 월(1~12). quarter와 함께 쓸 수 없다(서버 422). month만 있으면 서버가 올해로 본다. */
  month?: number
  /** 최종 업데이트 기간(양끝 포함, 'YYYY-MM-DD'). 한쪽만 있어도 된다. */
  updatedFrom?: string
  updatedTo?: string
  /** true면 기한초과(overdue) Deal만. stale과 함께면 둘 중 하나(OR). */
  overdue?: boolean
  /** true면 미업데이트(stale) Deal만. */
  stale?: boolean
  /** true면 현재 로그인 사용자가 Owner인 Deal만. */
  mine?: boolean
  /** Next Action이 있는 가장 최근 Action의 상태. */
  nextActionStatus?: NextActionStatusFilter
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
 * Action 등록 입력. progress·nextAction은 각각 선택(빈 문자열)이며 둘 다 비면 422. dueDate는 nextAction이 있을 때만 필수(없으면 빈 문자열),
 * memo는 빈 문자열 가능, dueDate는 과거 허용.
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
  /** 있으면 저장 때 그 이전 Next Action(Action id)을 종료(수행)로 바꾼다. 지금 기준 행이 아니면 409. */
  closePreviousNextActionId?: number
}

/** Action 수정 입력. 등록 시점 Status/Forecast와 수행일시·담당자는 바꿀 수 없다. */
export type ActionUpdateInput = Omit<ActionInput, 'statusChanges' | 'closePreviousNextActionId'>

/** Next Action 상태 변경. memo는 종료할 때만(Open으로 되돌릴 때는 빈 문자열). */
export interface NextActionStatusInput {
  status: NextActionStatus
  memo: string
}

export type ActionSortKey = 'actedAt' | 'actor' | 'type' | 'dueDate' | 'nextActionStatus'

export interface ActionQuery {
  typeId?: number
  actorId?: number
  /** 진행사항·Next Action·Memo 부분 일치. */
  keyword?: string
  actedFrom?: string
  actedTo?: string
  dueFrom?: string
  dueTo?: string
  nextActionStatus?: NextActionStatusFilter
  /** sort와 order가 모두 있을 때만 정렬을 요청한다(없으면 서버 기본: 수행일시 최신순). */
  sort?: ActionSortKey
  order?: SortOrder
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
  /** 월(1~12). quarter와 함께 쓸 수 없다. */
  month?: number
  vendorId?: number
  ownerId?: number
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
  /** Forecast 코드 order(서버 값). */
  order: number
}

export interface ForecastSummaryRow {
  /** 합계 행이면 null. */
  ownerId: number | null
  ownerName: string
  /** forecastKey → 셀. columns의 모든 key가 존재한다(없으면 {0,0}). */
  cells: Record<string, ForecastCell>
  /** Open(outcome 'open') 합. Won·Lost 제외. */
  total: ForecastCell
}

/** 저장된 월말 스냅숏 한 건의 머리 정보. */
export interface ForecastSnapshotInfo {
  /** 기준 월 'YYYY-MM'. */
  period: string
  /** 생성 시각(오프셋 포함 ISO). */
  takenAt: string
}

/**
 * Forecast 요약. 분류 기준은 Expected Close(revenueDate)의 연/분기/월. Lost는 columns·total에서 제외.
 * rows는 Deal이 있는 담당자(퇴사 포함)만, totalRow는 rows의 합이며 Deal 목록 원장 합과 같아야 한다.
 */
export interface ForecastSummary {
  /** live: 지금 기준 실시간 집계, snapshot: 월말 스냅숏(R2). */
  basis: 'live' | 'snapshot'
  /** 서버가 집계한 시각(ISO 8601). */
  asOf: string
  /** basis가 snapshot일 때 기준 월('YYYY-MM'), 실시간은 null. */
  snapshotPeriod: string | null
  query: ForecastQuery
  /** Forecast 코드 order 순, Lost 제외. */
  columns: ForecastColumn[]
  rows: ForecastSummaryRow[]
  totalRow: ForecastSummaryRow
}

// ───────────────────────── Dashboard ─────────────────────────

/** Dashboard 요약 조회 조건. 기간 기준은 Expected Close. year는 필수, 나머지는 없으면 전체. */
export interface DashboardQuery {
  year: number
  quarter?: 1 | 2 | 3 | 4
  ownerId?: number
  vendorId?: number
}

/** 분기 하나의 Forecast 구분별 셀(Lost 제외). `total` = Open 합 + Won. */
export interface DashboardQuarter {
  quarter: 1 | 2 | 3 | 4
  from: string
  to: string
  /** forecastKey → 셀. `DashboardSummary.forecast.columns`의 모든 key가 존재한다. */
  cells: Record<string, ForecastCell>
  openTotal: ForecastCell
  total: ForecastCell
}

export interface DashboardStatusItem extends ForecastCell {
  key: string
  name: string
  order: number
}

/**
 * Dashboard 요약(서버 계산값을 그대로 쓴다). 타일·막대·표가 모두 이 한 응답에서 나온다.
 * `attention`은 담당자·Vendor만 적용하고 기간(year·quarter)은 적용하지 않는다.
 */
export interface DashboardSummary {
  asOf: string
  /** 서버 업무 날짜('YYYY-MM-DD'). */
  today: string
  period: { year: number; quarter: number | null; from: string; to: string }
  forecast: {
    /** Forecast 코드 order 순, Lost 제외. */
    columns: ForecastColumn[]
    cells: Record<string, ForecastCell>
    openTotal: ForecastCell
  }
  /** Lost Deal 제외, Status 코드 order 순. */
  statuses: { items: DashboardStatusItem[]; total: ForecastCell }
  /** 항상 Q1~Q4. */
  quarters: DashboardQuarter[]
  attention: {
    staleDays: number
    overdue: number
    stale: number
    closingThisMonth: { year: number; month: number; count: number }
    closingThisQuarter: { year: number; quarter: number; count: number }
  }
}
