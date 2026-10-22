/** Solution 도입 전 레거시 Deal(Solution 빈 값)을 가진 시드. 서버에 남아 있는 예전 행을 흉내 낸다. */

import type { MockClock } from '../fake/clock'
import type { SeedData } from '../fake/store'
import { buildSampleSeed } from './sampleSeed'

export function buildLegacySolutionSeed(clock: MockClock): SeedData {
  const seed = buildSampleSeed(clock)
  return { ...seed, deals: seed.deals.map((deal) => ({ ...deal, solution: '' })) }
}
