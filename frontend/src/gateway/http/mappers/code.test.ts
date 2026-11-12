import { describe, expect, it } from 'vitest'
import { toCode } from './code'

const base = { id: 1, kind: 'forecast', key: 'won', name: 'Won', order: 5, locked: true, probability_hint: null } as const

describe('toCode', () => {
  // open·won·lost 결과는 그대로 받아들인다.
  it.each(['open', 'won', 'lost'])('accepts the outcome %s', (outcome) => {
    // when: 결과를 가진 응답을 코드로 바꾼다
    const code = toCode({ ...base, outcome })

    // then: 결과가 그대로다
    expect(code.outcome).toBe(outcome)
  })

  // 모르는 결과는 화면으로 넘기지 않고 해석 불가 오류로 거절한다.
  // 테스트 코드: CD-070
  it('rejects an unknown outcome instead of passing it to the screens', () => {
    // when·then: 모르는 결과 "maybe"로 바꾼다 → "서버 응답을 해석할 수 없습니다." 오류다
    expect(() => toCode({ ...base, outcome: 'maybe' })).toThrow('서버 응답을 해석할 수 없습니다.')
  })
})
