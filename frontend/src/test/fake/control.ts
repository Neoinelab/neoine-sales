import type { MockControl } from './types'
import { setSession, type MockContext } from './gateway/context'

/** 테스트용 제어. 게이트웨이 메서드가 아니므로 권한·History와 무관하다. */
export function createMockControl(ctx: MockContext, reseed: () => void): MockControl {
  return {
    resetData: reseed,
    restartSetup() {
      ctx.store.data.setup = { directoryDone: false, storageDone: false, adminDone: false }
      ctx.store.data.directory = null
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
    seedSavedReports(reports) {
      const state = ctx.store.reports
      state.saved = JSON.parse(JSON.stringify(reports)) as typeof reports
      state.nextSavedId = reports.reduce((max, r) => Math.max(max, r.id), 0) + 1
    },
    setLayoutSaveGate(gate) {
      ctx.store.reports.layoutGate = gate
    },
    touchSavedReport(id, change = {}) {
      const target = ctx.store.reports.saved.find((r) => r.id === id)
      if (!target) throw new Error(`저장 리포트 없음: ${id}`)
      const park = ctx.store.data.users.find((u) => u.name === '박영업')
      if (!park) throw new Error('박영업 사용자가 없습니다.')
      target.revision += 1
      target.updatedAt = ctx.clock.now()
      target.updatedBy = { id: park.id, name: park.name, role: park.role, status: 'active' }
      if (change.layout) target.layout = JSON.parse(JSON.stringify(change.layout)) as typeof change.layout
      if (change.name) target.name = change.name
    },
    savedReportRequests: () => ctx.store.reports.requests.map((r) => JSON.parse(JSON.stringify(r)) as typeof r),
  }
}
