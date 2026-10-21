import { describe, expect, it } from 'vitest'
import { filtersFromParams, paramsFromFilters, queryOf } from './forecastParams'

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
