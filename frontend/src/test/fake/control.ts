import type { MockControl } from './types'
import { setSession, type MockContext } from './gateway/context'

/** 테스트용 제어. 게이트웨이 메서드가 아니므로 권한·History와 무관하다. */
export function createMockControl(ctx: MockContext, reseed: () => void): MockControl {
  return {
    resetData: reseed,
    restartSetup() {
      ctx.store.data.setup = { directoryDone: false, storageDone: false, adminDone: false }
      setSession(ctx, null)
    },
    setStorageFailure(on) {
      ctx.store.storageFailure = on
    },
    isStorageFailure: () => ctx.store.storageFailure,
    now: () => ctx.clock.now(),
    setLatency: (on) => ctx.latency.setOn(on),
    isLatencyOn: () => ctx.latency.isOn(),
    setReportQueryHandler(handler) {
      ctx.store.reports.handler = handler
    },
    reportQueries: () => [...ctx.store.reports.queries],
  }
}
