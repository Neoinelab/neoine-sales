import { DEFAULT_STALE_DAYS } from '../../../shared/model/constants'
import type { MockClock } from '../clock'
import type { DirectoryRecord, SeedData, StorageRecord } from '../store'
import { seedActionTypes } from './actionTypes'
import { seedCodes, seedLabels } from './codes'
import { createSeedEnv } from './env'
import { seedUsers } from './users'

export type SeedFactory = (clock: MockClock) => SeedData

/**
 * 앱 기본 시드: 업무 데이터(Deal·연락처·Action·History·첨부)가 하나도 없는 상태.
 * 남기는 것은 로그인에 필요한 계정, PRD 기본 코드(Status·Forecast)와 BANT 기본 Label, 설정 기본값뿐이다.
 * 샘플 업무 데이터는 `src/test/fixtures/`(테스트 전용)에만 있다.
 */
export const emptyBusinessSeed: SeedFactory = (clock) => {
  const env = createSeedEnv(clock.now())
  const counters: Record<string, number> = {}
  const users = seedUsers(env)
  const codes = seedCodes(counters)
  const labels = seedLabels(env, counters)
  const actionTypes = seedActionTypes(env, counters)

  const directory: DirectoryRecord = {
    serverUrls: ['ldaps://dc1.corp.test', 'ldaps://dc2.corp.test'],
    useStarttls: false,
    caCertPem: null,
    bindTemplate: 'CORP\\{login_id}',
    baseDn: 'dc=corp,dc=test',
    userFilter: '(&(objectClass=user)(sAMAccountName={login_id}))',
    displayNameAttribute: 'displayName',
    emailAttribute: 'mail',
    connectTimeoutSeconds: 5,
    receiveTimeoutSeconds: 10,
    revision: 3,
    updatedAt: env.at(100, 9),
    updatedById: 'u-root',
  }
  const storage: StorageRecord = { path: '/data/neoine-sales/files', updatedAt: env.at(100, 9), updatedById: 'u-root' }

  return {
    users,
    codes,
    labels,
    actionTypes,
    vendors: [],
    solutions: [],
    contacts: [],
    deals: [],
    actions: [],
    history: [],
    attachments: [],
    directory,
    storage,
    alerts: { staleDays: DEFAULT_STALE_DAYS, updatedAt: null, updatedById: null },
    setup: { directoryDone: true, storageDone: true, adminDone: true },
    counters,
  }
}
