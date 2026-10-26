import { describe, expect, it } from 'vitest'
import {
  FORECAST_KEYS_MAX,
  forecastParam,
  forecastSummary,
  parseForecastParam,
  toggleForecastParam,
} from './forecastKeys'
import { testCodes } from './testing'
import type { Code } from './types'

/** Forecast 다중 조건: URL `forecast` 값(콤마 구분)과 필터 버튼 요약 (AC-08·10·11·12). */

const keys = (n: number): string[] => Array.from({ length: n }, (_, i) => `k${i}`)

describe('parseForecastParam', () => {
  it.each([[null], ['']])('reads %j as no selection', (raw) => {
    expect(parseForecastParam(raw)).toEqual([])
  })

  it('reads an old single value', () => {
    expect(parseForecastParam('commit')).toEqual(['commit'])
  })

  it('sorts alphabetically', () => {
    expect(parseForecastParam('pipeline,best')).toEqual(['best', 'pipeline'])
  })

  it('drops duplicates, blanks and surrounding spaces', () => {
    expect(parseForecastParam(' best , best ,pipeline,')).toEqual(['best', 'pipeline'])
  })

  it('drops items whose format is wrong (upper case, bad characters, leading digit)', () => {
    expect(parseForecastParam('Commit,ok')).toEqual(['ok'])
    expect(parseForecastParam('XYZ')).toEqual([])
    expect(parseForecastParam('a-b,ok')).toEqual(['ok'])
    expect(parseForecastParam('1abc,ok')).toEqual(['ok'])
  })

  it('keeps a 50 character key and drops a 51 character key', () => {
    const fifty = 'a'.repeat(50)
    expect(parseForecastParam(fifty)).toEqual([fifty])
    expect(parseForecastParam(`${'a'.repeat(51)},ok`)).toEqual(['ok'])
  })

  it('keeps one hundred distinct keys and ignores the whole condition above that', () => {
    expect(FORECAST_KEYS_MAX).toBe(100)
    expect(parseForecastParam(keys(100).join(','))).toHaveLength(100)
    expect(parseForecastParam(keys(101).join(','))).toEqual([])
  })

  it('does not count duplicates towards the limit', () => {
    const raw = [...keys(100), ...keys(100)].join(',')
    expect(parseForecastParam(raw)).toHaveLength(100)
  })
})

describe('forecastParam', () => {
  it('joins sorted, de-duplicated keys with commas', () => {
    expect(forecastParam(['pipeline', 'best', 'best'])).toBe('best,pipeline')
  })

  it('is empty for no keys', () => {
    expect(forecastParam([])).toBe('')
  })
})

describe('toggleForecastParam', () => {
  it('adds a key in sorted position', () => {
    expect(toggleForecastParam('best', 'pipeline', true)).toBe('best,pipeline')
    expect(toggleForecastParam(null, 'pipeline', true)).toBe('pipeline')
  })

  it('removes a key', () => {
    expect(toggleForecastParam('best,pipeline', 'best', false)).toBe('pipeline')
  })

  it('becomes empty after the last key is switched off', () => {
    expect(toggleForecastParam('best', 'best', false)).toBe('')
  })

  it('does not change anything when the key is already on', () => {
    expect(toggleForecastParam('best,pipeline', 'best', true)).toBe('best,pipeline')
  })

  it('does not change anything when switching off a key that is not on', () => {
    expect(toggleForecastParam('best', 'pipeline', false)).toBe('best')
  })

  it('gives the same value whatever the order of switching on', () => {
    const a = toggleForecastParam(toggleForecastParam(null, 'best', true), 'pipeline', true)
    const b = toggleForecastParam(toggleForecastParam(null, 'pipeline', true), 'best', true)
    expect(a).toBe(b)
  })
})

describe('forecastSummary', () => {
  const base = testCodes().forecasts
  // admin이 추가한 Open 코드 하나
  const verbal: Code = { ...base[3]!, id: 999, key: 'verbal', name: 'Verbal', order: 7, outcome: 'open' }
  const codes: Code[] = [...base, verbal]
  const keysOf = (pick: (c: Code) => boolean) => codes.filter(pick).map((c) => c.key)

  it('says 전체 for no selection', () => {
    expect(forecastSummary([], codes)).toBe('전체')
  })

  it('shows the name of a single code, or the key when the code is unknown', () => {
    expect(forecastSummary(['best'], codes)).toBe('Best')
    expect(forecastSummary(['zzz'], codes)).toBe('zzz')
  })

  it('says 모두 선택 when every code including Lost is selected', () => {
    expect(forecastSummary(keysOf(() => true), codes)).toBe('모두 선택')
  })

  it('says Lost 제외 when exactly the non-lost codes are selected', () => {
    expect(forecastSummary(keysOf((c) => c.outcome !== 'lost'), codes)).toBe('Lost 제외')
  })

  it('says Open 전체 when exactly the open codes (including added ones) are selected', () => {
    expect(forecastSummary(keysOf((c) => c.outcome === 'open'), codes)).toBe('Open 전체')
  })

  it('does not say Open 전체 when an added open code is missing from the selection', () => {
    expect(forecastSummary(['pipeline', 'best', 'most_likely', 'commit'], codes)).toBe('4개 선택')
  })

  it('counts any other selection', () => {
    expect(forecastSummary(['best', 'lost'], codes)).toBe('2개 선택')
  })

  it('counts a selection of unknown keys as well', () => {
    expect(forecastSummary(['aaa', 'bbb'], codes)).toBe('2개 선택')
  })

  it('counts without names while the codes are not loaded', () => {
    expect(forecastSummary(['a', 'b', 'c'], undefined)).toBe('3개 선택')
    expect(forecastSummary([], undefined)).toBe('전체')
  })

  it('shows the name when the only open code is selected alone', () => {
    const onlyOne = codes.filter((c) => c.outcome !== 'open' || c.key === 'commit')
    expect(forecastSummary(['commit'], onlyOne)).toBe('Commit')
  })
})
