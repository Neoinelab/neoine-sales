import { renderHook } from '@testing-library/react'
import { afterEach, describe, expect, it } from 'vitest'
import { resetMock } from '../test/fake/default'
import { useToday } from './today'

afterEach(() => resetMock({ now: null }))

describe('useToday', () => {
  it('returns the mock clock now, its calendar date and year', () => {
    resetMock({ now: '2030-12-31T23:30:00+09:00' })
    const { result } = renderHook(() => useToday())
    expect(result.current).toEqual({ now: '2030-12-31T23:30:00+09:00', today: '2030-12-31', year: 2030 })
  })

  it('follows the clock when it is changed between renders', () => {
    resetMock({ now: '2027-01-01T00:10:00+09:00' })
    const { result, rerender } = renderHook(() => useToday())
    expect(result.current.today).toBe('2027-01-01')
    resetMock({ now: '2028-05-06T10:00:00+09:00' })
    rerender()
    expect(result.current).toMatchObject({ today: '2028-05-06', year: 2028 })
  })
})
