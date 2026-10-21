import { describe, expect, it } from 'vitest'
import { REMEMBERED_LIST_KEYS } from '../../../shared/model/dealListMemory'
import { FILTER_KEYS, currentSort, hasActiveFilter, listQueryFromParams, nextSort, updateParams } from './listQuery'
import { USER_ID } from '../../../test/fake/seed/ids'

const params = (query: string) => new URLSearchParams(query)

const VENDOR = 3
const SOLUTION = 12

describe('listQueryFromParams (T-LIST-05, T-LIST-09)', () => {
  it('returns only paging for empty params', () => {
    expect(listQueryFromParams(params(''))).toEqual({ offset: 0, limit: 20 })
  })

  it('maps every filter, sort and page from the URL', () => {
    const query = listQueryFromParams(
      params(
        `q=한빛&owner=${USER_ID.kim}&vendor=${VENDOR}&solution=${SOLUTION}&status=prospecting&forecast=best&year=2026&quarter=4&updated_from=2026-01-01&updated_to=2026-12-31&budget=1&need=9&mine=1&sort=revenueAmount&order=asc&page=3`,
      ),
    )
    expect(query).toEqual({
      keyword: '한빛',
      ownerId: USER_ID.kim,
      vendorId: VENDOR,
      solutionId: SOLUTION,
      statusKey: 'prospecting',
      forecastKey: 'best',
      year: 2026,
      quarter: 4,
      updatedFrom: '2026-01-01',
      updatedTo: '2026-12-31',
      bantLabelIds: { budget: 1, need: 9 },
      mine: true,
      sort: 'revenueAmount',
      order: 'asc',
      offset: 40,
      limit: 20,
    })
  })

  it('maps a single updated date and sends a reversed range as it is (the server answers 422)', () => {
    expect(listQueryFromParams(params('updated_from=2026-06-01'))).toEqual({ offset: 0, limit: 20, updatedFrom: '2026-06-01' })
    expect(listQueryFromParams(params('updated_to=2026-06-30'))).toEqual({ offset: 0, limit: 20, updatedTo: '2026-06-30' })
    expect(listQueryFromParams(params('updated_from=2026-07-01&updated_to=2026-06-30'))).toEqual({
      offset: 0,
      limit: 20,
      updatedFrom: '2026-07-01',
      updatedTo: '2026-06-30',
    })
  })

  it.each(['abc', '2026/06/01', '2026-6-1', '2026-02-30', '2026-13-01', '2026-06-01T10:00:00', '20260601', ' '])(
    'ignores the malformed updated date %j',
    (raw) => {
      const encoded = encodeURIComponent(raw)
      expect(listQueryFromParams(params(`updated_from=${encoded}&updated_to=${encoded}`))).toEqual({ offset: 0, limit: 20 })
    },
  )

  it('accepts a real leap day and ignores one on a non-leap year', () => {
    expect(listQueryFromParams(params('updated_from=2024-02-29'))).toEqual({ offset: 0, limit: 20, updatedFrom: '2024-02-29' })
    expect(listQueryFromParams(params('updated_from=2026-02-29'))).toEqual({ offset: 0, limit: 20 })
  })

  it('ignores the old Expected Close from/to keys', () => {
    expect(listQueryFromParams(params('from=2026-01-01&to=2026-12-31'))).toEqual({ offset: 0, limit: 20 })
  })

  it('ignores broken values instead of failing', () => {
    const query = listQueryFromParams(params('year=abc&quarter=9&sort=bogus&order=up&page=0&mine=0&q=%20%20'))
    expect(query).toEqual({ offset: 0, limit: 20 })
    expect(listQueryFromParams(params('page=-3')).offset).toBe(0)
    expect(listQueryFromParams(params('page=x')).offset).toBe(0)
  })

  it('AC-18 sends a quarter without a year (it means this year on the server)', () => {
    expect(listQueryFromParams(params('quarter=2'))).toEqual({ offset: 0, limit: 20, quarter: 2 })
  })

  it('keeps year and quarter together when both are present', () => {
    expect(listQueryFromParams(params('year=2027&quarter=1'))).toEqual({ offset: 0, limit: 20, year: 2027, quarter: 1 })
  })

  it('ignores a quarter outside 1 to 4 even without a year', () => {
    expect(listQueryFromParams(params('quarter=0'))).toEqual({ offset: 0, limit: 20 })
    expect(listQueryFromParams(params('quarter=5'))).toEqual({ offset: 0, limit: 20 })
  })

  it('reads integer vendor and solution ids', () => {
    expect(listQueryFromParams(params('vendor=12&solution=3'))).toEqual({ offset: 0, limit: 20, vendorId: 12, solutionId: 3 })
  })

  it('ignores uuid and name values for vendor and solution', () => {
    expect(listQueryFromParams(params('vendor=Okta&solution=SSO'))).toEqual({ offset: 0, limit: 20 })
    expect(
      listQueryFromParams(params('vendor=10000000-0000-4000-8000-000000000003&solution=20000000-0000-4000-8000-000000000003')),
    ).toEqual({ offset: 0, limit: 20 })
    expect(listQueryFromParams(params(`vendor=${VENDOR}&solution=ITDR`))).toEqual({ offset: 0, limit: 20, vendorId: VENDOR })
  })

  it.each(['0', '-1', '1.5', '1e3', '01', '+3', '9007199254740992'])(
    'ignores the out-of-range or non-integer id %j in every id parameter',
    (raw) => {
      const encoded = encodeURIComponent(raw)
      expect(listQueryFromParams(params(`vendor=${encoded}&solution=${encoded}&owner=${encoded}&budget=${encoded}&need=${encoded}`))).toEqual({
        offset: 0,
        limit: 20,
      })
    },
  )

  it('accepts the largest safe integer as an id', () => {
    expect(listQueryFromParams(params('vendor=9007199254740991'))).toEqual({ offset: 0, limit: 20, vendorId: 9007199254740991 })
  })

  it('ignores an old uuid or user key in the owner and bant parameters', () => {
    expect(listQueryFromParams(params('owner=u-kim&budget=lb-1&authority=0f0e0d0c-0b0a-4908-8706-050403020100'))).toEqual({
      offset: 0,
      limit: 20,
    })
  })
})

describe('updateParams', () => {
  it('sets a value, drops empty ones and goes back to the first page', () => {
    const next = updateParams(params(`q=a&page=3&vendor=${VENDOR}`), { vendor: '', status: 'best' })
    expect(next.get('vendor')).toBeNull()
    expect(next.get('status')).toBe('best')
    expect(next.get('q')).toBe('a')
    expect(next.get('page')).toBeNull()
  })

  it('sets and clears the updated dates like other conditions', () => {
    const set = updateParams(params('page=2'), { updated_from: '2026-06-01', updated_to: '2026-06-30' })
    expect(set.get('updated_from')).toBe('2026-06-01')
    expect(set.get('updated_to')).toBe('2026-06-30')
    expect(set.get('page')).toBeNull()
    const cleared = updateParams(set, { updated_from: '', updated_to: '' })
    expect(cleared.toString()).toBe('')
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
  it('is true for an updated date and false for the old from/to keys', () => {
    expect(hasActiveFilter(params('updated_from=2026-06-01'))).toBe(true)
    expect(hasActiveFilter(params('updated_to=2026-06-30'))).toBe(true)
    expect(hasActiveFilter(params('from=2026-06-01&to=2026-06-30'))).toBe(false)
  })
  it('is true for any condition including mine', () => {
    expect(hasActiveFilter(params('mine=1'))).toBe(true)
    expect(hasActiveFilter(params('budget=1'))).toBe(true)
    expect(hasActiveFilter(params('q=a'))).toBe(true)
  })
})

describe('FILTER_KEYS', () => {
  it('replaces from/to with updated_from/updated_to and keeps sixteen keys', () => {
    expect(FILTER_KEYS).toHaveLength(16)
    expect(FILTER_KEYS).toContain('updated_from')
    expect(FILTER_KEYS).toContain('updated_to')
    expect(FILTER_KEYS).not.toContain('from')
    expect(FILTER_KEYS).not.toContain('to')
    expect(REMEMBERED_LIST_KEYS).toContain('updated_from')
    expect(REMEMBERED_LIST_KEYS).not.toContain('from')
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

describe('next_status URL 키 (AC-24)', () => {
  it.each([
    ['open', 'open'],
    ['done', 'done'],
    ['not_done', 'notDone'],
    ['closed', 'closed'],
  ] as const)('maps next_status=%s to nextActionStatus %s', (wire, status) => {
    expect(listQueryFromParams(params(`next_status=${wire}`))).toEqual({ offset: 0, limit: 20, nextActionStatus: status })
  })

  it.each(['', 'bogus', 'notDone', 'DONE', 'all'])('ignores next_status=%s', (value) => {
    expect(listQueryFromParams(params(`next_status=${value}`))).toEqual({ offset: 0, limit: 20 })
  })

  it('counts next_status as an active filter and a remembered key', () => {
    expect(hasActiveFilter(params('next_status=open'))).toBe(true)
    expect(hasActiveFilter(params('next_status='))).toBe(false)
    expect(FILTER_KEYS).toContain('next_status')
    expect(REMEMBERED_LIST_KEYS).toContain('next_status')
  })

  it('returns to the first page when next_status changes', () => {
    const next = updateParams(params('page=3'), { next_status: 'closed' })

    expect(next.get('next_status')).toBe('closed')
    expect(next.has('page')).toBe(false)
  })
})
