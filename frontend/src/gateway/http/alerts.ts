import { api } from '../../shared/api/client'
import type { Schemas } from '../../shared/api/client'
import type { AlertSettings } from '../../shared/model/types'
import type { AlertsGateway } from '../types'
import { toUserRef } from './mappers/user'
import { unwrap } from './request'

function toAlertSettings(row: Schemas['AlertSettingsResponse']): AlertSettings {
  return {
    staleDays: row.stale_days,
    updatedAt: row.updated_at,
    updatedBy: row.updated_by === null ? null : toUserRef(row.updated_by),
  }
}

export function createAlertsHttp(): AlertsGateway {
  return {
    get: async () => toAlertSettings(await unwrap(api.GET('/api/v1/alert-settings'))),
    save: async (staleDays) =>
      toAlertSettings(await unwrap(api.PUT('/api/v1/alert-settings', { body: { stale_days: staleDays } }))),
  }
}
