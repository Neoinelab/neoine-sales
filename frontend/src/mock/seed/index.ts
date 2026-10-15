import { addDays } from '../../shared/model/dates'
import type { MockClock } from '../clock'
import type { DirectoryRecord, SeedData, StorageRecord } from '../store'
import { seedAttachments } from './attachments'
import { seedActivity } from './activity'
import { seedCodes, seedLabels } from './codes'
import { seedContacts } from './contacts'
import { DEAL_SPECS } from './dealSpecs'
import { dealCodeOf, seedDeals } from './deals'
import { createSeedEnv } from './env'
import { seedUsers } from './users'

export type SeedFactory = (clock: MockClock) => SeedData

/** 계획 4.3의 시드. 모든 날짜는 clock.now() 기준 상대값이다. */
export function buildSeed(clock: MockClock): SeedData {
  const env = createSeedEnv(clock.now())
  const counters: Record<string, number> = {}
  const users = seedUsers(env)
  const codes = seedCodes(counters)
  const labels = seedLabels(env, counters)
  const contacts = seedContacts(env, counters)
  const deals = seedDeals(env, DEAL_SPECS, contacts, labels, codes)
  const userNames = new Map(users.map((u) => [u.id, u.name]))
  const activity = seedActivity(env, DEAL_SPECS, deals, codes, contacts, userNames, counters)
  const files = seedAttachments(env, deals, counters)

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
    contacts,
    deals,
    actions: activity.actions,
    history: [...activity.history, ...files.history],
    attachments: files.attachments,
    directory,
    storage,
    setup: { directoryDone: true, storageDone: true, adminDone: true },
    counters,
  }
}

/** 계획 4.3의 Deal 번호(1~24) → Deal code. 테스트와 문서용. */
export function seedDealCode(no: number, today: string): string {
  const spec = DEAL_SPECS.find((s) => s.no === no)
  if (!spec) throw new RangeError(`시드 Deal 번호는 1~24입니다: ${no}`)
  return dealCodeOf(spec, { date: (offset) => addDays(today, offset) })
}
