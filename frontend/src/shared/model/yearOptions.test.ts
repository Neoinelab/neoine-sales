import { describe, expect, it } from 'vitest'
import { selectableYears } from './yearOptions'

/** 연도 선택지 규칙(R2): min(earliest, 올해) ~ 올해+1 연속(오름차순) + 범위 밖 URL 연도(있으면). Deals 목록·Dashboard·Forecast 공통. */

const range = (from: number, to: number): number[] => Array.from({ length: to - from + 1 }, (_, i) => from + i)

describe('selectableYears', () => {
  it('가장 이른 연도부터 내년까지 모든 연도를 만든다', () => {
    // when: 올해 2026, 가장 이른 연도 2023으로 연도 선택지를 구한다
    const actual = selectableYears(2026, 2023)
    // then: 2023부터 내년 2027까지 빠짐없이 나온다
    expect(actual).toEqual([2023, 2024, 2025, 2026, 2027])
  })

  it('데이터가 없는 연도도 빠짐없이 나열한다', () => {
    // when: 올해 2026, 가장 이른 연도 2019로 연도 선택지를 구한다
    const actual = selectableYears(2026, 2019)
    // then: 데이터 없는 해를 포함해 2019부터 2027까지 이어진다
    expect(actual).toEqual(range(2019, 2027))
  })

  it('데이터가 없으면 올해와 내년만 둔다', () => {
    // when: 올해 2026, 가장 이른 연도 null로 연도 선택지를 구한다
    const actual = selectableYears(2026, null)
    // then: 올해 2026과 내년 2027만 나온다
    expect(actual).toEqual([2026, 2027])
  })

  it('가장 이른 연도를 아직 모르면 올해와 내년만 둔다', () => {
    // when: 올해 2026, 가장 이른 연도 undefined로 연도 선택지를 구한다
    const actual = selectableYears(2026, undefined)
    // then: 올해 2026과 내년 2027만 나온다
    expect(actual).toEqual([2026, 2027])
  })

  it('가장 이른 연도가 올해면 올해부터 시작한다', () => {
    // when: 올해 2026, 가장 이른 연도 2026으로 연도 선택지를 구한다
    const actual = selectableYears(2026, 2026)
    // then: 올해 2026부터 시작해 2027까지 나온다
    expect(actual).toEqual([2026, 2027])
  })

  it('가장 이른 연도가 미래면 올해부터 시작한다', () => {
    // when: 올해 2026, 가장 이른 연도 2027로 연도 선택지를 구한다
    const actual = selectableYears(2026, 2027)
    // then: 올해 2026부터 시작해 2027까지 나온다
    expect(actual).toEqual([2026, 2027])
  })

  it('내년 뒤의 데이터 연도는 무시한다', () => {
    // when: 올해 2026, 가장 이른 연도 2029로 연도 선택지를 구한다
    const actual = selectableYears(2026, 2029)
    // then: 2029는 무시되고 2026, 2027만 나온다
    expect(actual).toEqual([2026, 2027])
  })

  it('올해+2년은 더 이상 없다', () => {
    // when: 올해 2026, 가장 이른 연도 2023으로 연도 선택지를 구한다
    const actual = selectableYears(2026, 2023)
    // then: 2028이 선택지에 없다
    expect(actual).not.toContain(2028)
  })

  it('범위 뒤의 현재 선택 연도는 한 번만 덧붙인다', () => {
    // when: 현재 선택 연도 2030을 더해 연도 선택지를 구한다
    const actual = selectableYears(2026, 2023, 2030)
    // then: 범위 끝에 2030이 한 번만 붙는다
    expect(actual).toEqual([2023, 2024, 2025, 2026, 2027, 2030])
  })

  it('범위 앞의 현재 선택 연도는 순서에 맞게 앞에 덧붙인다', () => {
    // when: 현재 선택 연도 2015를 더해 연도 선택지를 구한다
    const actual = selectableYears(2026, 2023, 2015)
    // then: 범위 앞에 2015가 붙고 오름차순이다
    expect(actual).toEqual([2015, 2023, 2024, 2025, 2026, 2027])
  })

  it('이미 있는 현재 선택 연도는 중복하지 않는다', () => {
    // when: 이미 범위에 있는 현재 선택 연도 2024를 더해 연도 선택지를 구한다
    const actual = selectableYears(2026, 2023, 2024)
    // then: 2024가 중복 없이 한 번만 나온다
    expect(actual).toEqual([2023, 2024, 2025, 2026, 2027])
  })

  it('가장 이른 연도를 몰라도 현재 선택 연도는 더한다', () => {
    // when: 가장 이른 연도 null에 현재 선택 연도 2024를 더해 연도 선택지를 구한다
    const actual = selectableYears(2026, null, 2024)
    // then: 현재 선택 연도 2024가 올해·내년과 함께 나온다
    expect(actual).toEqual([2024, 2026, 2027])
  })

  it('항상 오름차순이고 중복이 없다', () => {
    // when: 범위가 매우 넓고 범위 밖 연도가 있을 때 선택지를 구한다
    const years = selectableYears(2026, 2000, 1990)
    // then: 오름차순이고 중복이 없다
    expect(years).toEqual([...new Set(years)].sort((a, b) => a - b))
  })

  it('올해가 바뀌면 같이 움직인다', () => {
    // when: 올해 2027, 가장 이른 연도 2025로 연도 선택지를 구한다
    const actual = selectableYears(2027, 2025)
    // then: 2027년 기준 2025부터 2028까지 나온다
    expect(actual).toEqual([2025, 2026, 2027, 2028])
  })
})
