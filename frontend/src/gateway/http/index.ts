/**
 * HTTP 게이트웨이 조립. 서버가 있는 도메인(auth·setup·users·settings·codes·labels·contacts·deals·history·actions)만 실제로 연결하고,
 * 아직 없는 도메인(attachments·forecast)은 501 "아직 실제 서버와 연결되지 않은 기능입니다."로 둔다.
 * 단계(P1·P2·P2b…)마다 `notImplemented`를 실제 구현으로 바꾼다. features는 이 폴더를 직접 import하지 않는다(경계 테스트).
 */

import type { Gateway } from '../types'
import { createActionsHttp } from './actions'
import { createAuthHttp } from './auth'
import { createCodesHttp } from './codes'
import { createContactsHttp } from './contacts'
import { createDealsHttp } from './deals'
import { createHistoryHttp } from './history'
import { createLabelsHttp } from './labels'
import { createSettingsHttp } from './settings'
import { createSetupHttp } from './setup'
import { notImplemented } from './unsupported'
import { createUsersHttp } from './users'

export function createHttpGateway(): Gateway {
  return {
    auth: createAuthHttp(),
    setup: createSetupHttp(),
    users: createUsersHttp(),
    settings: createSettingsHttp(),
    codes: createCodesHttp(),
    labels: createLabelsHttp(),
    contacts: createContactsHttp(),
    deals: createDealsHttp(),
    actions: createActionsHttp(),
    history: createHistoryHttp(),
    attachments: { list: notImplemented, upload: notImplemented, remove: notImplemented, download: notImplemented },
    forecast: { summary: notImplemented },
  }
}
