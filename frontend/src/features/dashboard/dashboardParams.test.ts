import { describe, expect, it } from 'vitest'
import { activeFilters, filtersFromParams, paramsFromFilters, patchActive, queryOf, type DashboardFilters } from './dashboardParams'

const params = (query: string) => new URLSearchParams(query)

const DEFAULTS = { year: 2026, quarters: [] }

describe('filtersFromParams defaults (AC-31·33)', () => {
  it('starts on the status tab with this year and no other condition on both tabs', () => {
    expect(filtersFromParams(params(''), 2026)).toEqual({ tab: 'status', status: DEFAULTS, forecast: DEFAULTS })
  })

  it('uses the fallback year the caller gives (this year of the app clock) on both tabs', () => {
    const filters = filtersFromParams(params(''), 2031)

    expect(filters.status.year).toBe(2031)
    expect(filters.forecast.year).toBe(2031)
  })

  it('reads the tab from the URL', () => {
    expect(filtersFromParams(params('tab=forecast'), 2026).tab).toBe('forecast')
  })
})

describe('filtersFromParams reads both tabs apart (AC-30·32)', () => {
  it('reads each tab from its own prefixed keys', () => {
    const filters = filtersFromParams(params('tab=forecast&status.year=2025&status.quarter=1%2C3&forecast.year=2026&forecast.owner=7'), 2026)

    expect(filters).toEqual({
      tab: 'forecast',
      status: { year: 2025, quarters: [1, 3] },
      forecast: { year: 2026, quarters: [], ownerId: 7 },
    })
  })

  it('reads owner, vendor and quarter of each tab independently', () => {
    const filters = filtersFromParams(
      params('tab=status&status.year=2025&status.quarter=2&status.owner=3&status.vendor=4&forecast.year=2027&forecast.quarter=4&forecast.owner=8&forecast.vendor=9'),
      2026,
    )

    expect(filters.status).toEqual({ year: 2025, quarters: [2], ownerId: 3, vendor: 4 })
    expect(filters.forecast).toEqual({ year: 2027, quarters: [4], ownerId: 8, vendor: 9 })
  })

  it('keeps all four quarters the user pressed (U6) in the filter state', () => {
    expect(filtersFromParams(params('status.quarter=1%2C2%2C3%2C4'), 2026).status.quarters).toEqual([1, 2, 3, 4])
  })

  it('sorts quarters ascending and drops duplicates', () => {
    expect(filtersFromParams(params('forecast.quarter=3%2C1%2C1'), 2026).forecast.quarters).toEqual([1, 3])
  })

  it('does not read a tab condition from the other tab keys', () => {
    const filters = filtersFromParams(params('status.owner=7&forecast.vendor=3'), 2026)

    expect(filters.status).toEqual({ ...DEFAULTS, ownerId: 7 })
    expect(filters.forecast).toEqual({ ...DEFAULTS, vendor: 3 })
  })
})

describe('filtersFromParams ignores broken values', () => {
  it.each(['', 'Forecast', 'FORECAST', 'status ', 'reports', '1'])('shows the status tab for the unknown tab %j', (raw) => {
    expect(filtersFromParams(params(`tab=${encodeURIComponent(raw)}`), 2026).tab).toBe('status')
  })

  it.each(['abc', '', '26', '20266', '-2026', '2026.5', '0'])('falls back to this year for the year %j', (raw) => {
    const filters = filtersFromParams(params(`status.year=${encodeURIComponent(raw)}&forecast.year=${encodeURIComponent(raw)}`), 2026)

    expect(filters.status.year).toBe(2026)
    expect(filters.forecast.year).toBe(2026)
  })

  it.each([
    ['5', []],
    ['x', []],
    ['0', []],
    ['1,5', [1]],
    ['x,2', [2]],
    ['', []],
  ])('keeps only the valid quarters of %j', (raw, expected) => {
    expect(filtersFromParams(params(`status.quarter=${encodeURIComponent(raw)}`), 2026).status.quarters).toEqual(expected)
  })

  it.each(['0', '-1', '1.5', '1e3', '01', '+3', 'abc', '', '9007199254740992', 'u-kim', '10000000-0000-4000-8000-000000000003'])(
    'ignores the owner and vendor %j',
    (raw) => {
      const encoded = encodeURIComponent(raw)
      const filters = filtersFromParams(params(`status.owner=${encoded}&status.vendor=${encoded}&forecast.owner=${encoded}&forecast.vendor=${encoded}`), 2026)

      expect(filters.status.ownerId).toBeUndefined()
      expect(filters.status.vendor).toBeUndefined()
      expect(filters.forecast.ownerId).toBeUndefined()
      expect(filters.forecast.vendor).toBeUndefined()
    },
  )

  it('accepts the largest safe integer as an id', () => {
    const filters = filtersFromParams(params('status.owner=9007199254740991&forecast.vendor=9007199254740991'), 2026)

    expect(filters.status.ownerId).toBe(9007199254740991)
    expect(filters.forecast.vendor).toBe(9007199254740991)
  })

  it('does not read month, snapshot or selection keys of the Forecast screen', () => {
    const filters = filtersFromParams(params('status.year=2026&month=3&snap=2026-09&sel=5'), 2026)

    expect(filters).toEqual({ tab: 'status', status: DEFAULTS, forecast: DEFAULTS })
  })
})

describe('paramsFromFilters (AC-32)', () => {
  it('always writes the tab and both years, even for the defaults', () => {
    const filters: DashboardFilters = { tab: 'status', status: DEFAULTS, forecast: DEFAULTS }

    expect(paramsFromFilters(filters).toString()).toBe('tab=status&status.year=2026&forecast.year=2026')
  })

  it('writes both tabs conditions in a fixed order as plain decimal text', () => {
    const next = paramsFromFilters({
      tab: 'forecast',
      status: { year: 2025, quarters: [1, 3], ownerId: 2, vendor: 12 },
      forecast: { year: 2026, quarters: [4], ownerId: 5, vendor: 9 },
    })

    expect(next.toString()).toBe(
      'tab=forecast&status.year=2025&status.quarter=1%2C3&status.owner=2&status.vendor=12&forecast.year=2026&forecast.quarter=4&forecast.owner=5&forecast.vendor=9',
    )
  })

  it('leaves out the conditions that are not set', () => {
    const next = paramsFromFilters({ tab: 'status', status: { year: 2026, quarters: [], ownerId: 2 }, forecast: DEFAULTS })

    expect(next.has('status.quarter')).toBe(false)
    expect(next.has('status.vendor')).toBe(false)
    expect(next.has('forecast.owner')).toBe(false)
    expect(next.toString()).toBe('tab=status&status.year=2026&status.owner=2&forecast.year=2026')
  })

  it('writes all four quarters when the user pressed all four (U6)', () => {
    const next = paramsFromFilters({ tab: 'status', status: { year: 2026, quarters: [1, 2, 3, 4] }, forecast: DEFAULTS })

    expect(next.get('status.quarter')).toBe('1,2,3,4')
    expect(next.toString()).toContain('status.quarter=1%2C2%2C3%2C4')
  })

  it('never writes the old shared keys or sq', () => {
    const next = paramsFromFilters({ tab: 'forecast', status: { year: 2025, quarters: [2], ownerId: 7, vendor: 3 }, forecast: { year: 2025, quarters: [], ownerId: 7, vendor: 3 } })

    for (const key of ['year', 'quarter', 'owner', 'vendor', 'sq']) expect(next.has(key)).toBe(false)
  })

  it('round-trips through filtersFromParams', () => {
    const filters: DashboardFilters = {
      tab: 'forecast',
      status: { year: 2027, quarters: [1, 2, 3, 4], ownerId: 5, vendor: 9 },
      forecast: { year: 2025, quarters: [2, 4], vendor: 1 },
    }

    expect(filtersFromParams(paramsFromFilters(filters), 2026)).toEqual(filters)
  })
})

describe('old shared addresses still open (AC-34)', () => {
  const OLD = 'tab=forecast&year=2025&quarter=2&owner=7&vendor=3&sq=3'

  it('reads the old year, owner and vendor into both tabs and the old quarter into the status tab only', () => {
    const filters = filtersFromParams(params(OLD), 2026)

    expect(filters.tab).toBe('forecast')
    expect(filters.status).toEqual({ year: 2025, quarters: [2], ownerId: 7, vendor: 3 })
    expect(filters.forecast).toEqual({ year: 2025, quarters: [], ownerId: 7, vendor: 3 })
  })

  it('reads the example from the plan: owner 7 on both tabs, quarter only on the status tab', () => {
    const filters = filtersFromParams(params('tab=forecast&year=2025&quarter=2&owner=7&sq=3'), 2026)

    expect(filters.forecast).toEqual({ year: 2025, quarters: [], ownerId: 7 })
    expect(filters.status).toEqual({ year: 2025, quarters: [2], ownerId: 7 })
  })

  it('ignores sq', () => {
    expect(filtersFromParams(params('sq=3'), 2026)).toEqual({ tab: 'status', status: DEFAULTS, forecast: DEFAULTS })
  })

  it('writes only prefixed keys when the old address is written back', () => {
    const next = paramsFromFilters(filtersFromParams(params(OLD), 2026))

    for (const key of ['year', 'quarter', 'owner', 'vendor', 'sq']) expect(next.has(key)).toBe(false)
    expect(next.get('status.quarter')).toBe('2')
    expect(next.get('forecast.owner')).toBe('7')
    expect(next.has('forecast.quarter')).toBe(false)
  })

  it('prefers the prefixed key of the same tab over the old key', () => {
    const filters = filtersFromParams(params('year=2025&owner=7&forecast.year=2027&forecast.owner=8'), 2026)

    expect(filters.forecast).toMatchObject({ year: 2027, ownerId: 8 })
    expect(filters.status).toMatchObject({ year: 2025, ownerId: 7 })
  })

  it('does not fall back to the old key when the prefixed value is broken', () => {
    const filters = filtersFromParams(params('year=2025&owner=7&status.year=abc&status.owner=0'), 2026)

    expect(filters.status.year).toBe(2026)
    expect(filters.status.ownerId).toBeUndefined()
    expect(filters.forecast).toMatchObject({ year: 2025, ownerId: 7 })
  })

  it('prefers the prefixed quarter of the status tab over the old quarter', () => {
    expect(filtersFromParams(params('quarter=2&status.quarter=4'), 2026).status.quarters).toEqual([4])
  })
})

describe('activeFilters and patchActive (AC-30)', () => {
  const FILTERS: DashboardFilters = {
    tab: 'status',
    status: { year: 2025, quarters: [2], ownerId: 7 },
    forecast: { year: 2026, quarters: [], vendor: 3 },
  }

  it('returns the conditions of the active tab', () => {
    expect(activeFilters(FILTERS)).toEqual(FILTERS.status)
    expect(activeFilters({ ...FILTERS, tab: 'forecast' })).toEqual(FILTERS.forecast)
  })

  it('patches the active tab only and leaves the other tab alone', () => {
    const next = patchActive(FILTERS, { quarters: [1, 3], ownerId: undefined })

    expect(next.status).toEqual({ year: 2025, quarters: [1, 3] })
    expect(next.forecast).toEqual(FILTERS.forecast)
    expect(next.tab).toBe('status')
  })

  it('patches the forecast tab when it is active', () => {
    const next = patchActive({ ...FILTERS, tab: 'forecast' }, { year: 2024 })

    expect(next.forecast).toEqual({ year: 2024, quarters: [], vendor: 3 })
    expect(next.status).toEqual(FILTERS.status)
  })

  it('does not mutate the filters it is given', () => {
    patchActive(FILTERS, { year: 2020 })

    expect(FILTERS.status.year).toBe(2025)
  })
})

describe('queryOf (AC-14)', () => {
  it('sends only the year when nothing else is chosen', () => {
    expect(queryOf({ year: 2026, quarters: [] })).toEqual({ year: 2026 })
  })

  it('maps quarters, owner and vendor to the gateway query', () => {
    expect(queryOf({ year: 2026, quarters: [1, 3], ownerId: 2, vendor: 12 })).toEqual({ year: 2026, quarters: [1, 3], ownerId: 2, vendorId: 12 })
  })

  it('sends no quarters for all four quarters (same as none)', () => {
    expect(queryOf({ year: 2026, quarters: [1, 2, 3, 4] })).toEqual({ year: 2026 })
    expect(queryOf({ year: 2026, quarters: [1, 2, 3, 4] })).not.toHaveProperty('quarters')
  })

  it('keeps ids as numbers', () => {
    const query = queryOf({ year: 2026, quarters: [], ownerId: 2, vendor: 12 })

    expect(typeof query.ownerId).toBe('number')
    expect(typeof query.vendorId).toBe('number')
  })

  it('never sends the old single quarter key', () => {
    expect(queryOf({ year: 2026, quarters: [2] })).not.toHaveProperty('quarter')
  })
})
