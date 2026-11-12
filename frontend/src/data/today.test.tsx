import { renderHook } from '@testing-library/react'
import { afterEach, describe, expect, it } from 'vitest'
import { resetMock } from '../test/fake/default'
import { useToday } from './today'

afterEach(() => resetMock({ now: null }))

describe('useToday', () => {
  // useToday는 앱 시계의 지금·오늘·연도를 읽는다.
  // 테스트 코드: TM-037
  it('returns the mock clock now, its calendar date and year', () => {
    // given: 앱 시계가 2030-12-31T23:30:00+09:00이다
    resetMock({ now: '2030-12-31T23:30:00+09:00' })
    // when: useToday를 렌더한다
    const { result } = renderHook(() => useToday())
    // then: now·today·year가 시계 값이다
    expect(result.current).toEqual({ now: '2030-12-31T23:30:00+09:00', today: '2030-12-31', year: 2030 })
  })

  // 렌더마다 앱 시계를 다시 읽는다.
  // 테스트 코드: TM-037
  it('follows the clock when it is changed between renders', () => {
    // given: 앱 시계가 2027-01-01이다
    resetMock({ now: '2027-01-01T00:10:00+09:00' })
    const { result, rerender } = renderHook(() => useToday())
    expect(result.current.today).toBe('2027-01-01')
    // when: 시계를 2028-05-06으로 바꾸고 다시 렌더한다
    resetMock({ now: '2028-05-06T10:00:00+09:00' })
    rerender()
    // then: today와 year가 바뀐다
    expect(result.current).toMatchObject({ today: '2028-05-06', year: 2028 })
  })
})
