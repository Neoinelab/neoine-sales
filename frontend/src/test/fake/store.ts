/** 메모리 저장소. 시드의 사본을 들고 있고, 변경은 게이트웨이가 한다. 반환 시에는 뷰 변환으로 복사본을 만든다. */

import type { ReportQueryInput, ReportResult, SavedReport } from '../../shared/model/reportTypes'
import type {
  BantCategory,
  ContractStatus,
  InspectionCycle,
  LicenseTerm,
  Code,
  Contact,
  Deal,
  DirectorySettings,
  ForecastOutcome,
  HistoryCategory,
  NextActionStatus,
  Role,
  SetupState,
  UserStatus,
} from '../../shared/model/types'

export interface UserRecord {
  id: number
  loginId: string
  name: string
  role: Role
  status: UserStatus
  email: string | null
  phone: string | null
  createdAt: string
  lastLoginAt: string | null
  resignedAt: string | null
}

export interface ActionRecord {
  id: number
  dealCode: string
  actedOn: string
  actorId: number
  /** Action 유형(`ActionTypeRecord.id`). 이름은 읽을 때 조인한다. */
  typeId: number
  /** 진행사항·Next Action은 각각 비울 수 있다(둘 다 비면 안 된다). Due Date는 Next Action이 있을 때만 있다. */
  progress: string | null
  nextAction: string | null
  dueDate: string | null
  /** Next Action이 있는 행에만 값이 있다(없으면 null). */
  nextActionStatus: NextActionStatus | null
  /** 종료 상태일 때만 서버 시계의 종료일(업무 날짜, YYYY-MM-DD). */
  nextActionClosedOn: string | null
  statusKey: string
  forecastKey: string
}

/** Deal Comment(`actionId` null) 또는 Action Comment. 읽음은 Deal Owner가 읽었는지를 나타내는 속성(`readAt`)이다. 수정은 없다. */
export interface CommentRecord {
  id: number
  dealCode: string
  /** 연결된 Action(같은 Deal 소속). Deal Comment면 null. */
  actionId: number | null
  authorId: number
  body: string
  createdAt: string
  /** Owner가 읽은 시각. null이면 읽지 않음. */
  readAt: string | null
}

export interface HistoryRecord {
  id: number
  /** 같은 시각 정렬용 일련번호(클수록 나중). */
  seq: number
  dealCode: string
  at: string
  byId: number
  category: HistoryCategory
  target: string
  before: string
  after: string
}

export interface AttachmentRecord {
  id: number
  dealCode: string
  fileName: string
  size: number
  mime: string
  description: string
  uploadedById: number
  uploadedAt: string
  /** 업로드한 파일 또는 시드의 더미 텍스트. */
  content: Blob | string
}

/** Action 유형 카탈로그 항목. 기본 유형은 시드 순서를 유지하고 이름은 대소문자 무시로 고유하다. */
export interface ActionTypeRecord {
  id: number
  name: string
  isDefault: boolean
  createdById: number | null
  createdAt: string
  updatedAt: string
}

export interface LabelRecord {
  id: number
  category: BantCategory
  name: string
  isDefault: boolean
  createdById: number | null
  createdAt: string
}

/** Vendor(Aggregate Root). 이름은 대소문자 무시로 고유. */
export interface VendorRecord {
  id: number
  name: string
  createdAt: string
  updatedAt: string
}

/** 파트너 Activity 미팅 기록. 회사는 저장 당시 대표 표기 텍스트이고 Deal과 연결되지 않는다. */
export interface PartnerMeetingRecord {
  id: number
  partnerCompany: string
  meetingDate: string
  content: string
  authorId: number
  createdAt: string
  updatedAt: string
}

/**
 * 라이선스 계약. Deal에서 오는 5칸은 저장하지 않고 조회 때 Deal에서 읽는다. 다만 시드의 과거 계약은 시드 Deal 24건 밖의 Deal에 속하므로
 * 그런 계약만 `dealSide`로 그 Deal의 값을 직접 들고 있다(Deal이 있는 계약은 항상 Deal 값을 읽는다).
 */
export interface LicenseContractRecord {
  id: number
  dealCode: string
  status: ContractStatus
  licenseStart: string | null
  licenseEnd: string | null
  term: LicenseTerm | null
  techOwner: string
  inspection: InspectionCycle
  note: string
  renewedFromId: number | null
  endedOn: string | null
  createdById: number
  updatedById: number
  createdAt: string
  updatedAt: string
  dealSide?: ContractDealSide
}

/** Deal이 없는 시드 계약이 들고 있는 Deal 값. */
export interface ContractDealSide {
  dealName: string
  customer: string
  vendorId: number | null
  product: string
  partner: string | null
  ownerId: number
}

export interface ContractAttachmentRecord {
  id: number
  contractId: number
  fileName: string
  size: number
  mime: string
  description: string
  uploadedById: number
  uploadedAt: string
  content: Blob | string
}

export type DirectoryRecord = Omit<DirectorySettings, 'updatedBy'> & { updatedById: number | null }

export interface StorageRecord {
  path: string
  updatedAt: string
  updatedById: number | null
}

/** 경고 기준(미업데이트 일수). 저장된 적이 없으면 updatedAt/updatedById가 null. */
export interface AlertRecord {
  staleDays: number
  updatedAt: string | null
  updatedById: number | null
}

/** Forecast 월말 스냅숏의 셀 하나. 코드 이름·outcome·order는 셀이 아니라 스냅숏의 열에 있다. */
export interface ForecastSnapshotCellRecord {
  revenueYear: number
  revenueMonth: number
  ownerId: number
  forecastKey: string
  count: number
  amount: number
}

/** Forecast 월말 스냅숏의 열 하나: 스냅숏을 만든 시점의 Forecast 코드(Deal이 없던 코드도 저장된다). */
export interface ForecastSnapshotColumnRecord {
  key: string
  name: string
  outcome: ForecastOutcome
  order: number
}

/** Forecast 월말 스냅숏(기준 월 `YYYY-MM`당 하나). 생성 이후 Deal·코드가 바뀌어도 변하지 않는다. */
export interface ForecastSnapshotRecord {
  period: string
  takenAt: string
  /** 저장 당시의 Forecast 코드 목록(Lost 포함). 요약의 열은 여기서 만든다. */
  columns: ForecastSnapshotColumnRecord[]
  cells: ForecastSnapshotCellRecord[]
}

/** 시드가 만들어 주는 전체 데이터. */
export interface SeedData {
  users: UserRecord[]
  codes: Code[]
  labels: LabelRecord[]
  actionTypes: ActionTypeRecord[]
  vendors: VendorRecord[]
  contacts: Contact[]
  deals: Deal[]
  actions: ActionRecord[]
  /** Deal·Action Comment(비어 있어도 된다). 샘플 시드는 비어 있고 테스트가 게이트웨이로 만든다. */
  comments: CommentRecord[]
  history: HistoryRecord[]
  attachments: AttachmentRecord[]
  /** 라이선스 계약(없으면 비어 있는 것과 같다). 샘플 시드(`test/fixtures`)가 채우고, Won 진입 때 Fake가 만든다. */
  licenseContracts: LicenseContractRecord[]
  contractAttachments: ContractAttachmentRecord[]
  directory: DirectoryRecord | null
  storage: StorageRecord | null
  alerts: AlertRecord
  /** 월말 스냅숏(없으면 비어 있는 것과 같다). 샘플 시드(`test/fixtures`)만 채운다. */
  forecastSnapshots?: ForecastSnapshotRecord[]
  /** 파트너 Activity 미팅 기록(없으면 비어 있는 것과 같다). 샘플 시드(`test/fixtures`)만 채운다. */
  partnerMeetings?: PartnerMeetingRecord[]
  setup: SetupState
  /** local 모드 비밀번호(사용자 id별). 없는 사용자는 `SEED_PASSWORD`다. 화면·게이트웨이 응답에는 나가지 않는다. */
  passwords?: Record<number, string>
  /** 접두사별 마지막 순번. `takeId`가 올린다. */
  counters: Record<string, number>
}

/** 테스트가 지정하는 리포트 조회 응답. 결과를 돌려주거나 throw(ApiError)하면 reject된다. */
export type ReportQueryHandler = (input: ReportQueryInput) => ReportResult | Promise<ReportResult>

/** Fake가 받은 저장 리포트 요청 기록 한 건(쓰기와 실행만 남기고, 목록·상세 조회는 남기지 않는다). */
export interface SavedReportRequest {
  op: 'create' | 'update' | 'copy' | 'remove' | 'run' | 'layout'
  /** create는 null, 나머지는 대상 리포트 id. */
  id: number | null
  /** create·update는 보낸 입력(update는 revision 포함), layout은 `{ layout, revision }`, copy는 메타, remove·run은 undefined. */
  body?: unknown
}

/** 리포트 Fake 제어 상태: 지정 응답, 받은 조회 요청 기록, 저장 리포트 저장소와 요청 기록. 시드 복원(`resetData`)이 비운다. */
export interface ReportsControlState {
  handler: ReportQueryHandler | null
  queries: ReportQueryInput[]
  /** 저장된 리포트(기본은 비어 있다). 만든 사람·수정자는 id로 들고 화면에는 사용자 목록에서 풀어 준다. */
  saved: SavedReport[]
  /** 다음에 발급할 리포트 id. */
  nextSavedId: number
  requests: SavedReportRequest[]
  /**
   * 배치 저장(`saveReportLayout`) 요청이 들어올 때마다 서버 처리 전에 불리는 관문. 테스트가 응답을 늦추거나(Promise를 나중에 끝냄)
   * 실패시키려고(throw) 건다. 요청 번호는 1부터. `resetData`가 지운다.
   */
  layoutGate: LayoutSaveGate | null
}

export type LayoutSaveGate = (call: { id: number; attempt: number; body: { layout: unknown; revision: number } }) => void | Promise<void>

export function emptyReportsState(): ReportsControlState {
  return { handler: null, queries: [], saved: [], nextSavedId: 1, requests: [], layoutGate: null }
}

export interface MockStore {
  data: SeedData
  session: { userId: number | null }
  storageFailure: boolean
  reports: ReportsControlState
}

/** 종류(접두사)별 순번 id를 만든다. 서버의 BIGINT 시퀀스처럼 1부터 1씩 커지는 정수다. */
export function takeId(counters: Record<string, number>, prefix: string): number {
  const next = (counters[prefix] ?? 0) + 1
  counters[prefix] = next
  return next
}

/** History 일련번호. */
export function nextSeq(counters: Record<string, number>): number {
  const next = (counters.seq ?? 0) + 1
  counters.seq = next
  return next
}

export function createStore(seed: SeedData, userId: number | null): MockStore {
  return { data: seed, session: { userId }, storageFailure: false, reports: emptyReportsState() }
}
