import type { Gateway } from '../../../gateway/types'
import { createActionsGateway } from './actions'
import { createActionTypesGateway } from './actionTypes'
import { createAlertsGateway } from './alerts'
import { createAttachmentsGateway } from './attachments'
import { createAuthGateway, createSetupGateway } from './auth'
import { createCodesGateway } from './codes'
import type { MockContext } from './context'
import { createContactsGateway } from './contacts'
import { createDashboardGateway } from './dashboard'
import { dealsReadApi } from './dealsRead'
import { dealsWriteApi } from './dealsWrite'
import { createForecastGateway } from './forecast'
import { createHistoryGateway } from './history'
import { createLabelsGateway } from './labels'
import { createReportsGateway } from './reports'
import { createSettingsGateway } from './settings'
import { createTimeGateway } from './time'
import { createUsersGateway } from './users'
import { createVendorsGateway } from './vendors'

/** 도메인별 mock 구현을 모아 `Gateway`를 만든다. 모든 구현은 같은 맥락(저장소·시계·지연)을 공유한다. */
export function createGatewayFor(ctx: MockContext): Gateway {
  return {
    auth: createAuthGateway(ctx),
    setup: createSetupGateway(ctx),
    deals: { ...dealsReadApi(ctx), ...dealsWriteApi(ctx) },
    contacts: createContactsGateway(ctx),
    actions: createActionsGateway(ctx),
    actionTypes: createActionTypesGateway(ctx),
    history: createHistoryGateway(ctx),
    attachments: createAttachmentsGateway(ctx),
    codes: createCodesGateway(ctx),
    labels: createLabelsGateway(ctx),
    vendors: createVendorsGateway(ctx),
    forecast: createForecastGateway(ctx),
    dashboard: createDashboardGateway(ctx),
    reports: createReportsGateway(ctx),
    users: createUsersGateway(ctx),
    settings: createSettingsGateway(ctx),
    alerts: createAlertsGateway(ctx),
    time: createTimeGateway(ctx),
  }
}
