/** 메모리 저장소. 시드의 사본을 들고 있고, 변경은 게이트웨이가 한다. 반환 시에는 뷰 변환으로 복사본을 만든다. */

import type {
  BantCategory,
  Code,
  Contact,
  Deal,
  DirectorySettings,
  HistoryCategory,
  Role,
  SetupState,
  UserStatus,
} from '../../shared/model/types'

export interface UserRecord {
  id: string
  loginId: string
  name: string
  role: Role
  status: UserStatus
  email: string | null
  createdAt: string
  createdById: string | null
  lastLoginAt: string | null
  resignedAt: string | null
  resignReason: string | null
}

export interface ActionRecord {
  id: string
  dealCode: string
  actedAt: string
  actorId: string
  /** Action 유형(`ActionTypeRecord.id`). 이름은 읽을 때 조인한다. */
  typeId: string
  progress: string
  nextAction: string
  dueDate: string
  memo: string
  statusKey: string
  forecastKey: string
}

export interface HistoryRecord {
  id: string
  /** 같은 시각 정렬용 일련번호(클수록 나중). */
  seq: number
  dealCode: string
  at: string
  byId: string
  category: HistoryCategory
  target: string
  before: string
  after: string
}

export interface AttachmentRecord {
  id: string
  dealCode: string
  fileName: string
  size: number
  mime: string
  description: string
  uploadedById: string
  uploadedAt: string
  /** 업로드한 파일 또는 시드의 더미 텍스트. */
  content: Blob | string
}

/** Action 유형 카탈로그 항목. 기본 유형은 시드 순서를 유지하고 이름은 대소문자 무시로 고유하다. */
export interface ActionTypeRecord {
  id: string
  name: string
  isDefault: boolean
  createdById: string | null
  createdAt: string
  updatedAt: string
}

export interface LabelRecord {
  id: string
  category: BantCategory
  name: string
  isDefault: boolean
  createdById: string | null
  createdAt: string
}

/** Vendor(Aggregate Root). 이름은 대소문자 무시로 고유. */
export interface VendorRecord {
  id: string
  name: string
  createdAt: string
  updatedAt: string
}

/** Vendor 소속 Solution. 이름은 같은 Vendor 안에서 대소문자 무시로 고유. */
export interface SolutionRecord {
  id: string
  vendorId: string
  name: string
  createdAt: string
  updatedAt: string
}

export type DirectoryRecord = Omit<DirectorySettings, 'updatedBy'> & { updatedById: string | null }

export interface StorageRecord {
  path: string
  updatedAt: string
  updatedById: string | null
}

/** 경고 기준(미업데이트 일수). 저장된 적이 없으면 updatedAt/updatedById가 null. */
export interface AlertRecord {
  staleDays: number
  updatedAt: string | null
  updatedById: string | null
}

/** 시드가 만들어 주는 전체 데이터. */
export interface SeedData {
  users: UserRecord[]
  codes: Code[]
  labels: LabelRecord[]
  actionTypes: ActionTypeRecord[]
  vendors: VendorRecord[]
  solutions: SolutionRecord[]
  contacts: Contact[]
  deals: Deal[]
  actions: ActionRecord[]
  history: HistoryRecord[]
  attachments: AttachmentRecord[]
  directory: DirectoryRecord | null
  storage: StorageRecord | null
  alerts: AlertRecord
  setup: SetupState
  /** 접두사별 마지막 순번. `takeId`가 올린다. */
  counters: Record<string, number>
}

export interface MockStore {
  data: SeedData
  session: { userId: string | null }
  storageFailure: boolean
}

/** `prefix-001` 형식의 순번 id를 만든다(테스트 안정성을 위해 UUID를 쓰지 않는다). */
export function takeId(counters: Record<string, number>, prefix: string): string {
  const next = (counters[prefix] ?? 0) + 1
  counters[prefix] = next
  return `${prefix}-${String(next).padStart(3, '0')}`
}

/**
 * Vendor·Solution id는 서버처럼 UUID 형식이다(목록 URL의 `vendor`·`solution` 값은 UUID일 때만 질의가 되므로).
 * 순번이 같으면 같은 id가 나온다: vendors는 `10000000-…`, solutions는 `20000000-…`로 시작한다.
 */
export function uuidOf(prefix: 'vd' | 'sl', n: number): string {
  return `${prefix === 'vd' ? '1' : '2'}0000000-0000-4000-8000-${String(n).padStart(12, '0')}`
}

/** `uuidOf` 형식의 새 id(카운터를 올린다). */
export function takeUuid(counters: Record<string, number>, prefix: 'vd' | 'sl'): string {
  const next = (counters[prefix] ?? 0) + 1
  counters[prefix] = next
  return uuidOf(prefix, next)
}

/** History 일련번호. */
export function nextSeq(counters: Record<string, number>): number {
  const next = (counters.seq ?? 0) + 1
  counters.seq = next
  return next
}

export function createStore(seed: SeedData, userId: string | null): MockStore {
  return { data: seed, session: { userId }, storageFailure: false }
}
