import { describe, expect, it } from 'vitest'
import { bubbleRadius } from './bubbleRadius'

/**
 * `bubbleRadius(sizes)` (명세 RC-R47): 반지름 = 4 + 26 * sqrt(크기 / 최대 크기). 면적이 크기에 비례하고 최대는 30px.
 * 반환 `{ radii: (number | null)[], skipped }`: 입력과 같은 길이이고 0 이하·빈 값 자리는 null(그리지 않음)이다.
 */

describe('bubbleRadius: 거품 반지름 계산', () => {
  // 테스트 코드: RC-092
  it('가장 큰 크기의 반지름은 30px이다', () => {
    // when: 크기 [10, 40, 20]의 반지름을 구한다
    const actual = bubbleRadius([10, 40, 20]).radii[1]

    // then: 가장 큰 크기(40)의 반지름이 30이다
    expect(actual).toBeCloseTo(30, 10)
  })

  // 테스트 코드: RC-092
  it('면적이 크기에 비례해 크기의 1/4은 반지름이 17이다', () => {
    // when: 크기 [100, 25]의 반지름을 구한다
    const { radii } = bubbleRadius([100, 25])

    // then: 둘째 반지름이 4 + 26 × √0.25 = 17이다
    expect(radii[1]).toBeCloseTo(17, 10) // 4 + 26 * sqrt(0.25)
  })

  // 테스트 코드: RC-092
  it('길이를 유지하고 0 이하·빈 크기 자리는 그리지 않는다(null)', () => {
    // when: 0·빈 값·음수가 섞인 크기의 반지름을 구한다
    const { radii, skipped } = bubbleRadius([100, 0, null, -5, 25])

    // then: 길이 5, 그리지 않을 자리는 null, 뺀 개수는 3이다
    expect(radii).toHaveLength(5)
    expect(radii[1]).toBeNull()
    expect(radii[2]).toBeNull()
    expect(radii[3]).toBeNull()
    expect(radii[4]).toBeCloseTo(17, 10)
    expect(skipped).toBe(3)
  })

  // 테스트 코드: RC-092
  it('그릴 것이 없으면 null만 돌려준다', () => {
    // when: 그릴 수 없는 크기의 반지름을 구한다
    const actual = bubbleRadius([0, null])

    // then: null만 있고 뺀 개수가 2다
    expect(actual).toEqual({ radii: [null, null], skipped: 2 })
  })

  // 테스트 코드: RC-092
  it('양수 하나는 가장 큰 반지름으로 그린다', () => {
    // when: 양수 하나의 반지름을 구한다
    const actual = bubbleRadius([7]).radii[0]

    // then: 반지름이 30이다
    expect(actual).toBeCloseTo(30, 10)
  })
})
