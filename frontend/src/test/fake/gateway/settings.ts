import type { SettingsGateway } from '../../../gateway/types'
import type { DirectorySettings, DirectorySettingsInput, StorageSettings } from '../../../shared/model/types'
import { directoryFailed, storageUnavailable, validation } from '../errors'
import type { DirectoryRecord } from '../store'
import { clone, read, requireAdmin, write, type MockContext } from './context'
import { userRef } from './views'

/** 서버 URL이 1개 이상, 필수 필드 입력, 타임아웃 1초 이상. */
export function checkDirectoryInput(input: DirectorySettingsInput): void {
  if (input.serverUrls.every((u) => u.trim() === '')) throw validation('서버 URL을 1개 이상 입력하세요.')
  if (input.bindTemplate.trim() === '') throw validation('바인드 템플릿을 입력하세요.')
  if (input.baseDn.trim() === '') throw validation('Base DN을 입력하세요.')
  if (input.userFilter.trim() === '') throw validation('사용자 필터를 입력하세요.')
  if (input.displayNameAttribute.trim() === '') throw validation('표시 이름 속성을 입력하세요.')
  if (input.emailAttribute.trim() === '') throw validation('이메일 속성을 입력하세요.')
  for (const t of [input.connectTimeoutSeconds, input.receiveTimeoutSeconds]) {
    if (!Number.isInteger(t) || t < 1) throw validation('타임아웃은 1초 이상의 정수로 입력하세요.')
  }
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
  const record: DirectoryRecord = {
    ...clone(input),
    serverUrls: input.serverUrls.map((u) => u.trim()).filter((u) => u !== ''),
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
    saveDirectory: (input) =>
      write(ctx, () => {
        const admin = requireAdmin(ctx)
        checkDirectoryInput(input)
        return directoryView(ctx, saveDirectoryRecord(ctx, input, admin.id))
      }),
    testDirectory: (input) =>
      write(ctx, () => {
        requireAdmin(ctx)
        checkDirectoryInput(input)
        if (input.serverUrls.some((u) => u.includes('fail'))) throw directoryFailed('연결 단계에서 실패했습니다', 'connect')
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
