/** 테스트 전용 샘플 시드(계획 4.3). 앱 기본 시드(`emptyBusinessSeed`)에 샘플 업무 데이터를 얹는다. 모든 날짜는 clock.now() 기준 상대값이다. */

import type { MockClock } from '../fake/clock'
import { createSeedEnv } from '../fake/seed/env'
import { emptyBusinessSeed } from '../fake/seed'
import type { SeedData } from '../fake/store'
import { addDays } from '../../shared/model/dates'
import { seedActivity } from './activity'
import { seedAttachments } from './attachments'
import { seedContacts } from './contacts'
import { DEAL_SPECS } from './dealSpecs'
import { dealCodeOf, seedDeals } from './deals'
import { SEED_SOLUTION_COUNT, SEED_VENDORS } from './vendors'

export function buildSampleSeed(clock: MockClock): SeedData {
  const base = emptyBusinessSeed(clock)
  const env = createSeedEnv(clock.now())
  const { counters, users, codes, labels } = base
  const contacts = seedContacts(env, counters)
  const deals = seedDeals(env, DEAL_SPECS, contacts, labels, codes)
  const userNames = new Map(users.map((u) => [u.id, u.name]))
  const activity = seedActivity(env, DEAL_SPECS, deals, codes, contacts, userNames, counters)
  const files = seedAttachments(env, deals, counters)
  const at = env.at(120, 9)
  const vendors = SEED_VENDORS.map((v) => ({ id: v.id, name: v.name, createdAt: at, updatedAt: at }))
  const solutions = SEED_VENDORS.flatMap((v) =>
    v.solutions.map((s) => ({ id: s.id, vendorId: v.id, name: s.name, createdAt: at, updatedAt: at })),
  )
  counters.vd = SEED_VENDORS.length
  counters.sl = SEED_SOLUTION_COUNT
  return {
    ...base,
    vendors,
    solutions,
    contacts,
    deals,
    actions: activity.actions,
    history: [...activity.history, ...files.history],
    attachments: files.attachments,
  }
}

/** 계획 4.3의 Deal 번호(1~24) → Deal code. 테스트용. */
export function seedDealCode(no: number, today: string): string {
  const spec = DEAL_SPECS.find((s) => s.no === no)
  if (!spec) throw new RangeError(`시드 Deal 번호는 1~24입니다: ${no}`)
  return dealCodeOf(spec, { date: (offset) => addDays(today, offset) })
}
