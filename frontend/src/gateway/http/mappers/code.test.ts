import { describe, expect, it } from 'vitest'
import { toCode } from './code'

const base = { id: 1, kind: 'forecast', key: 'won', name: 'Won', order: 5, locked: true, probability_hint: null } as const

describe('toCode', () => {
  it.each(['open', 'won', 'lost'])('accepts the outcome %s', (outcome) => {
    expect(toCode({ ...base, outcome }).outcome).toBe(outcome)
  })

  it('rejects an unknown outcome instead of passing it to the screens', () => {
    expect(() => toCode({ ...base, outcome: 'maybe' })).toThrow('서버 응답을 해석할 수 없습니다.')
  })
})
