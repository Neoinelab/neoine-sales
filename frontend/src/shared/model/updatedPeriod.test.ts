import { describe, expect, it } from 'vitest'
import { selectedUpdatedPeriod } from './updatedPeriod'
import type { UpdatedPeriods } from './types'

const PERIODS: UpdatedPeriods['periods'] = [
  { key: '2w', from: '2026-10-07', to: '2026-10-21' },
  { key: '1m', from: '2026-09-21', to: '2026-10-21' },
  { key: '2m', from: '2026-08-21', to: '2026-10-21' },
  { key: '3m', from: '2026-07-21', to: '2026-10-21' },
  { key: '6m', from: '2026-04-21', to: '2026-10-21' },
]

describe('selectedUpdatedPeriod', () => {
  it('URL에 날짜가 없으면 전체(빈 값)를 선택한다', () => {
    // when: 날짜 없이 선택된 기간을 구한다 (기간 목록 있음·없음)
    const result1 = selectedUpdatedPeriod(undefined, undefined, PERIODS)
    const result2 = selectedUpdatedPeriod(undefined, undefined, undefined)

    // then: 둘 다 빈 문자열이다
    expect(result1).toBe('')
    expect(result2).toBe('')
  })

  it.each(PERIODS)('날짜가 정확히 맞는 $key 프리셋을 선택한다', ({ key, from, to }) => {
    // when: 프리셋의 시작·끝 날짜로 선택된 기간을 구한다
    const result = selectedUpdatedPeriod(from, to, PERIODS)

    // then: 그 프리셋의 키다
    expect(result).toBe(key)
  })

  it('한쪽 날짜만 있으면 직접 지정으로 본다', () => {
    // when: 시작만, 끝만 있는 경우의 선택된 기간을 구한다
    const result1 = selectedUpdatedPeriod('2026-10-07', undefined, PERIODS)
    const result2 = selectedUpdatedPeriod(undefined, '2026-10-21', PERIODS)

    // then: 둘 다 custom이다
    expect(result1).toBe('custom')
    expect(result2).toBe('custom')
  })

  it('날짜가 하루라도 다르면 직접 지정으로 본다', () => {
    // when: 프리셋과 하루씩 어긋난 날짜로 선택된 기간을 구한다
    const result1 = selectedUpdatedPeriod('2026-10-08', '2026-10-21', PERIODS)
    const result2 = selectedUpdatedPeriod('2026-10-07', '2026-10-20', PERIODS)
    const result3 = selectedUpdatedPeriod('2026-10-06', '2026-10-20', PERIODS)

    // then: 모두 custom이다
    expect(result1).toBe('custom')
    expect(result2).toBe('custom')
    expect(result3).toBe('custom')
  })

  it('프리셋을 모르는 동안(불러오는 중·실패) 날짜가 있으면 직접 지정으로 본다', () => {
    // when: 기간 목록 없이 날짜가 있는 경우의 선택된 기간을 구한다
    const result1 = selectedUpdatedPeriod('2026-10-07', '2026-10-21', undefined)
    const result2 = selectedUpdatedPeriod('2026-10-07', undefined, undefined)
    const result3 = selectedUpdatedPeriod(undefined, '2026-10-21', undefined)

    // then: 모두 custom이다
    expect(result1).toBe('custom')
    expect(result2).toBe('custom')
    expect(result3).toBe('custom')
  })
})

describe('isUpcomingKey', () => {
  it('다가오는 기간의 키만 받아들인다', async () => {
    const { isUpcomingKey } = await import('./updatedPeriod')

    // when: 키마다 다가오는 기간 키인지 판정한다
    const result1 = isUpcomingKey('1m')
    const result2 = isUpcomingKey('2m')
    const result3 = isUpcomingKey('2w')
    const result4 = isUpcomingKey('3m')
    const result5 = isUpcomingKey('')

    // then: 1m·2m만 true이고 2w·3m·빈 값은 false다
    expect(result1).toBe(true)
    expect(result2).toBe(true)
    expect(result3).toBe(false)
    expect(result4).toBe(false)
    expect(result5).toBe(false)
  })
})
