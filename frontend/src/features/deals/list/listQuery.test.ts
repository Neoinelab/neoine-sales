import { describe, expect, it } from 'vitest'
import { REMEMBERED_LIST_KEYS } from '../../../shared/model/dealListMemory'
import { FILTER_KEYS, currentSort, hasActiveFilter, listQueryFromParams, nextSort, updateParams } from './listQuery'

const params = (query: string) => new URLSearchParams(query)

describe('listQueryFromParams (T-LIST-05, T-LIST-09)', () => {
  it('returns only paging for empty params', () => {
    expect(listQueryFromParams(params(''))).toEqual({ offset: 0, limit: 20 })
  })

  it('maps every filter, sort and page from the URL', () => {
    const query = listQueryFromParams(
      params(
        'q=한빛&owner=u-kim&vendor=Okta&solution=SSO&status=prospecting&forecast=best&year=2026&quarter=4&from=2026-01-01&to=2026-12-31&budget=lb-1&need=lb-9&mine=1&sort=revenueAmount&order=asc&page=3',
      ),
    )
    expect(query).toEqual({
      keyword: '한빛',
      ownerId: 'u-kim',
      vendor: 'Okta',
      solution: 'SSO',
      statusKey: 'prospecting',
      forecastKey: 'best',
      year: 2026,
      quarter: 4,
      revenueFrom: '2026-01-01',
      revenueTo: '2026-12-31',
      bantLabelIds: { budget: 'lb-1', need: 'lb-9' },
      mine: true,
      sort: 'revenueAmount',
      order: 'asc',
      offset: 40,
      limit: 20,
    })
  })

  it('ignores broken values instead of failing', () => {
    const query = listQueryFromParams(params('year=abc&quarter=9&sort=bogus&order=up&page=0&mine=0&q=%20%20'))
    expect(query).toEqual({ offset: 0, limit: 20 })
    expect(listQueryFromParams(params('page=-3')).offset).toBe(0)
    expect(listQueryFromParams(params('page=x')).offset).toBe(0)
  })

  it('keeps a quarter only together with a year', () => {
    expect(listQueryFromParams(params('quarter=2'))).toEqual({ offset: 0, limit: 20 })
  })
})

describe('updateParams', () => {
  it('sets a value, drops empty ones and goes back to the first page', () => {
    const next = updateParams(params('q=a&page=3&vendor=Okta'), { vendor: '', status: 'best' })
    expect(next.get('vendor')).toBeNull()
    expect(next.get('status')).toBe('best')
    expect(next.get('q')).toBe('a')
    expect(next.get('page')).toBeNull()
  })

  it('keeps the page when only the page changes and omits page 1', () => {
    expect(updateParams(params('q=a'), { page: '2' }).get('page')).toBe('2')
    expect(updateParams(params('q=a&page=2'), { page: '1' }).get('page')).toBeNull()
  })
})

describe('hasActiveFilter', () => {
  it('is false for sort and page only', () => {
    expect(hasActiveFilter(params('sort=name&order=asc&page=2'))).toBe(false)
  })
  it('is true for any condition including mine', () => {
    expect(hasActiveFilter(params('mine=1'))).toBe(true)
    expect(hasActiveFilter(params('budget=lb-1'))).toBe(true)
    expect(hasActiveFilter(params('q=a'))).toBe(true)
  })
})

describe('sorting', () => {
  it('defaults to the latest update first', () => {
    expect(currentSort(params(''))).toEqual({ sort: 'lastUpdatedAt', order: 'desc' })
  })

  it('starts a new column in its natural direction and flips it on the second click', () => {
    expect(nextSort({ sort: 'lastUpdatedAt', order: 'desc' }, 'revenueDate')).toEqual({ sort: 'revenueDate', order: 'asc' })
    expect(nextSort({ sort: 'revenueDate', order: 'asc' }, 'revenueDate')).toEqual({ sort: 'revenueDate', order: 'desc' })
    expect(nextSort({ sort: 'name', order: 'asc' }, 'revenueAmount')).toEqual({ sort: 'revenueAmount', order: 'desc' })
  })
})

describe('목록 조건 기억 키 (DL-06)', () => {
  it('remembered keys equal filter keys plus sort order page', () => {
    expect([...REMEMBERED_LIST_KEYS].sort()).toEqual([...FILTER_KEYS, 'sort', 'order', 'page'].sort())
  })
})
