import { describe, expect, it } from 'vitest'
import { filtersFromParams, paramsFromFilters, queryOf, selectedQuarterOf } from './dashboardParams'

const params = (query: string) => new URLSearchParams(query)

describe('filtersFromParams defaults (AC-10·11)', () => {
  it('starts on the status tab with this year and no other condition', () => {
    expect(filtersFromParams(params(''), 2026)).toEqual({ tab: 'status', year: 2026 })
  })

  it('uses the fallback year the caller gives (this year of the app clock)', () => {
    expect(filtersFromParams(params(''), 2031).year).toBe(2031)
  })

  it('reads every condition from the URL', () => {
    const filters = filtersFromParams(params('tab=forecast&year=2025&quarter=3&owner=7&vendor=12'), 2026)

    expect(filters).toEqual({ tab: 'forecast', year: 2025, quarter: 3, ownerId: 7, vendor: 12 })
  })
})

describe('filtersFromParams ignores broken values', () => {
  it.each(['', 'Forecast', 'FORECAST', 'status ', 'reports', '1'])('shows the status tab for the unknown tab %j', (raw) => {
    expect(filtersFromParams(params(`tab=${encodeURIComponent(raw)}`), 2026).tab).toBe('status')
  })

  it.each(['abc', '', '26', '20266', '-2026', '2026.5', '0'])('falls back to this year for the year %j', (raw) => {
    expect(filtersFromParams(params(`year=${encodeURIComponent(raw)}`), 2026).year).toBe(2026)
  })

  it.each(['0', '5', '-1', '1.5', 'abc', '', '01'])('ignores the quarter %j', (raw) => {
    expect(filtersFromParams(params(`quarter=${encodeURIComponent(raw)}`), 2026).quarter).toBeUndefined()
  })

  it.each(['1', '2', '3', '4'])('accepts the quarter %s', (raw) => {
    expect(filtersFromParams(params(`quarter=${raw}`), 2026).quarter).toBe(Number(raw))
  })

  it.each(['0', '-1', '1.5', '1e3', '01', '+3', 'abc', '', '9007199254740992', 'u-kim', '10000000-0000-4000-8000-000000000003'])(
    'ignores the owner and vendor %j',
    (raw) => {
      const encoded = encodeURIComponent(raw)
      const filters = filtersFromParams(params(`owner=${encoded}&vendor=${encoded}`), 2026)

      expect(filters.ownerId).toBeUndefined()
      expect(filters.vendor).toBeUndefined()
    },
  )

  it('accepts the largest safe integer as an id', () => {
    expect(filtersFromParams(params('owner=9007199254740991&vendor=9007199254740991'), 2026)).toMatchObject({
      ownerId: 9007199254740991,
      vendor: 9007199254740991,
    })
  })

  it('does not read month, snapshot or selection keys of the Forecast screen', () => {
    const filters = filtersFromParams(params('year=2026&month=3&snap=2026-09&sel=5'), 2026)

    expect(filters).toEqual({ tab: 'status', year: 2026 })
  })
})

describe('paramsFromFilters', () => {
  it('always writes the tab and the year, even for the defaults', () => {
    expect(paramsFromFilters({ tab: 'status', year: 2026 }).toString()).toBe('tab=status&year=2026')
  })

  it('writes every condition in a fixed order as plain decimal text', () => {
    const next = paramsFromFilters({ tab: 'forecast', year: 2026, quarter: 4, ownerId: 2, vendor: 12 })

    expect(next.toString()).toBe('tab=forecast&year=2026&quarter=4&owner=2&vendor=12')
  })

  it('leaves out the conditions that are not set', () => {
    const next = paramsFromFilters({ tab: 'status', year: 2026, ownerId: 2 })

    expect(next.has('quarter')).toBe(false)
    expect(next.has('vendor')).toBe(false)
    expect(next.toString()).toBe('tab=status&year=2026&owner=2')
  })

  it('round-trips through filtersFromParams', () => {
    const filters = { tab: 'forecast', year: 2027, quarter: 1, ownerId: 5, vendor: 9 } as const

    expect(filtersFromParams(paramsFromFilters(filters), 2026)).toEqual(filters)
  })
})

describe('queryOf', () => {
  it('sends only the year when nothing else is chosen (the tab is not a query condition)', () => {
    expect(queryOf({ tab: 'forecast', year: 2026 })).toEqual({ year: 2026 })
  })

  it('maps quarter, owner and vendor to the gateway query on the status tab', () => {
    expect(queryOf({ tab: 'status', year: 2026, quarter: 4, ownerId: 2, vendor: 12 })).toEqual({
      year: 2026,
      quarter: 4,
      ownerId: 2,
      vendorId: 12,
    })
  })

  it('keeps ids as numbers', () => {
    const query = queryOf({ tab: 'status', year: 2026, ownerId: 2, vendor: 12 })

    expect(typeof query.ownerId).toBe('number')
    expect(typeof query.vendorId).toBe('number')
  })
})

describe('sq (Forecast 탭의 Selected Quarter, AC3·4·7)', () => {
  it.each(['1', '2', '3', '4'])('reads the selected quarter %s', (raw) => {
    expect(filtersFromParams(params(`sq=${raw}`), 2026).selectedQuarter).toBe(Number(raw))
  })

  it.each(['0', '5', '-1', '1.5', 'abc', '', '01', ' 2'])('ignores the broken sq %j', (raw) => {
    expect(filtersFromParams(params(`sq=${encodeURIComponent(raw)}`), 2026).selectedQuarter).toBeUndefined()
  })

  it('keeps sq apart from the quarter filter', () => {
    expect(filtersFromParams(params('tab=forecast&year=2026&quarter=1&sq=3'), 2026)).toEqual({ tab: 'forecast', year: 2026, quarter: 1, selectedQuarter: 3 })
  })

  it('does not set selectedQuarter when sq is absent (the default is resolved with the date)', () => {
    expect(filtersFromParams(params('tab=forecast&year=2026'), 2026)).toEqual({ tab: 'forecast', year: 2026 })
  })

  it('writes sq after quarter and before owner, only when set', () => {
    const next = paramsFromFilters({ tab: 'forecast', year: 2026, quarter: 3, selectedQuarter: 2, ownerId: 2, vendor: 12 })

    expect(next.toString()).toBe('tab=forecast&year=2026&quarter=3&sq=2&owner=2&vendor=12')
    expect(paramsFromFilters({ tab: 'forecast', year: 2026 }).has('sq')).toBe(false)
  })

  it('round-trips sq through filtersFromParams', () => {
    const filters = { tab: 'forecast', year: 2027, quarter: 1, selectedQuarter: 4, ownerId: 5, vendor: 9 } as const

    expect(filtersFromParams(paramsFromFilters(filters), 2026)).toEqual(filters)
  })

  it('never sends sq to the server', () => {
    expect(queryOf({ tab: 'forecast', year: 2026, selectedQuarter: 3 })).toEqual({ year: 2026 })
    expect(queryOf({ tab: 'status', year: 2026, selectedQuarter: 3 })).toEqual({ year: 2026 })
  })
})

describe('queryOf on the Forecast tab (AC2)', () => {
  it('leaves out quarter but keeps owner and vendor', () => {
    expect(queryOf({ tab: 'forecast', year: 2026, quarter: 4, ownerId: 2, vendor: 12 })).toEqual({ year: 2026, ownerId: 2, vendorId: 12 })
  })
})

describe('selectedQuarterOf (AC4)', () => {
  it('uses the explicit sq first', () => {
    expect(selectedQuarterOf({ tab: 'forecast', year: 2026, selectedQuarter: 2 }, '2026-11-05')).toBe(2)
  })

  it.each([
    ['2026-01-01', 1],
    ['2026-03-31', 1],
    ['2026-04-01', 2],
    ['2026-06-30', 2],
    ['2026-07-01', 3],
    ['2026-09-30', 3],
    ['2026-10-01', 4],
    ['2026-12-31', 4],
  ])('uses the quarter of today %s for this year (Q%i)', (today, quarter) => {
    expect(selectedQuarterOf({ tab: 'forecast', year: 2026 }, today)).toBe(quarter)
  })

  it.each([2025, 2027])('uses Q1 for another year %i', (year) => {
    expect(selectedQuarterOf({ tab: 'forecast', year }, '2026-11-05')).toBe(1)
  })

  it('ignores the quarter filter', () => {
    expect(selectedQuarterOf({ tab: 'forecast', year: 2026, quarter: 1 }, '2026-11-05')).toBe(4)
  })
})
