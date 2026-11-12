import { describe, expect, it } from 'vitest'
import { leavesWon } from './sync'

/** Won(Forecast won) 이탈 판정: 확인 대화상자를 띄울지 정한다. 프런트·서버 규칙이 같다(서버: won_transition left). */
const won = { statusKey: 'contract_completed', forecastKey: 'won' }

describe('leavesWon', () => {
  it.each([
    ['commit', 'technical_evaluation'],
    ['best', 'technical_evaluation'],
    ['lost', 'prospecting'],
    ['pipeline', 'prospecting'],
  ])('Won Deal이 Forecast %s(으)로 옮겨가면 Won을 벗어난 것이다', (forecastKey, statusKey) => {
    // when: Won에서 다른 Forecast로 바꾼 뒤 이탈 여부를 판정한다
    const result = leavesWon(won, { statusKey, forecastKey })

    // then: 이탈이다
    expect(result).toBe(true)
  })

  it('Won을 유지하면 Won 이탈이 아니다', () => {
    // when: Won 그대로의 상태로 판정한다
    const result = leavesWon(won, { ...won })

    // then: 이탈이 아니다
    expect(result).toBe(false)
  })

  it.each([
    [{ statusKey: 'prospecting', forecastKey: 'pipeline' }, { statusKey: 'contract_completed', forecastKey: 'won' }],
    [{ statusKey: 'prospecting', forecastKey: 'pipeline' }, { statusKey: 'prospecting', forecastKey: 'commit' }],
    [{ statusKey: 'prospecting', forecastKey: 'lost' }, { statusKey: 'prospecting', forecastKey: 'pipeline' }],
  ])('이전에 Won이 아니었으면 Won 이탈이 아니다 (%j -> %j)', (before, after) => {
    // when: Won이 아닌 상태에서 다른 상태로 바꾼 뒤 판정한다
    const result = leavesWon(before, after)

    // then: 이탈이 아니다
    expect(result).toBe(false)
  })
})
