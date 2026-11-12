import { describe, expect, it } from 'vitest'
import { funnelBars } from './funnelBars'

/**
 * `funnelBars(values)` (명세 RC-R55): 0 이하·빈 값을 빼고 결과 순서대로 가운데 정렬 막대 `[-v/2, v/2]`.
 * 반환 `{ bars: { index, value, range: [number, number] }[], skipped }`. `index`는 입력에서의 원래 위치다.
 */

describe('funnelBars: 깔때기 막대 계산', () => {
  // 테스트 코드: RC-103
  it('막대는 0을 가운데로 정렬한다', () => {
    // when: 값 [100, 60, 20]으로 깔때기 막대를 구한다
    const { bars } = funnelBars([100, 60, 20])

    // then: 막대 범위가 [-v/2, v/2]이고 값이 입력 순서다
    expect(bars.map((b) => b.range)).toEqual([
      [-50, 50],
      [-30, 30],
      [-10, 10],
    ])
    expect(bars.map((b) => b.value)).toEqual([100, 60, 20])
  })

  // 테스트 코드: RC-103
  it('입력 순서를 유지하고 정렬하지 않는다', () => {
    // when: 값 [20, 100]으로 깔때기 막대를 구한다
    const { bars } = funnelBars([20, 100])

    // then: 값이 입력 순서 그대로다
    expect(bars.map((b) => b.value)).toEqual([20, 100])
  })

  // 테스트 코드: RC-103
  it('0 이하·빈 값은 빼고 원래 위치를 유지한다', () => {
    // when: 0·빈 값·음수가 섞인 값으로 깔때기 막대를 구한다
    const { bars, skipped } = funnelBars([100, 0, null, -3, 40])

    // then: 남은 막대의 원래 index가 유지되고 뺀 개수는 3이다
    expect(bars.map((b) => [b.index, b.value])).toEqual([
      [0, 100],
      [4, 40],
    ])
    expect(skipped).toBe(3)
  })

  // 테스트 코드: RC-103
  it('양수가 없으면 막대가 없다', () => {
    // when: 양수가 없는 값으로 깔때기 막대를 구한다
    const actual = funnelBars([0, null])

    // then: 막대는 비고 뺀 개수가 2다
    expect(actual).toEqual({ bars: [], skipped: 2 })
  })
})
