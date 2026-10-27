/**
 * HTTP 게이트웨이 조립. 서버가 있는 도메인(auth·setup·users·settings·codes·labels·contacts·deals·history·actions·attachments·forecast·dashboard·reports)를 모두 실제 서버에 연결한다.
 * features는 이 폴더를 직접 import하지 않는다(경계 테스트).
 */

import type { Gateway } from '../types'
import { createActionsHttp } from './actions'
import { createActionTypesHttp } from './actionTypes'
import { createAlertsHttp } from './alerts'
import { createAttachmentsHttp } from './attachments'
import { createAuthHttp } from './auth'
import { createCodesHttp } from './codes'
import { createContactsHttp } from './contacts'
import { createDashboardHttp } from './dashboard'
import { createDealsHttp } from './deals'
import { createForecastHttp } from './forecast'
import { createHistoryHttp } from './history'
import { createLabelsHttp } from './labels'
import { createReportsHttp } from './reports'
import { createSettingsHttp } from './settings'
import { createSetupHttp } from './setup'
import { createTimeHttp } from './time'
import { createUsersHttp } from './users'
import { createVendorsHttp } from './vendors'

export function createHttpGateway(): Gateway {
  return {
    auth: createAuthHttp(),
    setup: createSetupHttp(),
    users: createUsersHttp(),
    settings: createSettingsHttp(),
    alerts: createAlertsHttp(),
    codes: createCodesHttp(),
    labels: createLabelsHttp(),
    vendors: createVendorsHttp(),
    contacts: createContactsHttp(),
    deals: createDealsHttp(),
    actions: createActionsHttp(),
    actionTypes: createActionTypesHttp(),
    history: createHistoryHttp(),
    attachments: createAttachmentsHttp(),
    forecast: createForecastHttp(),
    dashboard: createDashboardHttp(),
    reports: createReportsHttp(),
    time: createTimeHttp(),
  }
}
