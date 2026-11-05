import { describe, expect, it } from 'vitest'
import { leavesWon } from './sync'

/** Won(Forecast won) 이탈 판정(AC9): 확인 대화상자를 띄울지 정한다. 프런트·서버 규칙이 같다(서버: won_transition left). */
const won = { statusKey: 'contract_completed', forecastKey: 'won' }

describe('leavesWon (AC9)', () => {
  it.each([
    ['commit', 'technical_evaluation'],
    ['best', 'technical_evaluation'],
    ['lost', 'prospecting'],
    ['pipeline', 'prospecting'],
  ])('is true when a Won deal moves to forecast %s', (forecastKey, statusKey) => {
    expect(leavesWon(won, { statusKey, forecastKey })).toBe(true)
  })

  it('is false when the deal stays Won', () => {
    expect(leavesWon(won, { ...won })).toBe(false)
  })

  it.each([
    [{ statusKey: 'prospecting', forecastKey: 'pipeline' }, { statusKey: 'contract_completed', forecastKey: 'won' }],
    [{ statusKey: 'prospecting', forecastKey: 'pipeline' }, { statusKey: 'prospecting', forecastKey: 'commit' }],
    [{ statusKey: 'prospecting', forecastKey: 'lost' }, { statusKey: 'prospecting', forecastKey: 'pipeline' }],
  ])('is false when the deal was not Won before (%j -> %j)', (before, after) => {
    expect(leavesWon(before, after)).toBe(false)
  })
})
