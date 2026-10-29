import type { SettingsGateway } from '../../../gateway/types'
import type { DirectorySettings, DirectorySettingsInput, StorageSettings } from '../../../shared/model/types'
import { conflict, directoryFailed, notFound, storageUnavailable, validation } from '../errors'
import type { DirectoryRecord } from '../store'
import { clone, read, requireAdmin, write, type MockContext } from './context'
import { userRef } from './views'

export const FAKE_BASE_DN = 'dc=corp,dc=test'
const BIND_PASSWORD_REQUIRED = '바인드 비밀번호를 입력하세요.'
const BIND_PASSWORD_RETYPE = '서버나 바인드 계정을 바꾸면 비밀번호를 다시 입력해야 합니다.'

/** 호스트·바인드 계정 필수, 포트 1~65535, 사용자 필터 필수, 연결 제한 시간 1~30초(서버 검증과 같은 범위). */
export function checkDirectoryInput(input: DirectorySettingsInput): void {
  if (input.host.trim() === '') throw validation('호스트를 입력하세요.')
  if (!Number.isInteger(input.port) || input.port < 1 || input.port > 65535) throw validation('포트는 1~65535 사이의 정수로 입력하세요.')
  if (input.bindAccount.trim() === '') throw validation('바인드 계정을 입력하세요.')
  if (input.userFilter.trim() === '') throw validation('사용자 필터를 입력하세요.')
  const t = input.connectTimeoutSeconds
  if (!Number.isInteger(t) || t < 1 || t > 30) throw validation('연결 제한 시간은 1~30초 사이의 정수로 입력하세요.')
}

/**
 * 바인드 비밀번호 규칙: 저장된 설정이 없으면 비밀번호가 필수이고, 있으면 null일 때 저장 값을 유지한다.
 * 다만 접속 정보(호스트·포트·보안·계정)가 저장 값과 다르거나 저장된 비밀번호를 읽을 수 없으면 새 비밀번호가 필요하다.
 */
export function checkBindPassword(input: DirectorySettingsInput, previous: DirectoryRecord | null): void {
  if (input.bindPassword !== null) {
    if (input.bindPassword === '') throw validation(BIND_PASSWORD_REQUIRED)
    return
  }
  if (previous === null) throw validation(BIND_PASSWORD_REQUIRED)
  const changed =
    input.host !== previous.host ||
    input.port !== previous.port ||
    input.security !== previous.security ||
    input.bindAccount !== previous.bindAccount
  if (changed) throw validation(BIND_PASSWORD_RETYPE)
  if (previous.bindCredentialStatus === 'unreadable') throw validation(BIND_PASSWORD_REQUIRED)
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
export function checkStorageWritable(ctx: MockContext, path: string): void {
  validateStoragePath(path)
  if (ctx.store.storageFailure) throw storageUnavailable('파일 저장 위치를 사용할 수 없습니다. 관리자에게 문의하세요.')
}

export function saveDirectoryRecord(
  ctx: MockContext,
  input: DirectorySettingsInput,
  updatedById: number | null,
): DirectoryRecord {
  const previous = ctx.store.data.directory
  // 비밀번호는 저장하지 않는다(Fake는 상태만 가진다). 새 비밀번호를 받으면 읽을 수 있는 상태로 돌아간다.
  const record: DirectoryRecord = {
    host: input.host,
    port: input.port,
    security: input.security,
    bindAccount: input.bindAccount,
    userFilter: input.userFilter,
    connectTimeoutSeconds: input.connectTimeoutSeconds,
    bindCredentialStatus: 'ok',
    baseDn: FAKE_BASE_DN,
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
        if (auth.expectedRevision === null && previous !== null) throw conflict('AD 설정이 이미 있습니다. 화면을 새로 고친 뒤 다시 시도하세요.')
        if (auth.expectedRevision !== null && previous === null) throw notFound('AD 설정이 없습니다.')
        checkBindPassword(input, previous)
        checkDirectoryReachable(input)
        const record = saveDirectoryRecord(ctx, input, admin.id)
        ctx.store.data.setup.directoryDone = true
        return directoryView(ctx, record)
      }),
    testDirectory: (input) =>
      write(ctx, () => {
        requireAdmin(ctx)
        checkDirectoryInput(input)
        checkBindPassword(input, ctx.store.data.directory)
        checkDirectoryReachable(input)
        return { baseDn: FAKE_BASE_DN }
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
    testStorage: (path) =>
      write(ctx, () => {
        requireAdmin(ctx)
        checkStorageWritable(ctx, path)
      }),
  }
}
