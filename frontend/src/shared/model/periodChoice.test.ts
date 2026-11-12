import { describe, expect, it } from 'vitest'
import { PAST_PERIOD_LABELS, UPCOMING_PERIOD_LABELS, resolvePeriodChoice } from './periodChoice'
import type { UpdatedPeriods } from './types'

const PRESETS: UpdatedPeriods = {
  today: '2026-10-22',
  periods: [
    { key: '2w', from: '2026-10-08', to: '2026-10-22' },
    { key: '1m', from: '2026-09-22', to: '2026-10-22' },
    { key: '2m', from: '2026-08-22', to: '2026-10-22' },
    { key: '3m', from: '2026-07-22', to: '2026-10-22' },
    { key: '6m', from: '2026-04-22', to: '2026-10-22' },
  ],
  upcoming: [
    { key: '1m', from: '2026-10-22', to: '2026-11-22' },
    { key: '2m', from: '2026-10-22', to: '2026-12-22' },
  ],
}

describe('resolvePeriodChoice', () => {
  // "전체"와 "직접 지정"은 프리셋 날짜가 없다.
  it('returns undefined for all and for custom', () => {
    // when·then: 선택값이 빈 문자열(전체)·custom이면 undefined다.
    expect(resolvePeriodChoice('', PRESETS)).toBeUndefined()
    expect(resolvePeriodChoice('custom', PRESETS)).toBeUndefined()
  })

  // 지난 기간 키는 서버가 준 기간 날짜로 풀린다.
  it.each(PRESETS.periods)('resolves the past key $key to the server period', ({ key, from, to }) => {
    // when·then: 서버 프리셋의 from·to와 같다.
    expect(resolvePeriodChoice(key, PRESETS)).toEqual({ from, to })
  })

  // 향후 키는 지난 기간이 아니라 향후 기간으로 풀린다.
  it('resolves next1m and next2m to the upcoming ranges, not to the past 1m and 2m', () => {
    // when·then: next1m·next2m은 upcoming 범위, 1m은 지난 1개월이다.
    expect(resolvePeriodChoice('next1m', PRESETS)).toEqual({ from: '2026-10-22', to: '2026-11-22' })
    expect(resolvePeriodChoice('next2m', PRESETS)).toEqual({ from: '2026-10-22', to: '2026-12-22' })
    expect(resolvePeriodChoice('1m', PRESETS)).toEqual({ from: '2026-09-22', to: '2026-10-22' })
  })

  // 서버 응답에 없는 키는 undefined다.
  it('returns undefined when the server response lacks the key', () => {
    // given: 프리셋이 일부만 온 응답이다.
    const partial: UpdatedPeriods = { today: PRESETS.today, periods: [PRESETS.periods[0]!], upcoming: [PRESETS.upcoming[0]!] }

    // when·then: 없는 키는 undefined다.
    expect(resolvePeriodChoice('6m', partial)).toBeUndefined()
    expect(resolvePeriodChoice('next2m', partial)).toBeUndefined()
  })
})

describe('period labels', () => {
  // 지난 기간 프리셋의 화면 이름이 정해져 있다.
  it('names the past presets', () => {
    // when·then: 최근 2주~6개월 이름이다.
    expect(PAST_PERIOD_LABELS).toEqual({
      '2w': '최근 2주',
      '1m': '최근 1개월',
      '2m': '최근 2개월',
      '3m': '최근 3개월',
      '6m': '최근 6개월',
    })
  })

  // 향후 프리셋의 화면 이름이 정해져 있다.
  it('names the upcoming presets', () => {
    // when·then: 향후 1·2개월 이름이다.
    expect(UPCOMING_PERIOD_LABELS).toEqual({ '1m': '향후 1개월', '2m': '향후 2개월' })
  })
})
