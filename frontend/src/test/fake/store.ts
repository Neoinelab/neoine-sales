/** 메모리 저장소. 시드의 사본을 들고 있고, 변경은 게이트웨이가 한다. 반환 시에는 뷰 변환으로 복사본을 만든다. */

import type {
  BantCategory,
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
  createdAt: string
  createdById: number | null
  lastLoginAt: string | null
  resignedAt: string | null
  resignReason: string | null
}

export interface ActionRecord {
  id: number
  dealCode: string
  actedAt: string
  actorId: number
  /** Action 유형(`ActionTypeRecord.id`). 이름은 읽을 때 조인한다. */
  typeId: number
  /** 진행사항·Next Action은 각각 비울 수 있다(둘 다 비면 안 된다). Due Date는 Next Action이 있을 때만 있다. */
  progress: string | null
  nextAction: string | null
  dueDate: string | null
  /** Next Action이 있는 행에만 값이 있다(없으면 null). */
  nextActionStatus: NextActionStatus | null
  /** 종료 상태일 때만 서버 시계의 종료 시각. */
  nextActionClosedAt: string | null
  memo: string
  statusKey: string
  forecastKey: string
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

/** Forecast 월말 스냅숏의 셀 하나(P6 R2). 코드 이름·outcome·order는 스냅숏을 만든 시점의 값이다. */
export interface ForecastSnapshotCellRecord {
  revenueYear: number
  revenueMonth: number
  ownerId: number
  forecastKey: string
  forecastName: string
  forecastOutcome: ForecastOutcome
  forecastOrder: number
  count: number
  amount: number
}

/** Forecast 월말 스냅숏(기준 월 `YYYY-MM`당 하나). 생성 이후 Deal·코드가 바뀌어도 변하지 않는다. */
export interface ForecastSnapshotRecord {
  period: string
  takenAt: string
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
  history: HistoryRecord[]
  attachments: AttachmentRecord[]
  directory: DirectoryRecord | null
  storage: StorageRecord | null
  alerts: AlertRecord
  /** 월말 스냅숏(없으면 비어 있는 것과 같다). 샘플 시드(`test/fixtures`)만 채운다. */
  forecastSnapshots?: ForecastSnapshotRecord[]
  setup: SetupState
  /** 접두사별 마지막 순번. `takeId`가 올린다. */
  counters: Record<string, number>
}

export interface MockStore {
  data: SeedData
  session: { userId: number | null }
  storageFailure: boolean
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
  return { data: seed, session: { userId }, storageFailure: false }
}
