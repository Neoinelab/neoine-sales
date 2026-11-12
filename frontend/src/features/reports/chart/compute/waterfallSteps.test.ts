import { describe, expect, it } from 'vitest'
import { waterfallSteps } from './waterfallSteps'

/**
 * `waterfallSteps(values, showTotal)` (명세 RC-R54): 결과 행 순서대로 앞 누계에서 시작하는 뜬 막대.
 * 반환 `{ from, to, kind: 'increase' | 'decrease' | 'total' }[]`. 빈 값은 0, 0은 증가로 본다.
 */

describe('waterfallSteps: 폭포 단계 계산', () => {
  // 테스트 코드: RC-102
  it('모든 막대는 앞 막대들의 누계에서 시작한다', () => {
    // when: 값 [100, 50, 30]으로 폭포 단계를 구한다
    const steps = waterfallSteps([100, 50, 30], false)

    // then: [0,100], [100,150], [150,180]이다
    expect(steps.map((s) => [s.from, s.to])).toEqual([
      [0, 100],
      [100, 150],
      [150, 180],
    ])
  })

  // 테스트 코드: RC-102
  it('증가·감소 방향을 표시하고 감소하면 누계가 내려간다', () => {
    // when: 값 [100, -40, 25]로 폭포 단계를 구한다
    const steps = waterfallSteps([100, -40, 25], false)

    // then: 증가 0→100, 감소 100→60, 증가 60→85이다
    expect(steps.map((s) => [s.from, s.to, s.kind])).toEqual([
      [0, 100, 'increase'],
      [100, 60, 'decrease'],
      [60, 85, 'increase'],
    ])
  })

  // 테스트 코드: RC-102
  it('빈 값은 0으로 본다', () => {
    // when: 빈 값이 섞인 값으로 폭포 단계를 구한다
    const steps = waterfallSteps([10, null, 5], false)

    // then: 빈 값 단계는 누계가 그대로다
    expect(steps.map((s) => [s.from, s.to])).toEqual([
      [0, 10],
      [10, 10],
      [10, 15],
    ])
  })

  // 테스트 코드: RC-102
  it('합계를 켜면 0에서 마지막 누계까지의 합계 막대를 더한다', () => {
    // when: 합계를 켜고 폭포 단계를 구한다
    const steps = waterfallSteps([100, -40], true)

    // then: 단계가 3개이고 마지막은 0→60 합계다
    expect(steps).toHaveLength(3)
    expect(steps.at(-1)).toEqual({ from: 0, to: 60, kind: 'total' })
  })

  // 테스트 코드: RC-102
  it('합계를 켜지 않으면 합계 막대가 없다', () => {
    // when: 합계 없이 폭포 단계를 구한다
    const actual = waterfallSteps([100, -40], false).some((s) => s.kind === 'total')

    // then: 합계 단계가 없다
    expect(actual).toBe(false)
  })

  // 테스트 코드: RC-102
  it('값이 없을 때 합계를 켜면 0인 합계 막대만 남는다', () => {
    // when: 값이 없는 입력으로 합계를 켠다
    const actual = waterfallSteps([], true)
    const actual2 = waterfallSteps([], false)
    // then: 0짜리 합계 하나, 끄면 빈 목록이다
    expect(actual).toEqual([{ from: 0, to: 0, kind: 'total' }])
    expect(actual2).toEqual([])
  })
})
