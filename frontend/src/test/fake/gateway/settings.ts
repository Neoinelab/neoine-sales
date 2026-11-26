import type { SettingsGateway } from '../../../gateway/types'
import type { DirectorySettings, DirectorySettingsInput, DirectoryTestInput, DirectorySaveInput, StorageSettings } from '../../../shared/model/types'
import { conflict, directoryFailed, notFound, validation } from '../errors'
import type { DirectoryRecord } from '../store'
import { modeOf } from './accountRules'
import { clone, read, requireAdmin, write, type MockContext } from './context'
import { userRef } from './views'

export const FAKE_BASE_DN = 'dc=corp,dc=test'
/** 서버 문구(IN-R8·IN-R9·IN-R10·IN-R14, 2.8). 화면이 보내기 전에 막는 문구("바인드 비밀번호를 입력하세요")와는 별개다. */
const REVISION_CONFLICT = '설정이 다른 곳에서 바뀌었습니다. 새로고침 후 다시 시도하세요'
const DIRECTORY_MISSING = 'AD 설정을(를) 찾을 수 없습니다: directory'

/** 호스트·바인드 계정 필수, 포트 1~65535, 사용자 필터 필수, 연결 제한 시간 1~30초(서버 검증과 같은 범위). */
export function checkDirectoryInput(input: DirectorySettingsInput): void {
  if (input.host.trim() === '') throw validation('호스트를 입력하세요.')
  if (!Number.isInteger(input.port) || input.port < 1 || input.port > 65535) throw validation('포트는 1~65535 사이의 정수로 입력하세요.')
  if (input.userFilter.trim() === '') throw validation('사용자 필터를 입력하세요.')
  const t = input.connectTimeoutSeconds
  if (!Number.isInteger(t) || t < 1 || t > 30) throw validation('연결 제한 시간은 1~30초 사이의 정수로 입력하세요.')
}

const proofs = new WeakMap<MockContext, Map<string, { endpoint: string; scope: string; expires: number; baseDn: string }>>()

function endpoint(input: DirectorySettingsInput): string {
  return JSON.stringify([input.host, input.port, input.security, input.userFilter, input.connectTimeoutSeconds])
}

export function testConnection(ctx: MockContext, input: DirectoryTestInput, scope: string, baseDn = FAKE_BASE_DN) {
  checkDirectoryInput(input)
  if (!input.bindAccount.trim() || !input.bindPassword) throw validation('바인드 계정과 비밀번호를 입력하세요.')
  checkDirectoryReachable(input)
  let issued = proofs.get(ctx)
  if (!issued) { issued = new Map(); proofs.set(ctx, issued) }
  const now = new Date(ctx.clock.now()).getTime()
  for (const [token, proof] of issued) if (proof.expires <= now) issued.delete(token)
  const testToken = crypto.randomUUID()
  issued.set(testToken, { endpoint: endpoint(input), scope, expires: now + 600_000, baseDn })
  return { baseDn, testToken }
}

export function verifyConnection(ctx: MockContext, input: DirectorySaveInput, scope: string): string {
  const proof = proofs.get(ctx)?.get(input.testToken)
  if (!proof || proof.endpoint !== endpoint(input) || proof.scope !== scope || proof.expires <= new Date(ctx.clock.now()).getTime()) {
    throw validation('연결 테스트 결과가 없거나 만료되었습니다. 다시 연결 테스트를 수행하세요.')
  }
  return proof.baseDn
}

/** 연결 단계 실패 시뮬레이션: 호스트에 'fail'이 들어가면 연결 단계에서 실패한다. */
export function checkDirectoryReachable(input: DirectorySettingsInput): void {
  if (input.host.includes('fail')) throw directoryFailed('연결 단계에서 실패했습니다', 'connect')
}

const MAX_STORAGE_PATH = 1024

/**
 * 서버 StoragePath와 같은 규칙으로 검증하고 정규화한 경로를 돌려준다.
 * NUL 거부, 앞뒤 공백 제거, 절대 경로만, 빈 조각·`.` 제거, `..` 거부, 정규화 뒤 1024자 이내.
 * 정규화 뒤 `/readonly`로 시작하면 쓸 수 없는 위치로 본다(mock).
 */
export function validateStoragePath(path: string): string {
  if (path.includes('\u0000')) throw validation('저장 경로에는 NUL 문자를 쓸 수 없습니다')
  const trimmed = path.trim()
  if (!trimmed.startsWith('/')) throw validation('절대 경로를 입력하세요.')
  const pieces = trimmed.split('/').filter((p) => p !== '' && p !== '.')
  if (pieces.includes('..')) throw validation('절대 경로를 입력하세요.')
  const normalized = `/${pieces.join('/')}`
  if (Array.from(normalized).length > MAX_STORAGE_PATH) throw validation('저장 경로는 1024자 이내로 입력하세요.')
  if (normalized.startsWith('/readonly')) throw validation('해당 위치에 쓸 수 없습니다.')
  return normalized
}

/** 쓰기 테스트: 저장하지 않고 경로 검증 + 저장소 장애 시뮬레이션만 적용한다. */
export function saveDirectoryRecord(
  ctx: MockContext,
  input: DirectorySettingsInput,
  updatedById: number | null,
  baseDn = FAKE_BASE_DN,
): DirectoryRecord {
  const previous = ctx.store.data.directory
  // 비밀번호는 저장하지 않는다(Fake는 상태만 가진다). 새 비밀번호를 받으면 읽을 수 있는 상태로 돌아간다.
  const record: DirectoryRecord = {
    host: input.host,
    port: input.port,
    security: input.security,
    userFilter: input.userFilter,
    connectTimeoutSeconds: input.connectTimeoutSeconds,
    baseDn,
    revision: (previous?.revision ?? 0) + 1,
    updatedAt: ctx.clock.now(),
    updatedById,
  }
  ctx.store.data.directory = record
  return record
}

function directoryView(ctx: MockContext, record: DirectoryRecord): DirectorySettings {
  const { updatedById, ...rest } = clone(record)
  return { ...rest, updatedBy: updatedById === null ? null : userRef(ctx.store.data, updatedById) }
}

function storageView(ctx: MockContext, record: { path: string; updatedAt: string; updatedById: number | null }): StorageSettings {
  return { path: record.path, updatedAt: record.updatedAt, updatedBy: record.updatedById === null ? null : userRef(ctx.store.data, record.updatedById) }
}

/** 서버처럼 앱에서 계정을 직접 관리하는(local) 시스템에서는 AD 설정을 저장·테스트할 수 없다(409). */
function requireDirectoryMode(ctx: MockContext): void {
  if (modeOf(ctx) === 'local') throw conflict('AD 연동 모드에서만 쓸 수 있습니다.')
}

export function createSettingsGateway(ctx: MockContext): SettingsGateway {
  return {
    getDirectory: () =>
      read(ctx, () => {
        requireAdmin(ctx)
        const record = ctx.store.data.directory
        return record ? directoryView(ctx, record) : null
      }),
    saveDirectory: (input, auth) =>
      write(ctx, () => {
        const admin = requireAdmin(ctx)
        const previous = ctx.store.data.directory
        checkDirectoryInput(input)
        requireDirectoryMode(ctx)
        if (auth.expectedRevision === null && previous !== null) throw conflict(REVISION_CONFLICT)
        if (auth.expectedRevision !== null && previous === null) throw notFound(DIRECTORY_MISSING)
        if (auth.expectedRevision !== null && previous !== null && previous.revision !== auth.expectedRevision) throw conflict(REVISION_CONFLICT)
        const baseDn = verifyConnection(ctx, input, `admin:${admin.id}`)
        const record = saveDirectoryRecord(ctx, input, admin.id, baseDn)
        ctx.store.data.setup.directoryDone = true
        return directoryView(ctx, record)
      }),
    testDirectory: (input) =>
      write(ctx, () => {
        const admin = requireAdmin(ctx)
        requireDirectoryMode(ctx)
        return testConnection(ctx, input, `admin:${admin.id}`)
      }),
    getStorage: () =>
      read(ctx, () => {
        requireAdmin(ctx)
        const record = ctx.store.data.storage
        return record ? storageView(ctx, record) : null
      }),
    saveStorage: (path) =>
      write(ctx, () => {
        const admin = requireAdmin(ctx)
        const record = { path: validateStoragePath(path), updatedAt: ctx.clock.now(), updatedById: admin.id }
        ctx.store.data.storage = record
        return storageView(ctx, record)
      }),
    // 서버의 관리자 쓰기 테스트는 저장소 장애(503)를 내지 않고 경로 규칙·쓰기 확인(422)만 한다.
    testStorage: (path) =>
      write(ctx, () => {
        requireAdmin(ctx)
        validateStoragePath(path)
      }),
  }
}
