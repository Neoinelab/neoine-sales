import type { ReportQueryInput, SavedReport } from '../../shared/model/reportTypes'
import type { ReportQueryHandler, SavedReportRequest } from './store'

/**
 * Fake 전용 제어(테스트가 사용). `default.ts`가 `mockControl`로 내보낸다.
 * 게이트웨이 메서드가 아니므로 권한·History와 무관하다.
 */
export interface MockControl {
  /** 시드로 복원(로그인 유지). 쿼리 캐시 무효화는 호출자가 `queryClient.invalidateQueries()`로 한다. */
  resetData(): void
  /** SetupState를 모두 false로 하고 로그아웃(세션 제거). */
  restartSetup(): void
  setStorageFailure(on: boolean): void
  isStorageFailure(): boolean
  /** 가짜 지연 on/off. 테스트 모드에서는 항상 0ms. */
  now(): string // Fake 시계의 지금(ISO). 화면은 `useToday()`(data/today.ts)로만 읽는다.
  setLatency(on: boolean): void
  isLatencyOn(): boolean
  /** 리포트 조회 응답을 지정한다(결과를 돌려주거나 ApiError를 throw). null이면 Fake의 기본 규칙. `resetData`가 지운다. */
  setReportQueryHandler(handler: ReportQueryHandler | null): void
  /** Fake가 받은 리포트 조회 요청 기록(오래된 것부터). `resetData`가 비운다. */
  reportQueries(): ReportQueryInput[]
  /** 저장된 리포트를 이 목록으로 바꾼다(비어 있던 저장소 기준). 다음 id는 가장 큰 id + 1이다. `resetData`가 비운다. */
  seedSavedReports(reports: SavedReport[]): void
  /** Fake가 받은 저장 리포트 요청(create·update·copy·remove·run) 기록, 오래된 것부터. `resetData`가 비운다. */
  savedReportRequests(): SavedReportRequest[]
}
