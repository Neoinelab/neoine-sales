/** 상세 화면 공용 도우미(순수 함수). */
import type { SyncApplied, SyncResolution } from '../../../shared/model/sync'

/**
 * `useSyncedChange`가 돌려준 결과를 게이트웨이 `ApplyChangeRequest.resolution`으로 바꾼다(A3 산출물 사용 예).
 * 필요 없는 값은 게이트웨이가 무시한다.
 */
export function toResolution(applied: SyncApplied): SyncResolution {
  const resolution: SyncResolution = {}
  if (applied.revenue) {
    resolution.revenueAmount = applied.revenue.amount
    resolution.revenueDate = applied.revenue.date
  }
  if (applied.patch.statusKey !== undefined) resolution.statusKey = applied.patch.statusKey
  if (applied.patch.forecastKey !== undefined) resolution.forecastKey = applied.patch.forecastKey
  return resolution
}

/** 게이트웨이 오류의 종류(`ApiError.kind`). features는 `shared/api`를 직접 import하지 않으므로 형태로 판별한다. */
export function errorKind(error: unknown): string | undefined {
  if (typeof error === 'object' && error !== null && 'kind' in error) {
    const kind = (error as { kind?: unknown }).kind
    return typeof kind === 'string' ? kind : undefined
  }
  return undefined
}

/** 사용자에게 보일 오류 문구. */
export function messageOf(error: unknown): string {
  return error instanceof Error ? error.message : '요청을 처리하지 못했습니다. 잠시 후 다시 시도하세요.'
}

/** 파일 크기 표기: 1KB 미만은 B, 1MB 미만은 KB, 그 이상은 MB(소수 한 자리). */
export function formatBytes(size: number): string {
  if (size < 1024) return `${size} B`
  if (size < 1024 * 1024) return `${Math.round(size / 1024)} KB`
  return `${(size / (1024 * 1024)).toFixed(1)} MB`
}

/** 업로드 설명 글자 수(서로게이트 쌍을 한 글자로 센다. `validateUpload`와 같은 기준). */
export function charCount(text: string): number {
  return Array.from(text).length
}

/** Blob을 내려받게 한다(목업 다운로드). jsdom 등 `URL.createObjectURL`이 없는 환경에서는 건너뛴다. */
export function saveBlob(fileName: string, blob: Blob): void {
  if (typeof URL.createObjectURL !== 'function') return
  const url = URL.createObjectURL(blob)
  const anchor = document.createElement('a')
  anchor.href = url
  anchor.download = fileName
  anchor.click()
  URL.revokeObjectURL(url)
}
