import type { AlertsGateway } from '../../../gateway/types'
import {
  STALE_DAYS_MAX,
  STALE_DAYS_MIN,
  STALE_DAYS_RANGE_MESSAGE,
} from '../../../shared/model/constants'
import type { AlertSettings } from '../../../shared/model/types'
import { requestValidation, validation } from '../errors'
import { read, requireAdmin, requireUser, write, type MockContext } from './context'
import { userRef } from './views'

function alertView(ctx: MockContext): AlertSettings {
  const { alerts } = ctx.store.data
  return {
    staleDays: alerts.staleDays,
    updatedAt: alerts.updatedAt,
    updatedBy: alerts.updatedById === null ? null : userRef(ctx.store.data, alerts.updatedById),
  }
}

/** 서버와 같다: 정수가 아니면 요청 형식 오류(422 request-validation), 1~365 밖 정수는 범위 문구(422 invalid-value). */
function checkStaleDays(value: number): void {
  if (!Number.isInteger(value)) throw requestValidation()
  if (value < STALE_DAYS_MIN || value > STALE_DAYS_MAX) throw validation(STALE_DAYS_RANGE_MESSAGE)
}

export function createAlertsGateway(ctx: MockContext): AlertsGateway {
  return {
    get: () =>
      read(ctx, () => {
        requireUser(ctx)
        return alertView(ctx)
      }),
    save: (staleDays) =>
      write(ctx, () => {
        const admin = requireAdmin(ctx)
        checkStaleDays(staleDays)
        ctx.store.data.alerts = { staleDays, updatedAt: ctx.clock.now(), updatedById: admin.id }
        return alertView(ctx)
      }),
  }
}
