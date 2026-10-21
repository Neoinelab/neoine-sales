import { describe, expect, it } from 'vitest'
import { filtersFromParams, paramsFromFilters, periodLabel, queryOf } from './forecastParams'

const params = (query: string) => new URLSearchParams(query)

describe('filtersFromParams ids', () => {
  it('reads integer vendor, owner and selected ids', () => {
    const filters = filtersFromParams(params('year=2026&owner=2&vendor=12&sel=5'), 2026)

    expect(filters).toMatchObject({ year: 2026, ownerId: 2, vendor: 12, selectedId: 5 })
  })

  it('ignores uuid and name values for the vendor', () => {
    expect(filtersFromParams(params('vendor=Okta'), 2026).vendor).toBeUndefined()
    expect(filtersFromParams(params('vendor=10000000-0000-4000-8000-000000000003'), 2026).vendor).toBeUndefined()
  })

  it('ignores an old user key in the owner and selection parameters', () => {
    const filters = filtersFromParams(params('owner=u-kim&sel=u-park'), 2026)

    expect(filters.ownerId).toBeUndefined()
    expect(filters.selectedId).toBeUndefined()
  })

  it.each(['0', '-1', '1.5', '1e3', '01', '+3', '9007199254740992'])('ignores the out-of-range or non-integer id %j', (raw) => {
    const encoded = encodeURIComponent(raw)
    const filters = filtersFromParams(params(`owner=${encoded}&vendor=${encoded}&sel=${encoded}`), 2026)

    expect(filters.ownerId).toBeUndefined()
    expect(filters.vendor).toBeUndefined()
    expect(filters.selectedId).toBeUndefined()
  })

  it('accepts the largest safe integer as an id', () => {
    expect(filtersFromParams(params('vendor=9007199254740991'), 2026).vendor).toBe(9007199254740991)
  })
})

describe('paramsFromFilters and queryOf ids', () => {
  it('writes ids into the URL as plain decimal text', () => {
    const next = paramsFromFilters({ year: 2026, quarter: 4, ownerId: 2, vendor: 12, selectedId: 5 })

    expect(next.toString()).toBe('year=2026&quarter=4&owner=2&vendor=12&sel=5')
  })

  it('keeps ids as numbers in the summary query and leaves the selection out', () => {
    const query = queryOf({ year: 2026, ownerId: 2, vendor: 12, selectedId: 5 })

    expect(query).toEqual({ year: 2026, vendorId: 12, ownerId: 2 })
  })
})

describe('month (P6 AC-3·8)', () => {
  it('reads a month from the URL', () => {
    expect(filtersFromParams(params('year=2026&month=3'), 2026)).toMatchObject({ year: 2026, month: 3 })
  })

  it.each(['0', '13', '-1', '1.5', 'abc', '03', ''])('ignores the invalid month %j', (raw) => {
    expect(filtersFromParams(params(`year=2026&month=${raw}`), 2026).month).toBeUndefined()
  })

  it.each(['1', '12'])('accepts the boundary month %s', (raw) => {
    expect(filtersFromParams(params(`year=2026&month=${raw}`), 2026).month).toBe(Number(raw))
  })

  it('keeps the quarter and drops the month when both are in the URL', () => {
    const filters = filtersFromParams(params('year=2026&quarter=4&month=11'), 2026)

    expect(filters.quarter).toBe(4)
    expect(filters.month).toBeUndefined()
  })

  it('writes the month into the URL and never together with a quarter', () => {
    expect(paramsFromFilters({ year: 2026, month: 3 }).toString()).toBe('year=2026&month=3')
    expect(paramsFromFilters({ year: 2026, quarter: 4, month: 3 }).has('month')).toBe(false)
  })

  it('puts the month in the summary query and leaves the quarter out', () => {
    expect(queryOf({ year: 2026, month: 3, ownerId: 2 })).toEqual({ year: 2026, month: 3, ownerId: 2 })
  })

  it('labels the period with the month, the quarter or the whole year', () => {
    expect(periodLabel({ year: 2026, month: 3 })).toBe('2026 3월')
    expect(periodLabel({ year: 2026, quarter: 4 })).toBe('2026 Q4')
    expect(periodLabel({ year: 2026 })).toBe('2026 전체')
  })
})

describe('기준 시점(snap) URL 파라미터 (P6 R2 AC-18)', () => {
  it('reads a YYYY-MM snapshot period', () => {
    expect(filtersFromParams(params('year=2026&snap=2026-09'), 2026).snap).toBe('2026-09')
  })

  it('has no snapshot by default', () => {
    expect(filtersFromParams(params('year=2026'), 2026).snap).toBeUndefined()
  })

  it.each(['', '2026-9', '2026-13', '2026-00', '202609', '2026/09', ' 2026-09', 'abc', '2026-09-01'])(
    'ignores the malformed snapshot period %j',
    (raw) => {
      expect(filtersFromParams(params(`year=2026&snap=${encodeURIComponent(raw)}`), 2026).snap).toBeUndefined()
    },
  )

  it('writes the snapshot period into the URL next to the other filters', () => {
    const written = paramsFromFilters({ year: 2026, quarter: 3, ownerId: 2, snap: '2026-09' })

    expect(Object.fromEntries(written)).toEqual({ year: '2026', quarter: '3', owner: '2', snap: '2026-09' })
  })

  it('leaves snap out of the URL when it is not chosen', () => {
    expect(paramsFromFilters({ year: 2026 }).has('snap')).toBe(false)
  })

  it('round-trips through the URL', () => {
    const filters = { year: 2026, month: 8, ownerId: 3, selectedId: 3, snap: '2026-09' }

    expect(filtersFromParams(paramsFromFilters(filters), 2000)).toEqual({ ...filters, quarter: undefined, vendor: undefined })
  })

  it('does not make the snapshot period part of the summary query', () => {
    expect(queryOf({ year: 2026, quarter: 3, snap: '2026-09' })).toEqual({ year: 2026, quarter: 3 })
  })
})
