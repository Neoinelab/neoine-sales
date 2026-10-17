import type { AlertsGateway } from '../../../gateway/types'
import {
  STALE_DAYS_MAX,
  STALE_DAYS_MIN,
  STALE_DAYS_RANGE_MESSAGE,
} from '../../../shared/model/constants'
import type { AlertSettings } from '../../../shared/model/types'
import { validation } from '../errors'
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

/** 1~365 정수만 허용한다. 서버는 비정수를 일반 요청 검증(422)으로 거절하고, mock은 같은 범위 메시지로 단순화한다. */
function checkStaleDays(value: number): void {
  if (!Number.isInteger(value) || value < STALE_DAYS_MIN || value > STALE_DAYS_MAX) {
    throw validation(STALE_DAYS_RANGE_MESSAGE)
  }
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
