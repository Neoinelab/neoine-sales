import { describe, expect, it } from 'vitest'
import { REMEMBERED_LIST_KEYS } from '../../../shared/model/dealListMemory'
import {
  FILTER_KEYS,
  currentSort,
  defaultListParams,
  effectiveMonth,
  hasActiveFilter,
  hasListCondition,
  listQueryFromParams,
  monthOptions,
  nextSort,
  quarterClearPatch,
  quarterTogglePatch,
  quartersOf,
  updateParams,
} from './listQuery'
import { USER_ID } from '../../../test/fake/seed/ids'

const params = (query: string) => new URLSearchParams(query)

const VENDOR = 3
const SOLUTION = 'ITDR'

describe('listQueryFromParams (T-LIST-05, T-LIST-09)', () => {
  it('returns only paging for empty params', () => {
    expect(listQueryFromParams(params(''))).toEqual({ offset: 0, limit: 20 })
  })

  it('maps every filter, sort and page from the URL', () => {
    const query = listQueryFromParams(
      params(
        `q=한빛&owner=${USER_ID.kim}&vendor=${VENDOR}&solution=${SOLUTION}&status=prospecting&forecast=best&year=2026&quarter=4&updated_from=2026-01-01&updated_to=2026-12-31&mine=1&overdue=1&stale=1&sort=revenueAmount&order=asc&page=3`,
      ),
    )
    expect(query).toEqual({
      keyword: '한빛',
      ownerId: USER_ID.kim,
      vendorId: VENDOR,
      solution: SOLUTION,
      statusKey: 'prospecting',
      forecastKeys: ['best'],
      year: 2026,
      quarters: [4],
      updatedFrom: '2026-01-01',
      updatedTo: '2026-12-31',
      mine: true,
      overdue: true,
      stale: true,
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
    expect(listQueryFromParams(params('quarter=2'))).toEqual({ offset: 0, limit: 20, quarters: [2] })
  })

  it('keeps year and quarter together when both are present', () => {
    expect(listQueryFromParams(params('year=2027&quarter=1'))).toEqual({ offset: 0, limit: 20, year: 2027, quarters: [1] })
  })

  it('ignores a quarter outside 1 to 4 even without a year', () => {
    expect(listQueryFromParams(params('quarter=0'))).toEqual({ offset: 0, limit: 20 })
    expect(listQueryFromParams(params('quarter=5'))).toEqual({ offset: 0, limit: 20 })
  })

  it('reads the integer vendor id and the solution as text', () => {
    expect(listQueryFromParams(params('vendor=12&solution=ITDR'))).toEqual({ offset: 0, limit: 20, vendorId: 12, solution: 'ITDR' })
  })

  it('passes the solution text as is', () => {
    expect(listQueryFromParams(params(`solution=${encodeURIComponent('통합 itdr')}`))).toEqual({ offset: 0, limit: 20, solution: '통합 itdr' })
    expect(listQueryFromParams(params('solution=12'))).toEqual({ offset: 0, limit: 20, solution: '12' })
  })

  it('trims the solution text and ignores a blank solution', () => {
    expect(listQueryFromParams(params('solution=%20itd%20'))).toEqual({ offset: 0, limit: 20, solution: 'itd' })
    expect(listQueryFromParams(params('solution='))).toEqual({ offset: 0, limit: 20 })
    expect(listQueryFromParams(params('solution=%20%20'))).toEqual({ offset: 0, limit: 20 })
  })

  it('ignores a solution longer than 200 characters after trimming, like other invalid values', () => {
    const over = 'a'.repeat(201)
    expect(listQueryFromParams(params(`solution=${over}`))).toEqual({ offset: 0, limit: 20 })
    expect(listQueryFromParams(params(`solution=%20${over}%20`))).toEqual({ offset: 0, limit: 20 })
    expect(listQueryFromParams(params(`vendor=12&solution=${over}`))).toEqual({ offset: 0, limit: 20, vendorId: 12 })
  })

  it('keeps a solution of exactly 200 characters even with surrounding spaces', () => {
    const edge = 'a'.repeat(200)
    expect(listQueryFromParams(params(`solution=%20${edge}%20`))).toEqual({ offset: 0, limit: 20, solution: edge })
  })

  it('ignores uuid and name values for vendor but not for the solution text', () => {
    expect(listQueryFromParams(params('vendor=Okta'))).toEqual({ offset: 0, limit: 20 })
    expect(listQueryFromParams(params('vendor=10000000-0000-4000-8000-000000000003'))).toEqual({ offset: 0, limit: 20 })
    expect(listQueryFromParams(params(`vendor=${VENDOR}&solution=ITDR`))).toEqual({ offset: 0, limit: 20, vendorId: VENDOR, solution: 'ITDR' })
  })

  it.each(['0', '-1', '1.5', '1e3', '01', '+3', '9007199254740992'])(
    'ignores the out-of-range or non-integer id %j in every id parameter',
    (raw) => {
      const encoded = encodeURIComponent(raw)
      expect(listQueryFromParams(params(`vendor=${encoded}&owner=${encoded}`))).toEqual({
        offset: 0,
        limit: 20,
      })
    },
  )

  it('accepts the largest safe integer as an id', () => {
    expect(listQueryFromParams(params('vendor=9007199254740991'))).toEqual({ offset: 0, limit: 20, vendorId: 9007199254740991 })
  })

  it('ignores an old uuid or user key in the owner parameter', () => {
    expect(listQueryFromParams(params('owner=u-kim'))).toEqual({ offset: 0, limit: 20 })
    expect(listQueryFromParams(params('owner=0f0e0d0c-0b0a-4908-8706-050403020100'))).toEqual({ offset: 0, limit: 20 })
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
    expect(hasActiveFilter(params('q=a'))).toBe(true)
  })
})

describe('FILTER_KEYS', () => {
  it('has fifteen keys without outcome: no BANT keys, with month (P6) and overdue/stale', () => {
    expect(FILTER_KEYS).toHaveLength(15)
    expect(FILTER_KEYS).not.toContain('outcome')
    expect(REMEMBERED_LIST_KEYS).not.toContain('outcome')
    expect(FILTER_KEYS).toContain('month')
    expect(REMEMBERED_LIST_KEYS).toContain('month')
    expect(FILTER_KEYS).toContain('updated_from')
    expect(FILTER_KEYS).toContain('updated_to')
    expect(FILTER_KEYS).not.toContain('from')
    expect(FILTER_KEYS).not.toContain('to')
    expect(REMEMBERED_LIST_KEYS).toContain('updated_from')
    expect(REMEMBERED_LIST_KEYS).not.toContain('from')
  })

  it.each(['budget', 'authority', 'need', 'timeline'])('no longer has the BANT key %s', (key) => {
    expect(FILTER_KEYS).not.toContain(key)
    expect(REMEMBERED_LIST_KEYS).not.toContain(key)
  })

  it.each(['overdue', 'stale'])('has %s as a filter and a remembered key', (key) => {
    expect(FILTER_KEYS).toContain(key)
    expect(REMEMBERED_LIST_KEYS).toContain(key)
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

describe('sorting by the new columns (AC-2)', () => {
  const NEW_KEYS = ['owner', 'customer', 'partner', 'vendor', 'forecastKey'] as const

  it.each(NEW_KEYS)('starts %s in ascending order', (key) => {
    expect(nextSort({ sort: 'lastUpdatedAt', order: 'desc' }, key)).toEqual({ sort: key, order: 'asc' })
  })

  it.each(NEW_KEYS)('flips %s on the second click in both directions', (key) => {
    expect(nextSort({ sort: key, order: 'asc' }, key)).toEqual({ sort: key, order: 'desc' })
    expect(nextSort({ sort: key, order: 'desc' }, key)).toEqual({ sort: key, order: 'asc' })
  })

  it.each(NEW_KEYS)('reads sort=%s from the URL with its natural order and an explicit order', (key) => {
    expect(currentSort(params(`sort=${key}`))).toEqual({ sort: key, order: 'asc' })
    expect(currentSort(params(`sort=${key}&order=desc`))).toEqual({ sort: key, order: 'desc' })
    expect(listQueryFromParams(params(`sort=${key}&order=desc`))).toEqual({ offset: 0, limit: 20, sort: key, order: 'desc' })
  })

  it.each(['forecast', 'bant', 'nextAction', 'risk', 'OWNER'])('falls back to the default sort for the unknown sort %s', (raw) => {
    expect(currentSort(params(`sort=${raw}&order=asc`))).toEqual({ sort: 'lastUpdatedAt', order: 'desc' })
    expect(listQueryFromParams(params(`sort=${raw}`))).toEqual({ offset: 0, limit: 20 })
  })

  it('keeps the existing natural orders', () => {
    expect(nextSort({ sort: 'name', order: 'asc' }, 'revenueAmount')).toEqual({ sort: 'revenueAmount', order: 'desc' })
    expect(nextSort({ sort: 'name', order: 'asc' }, 'lastUpdatedAt')).toEqual({ sort: 'lastUpdatedAt', order: 'desc' })
    expect(nextSort({ sort: 'name', order: 'desc' }, 'statusKey')).toEqual({ sort: 'statusKey', order: 'asc' })
  })
})

describe('retired BANT URL keys (AC-7)', () => {
  it('never turn the old budget/authority/need/timeline keys into a query condition', () => {
    const query = listQueryFromParams(params('budget=1&authority=2&need=3&timeline=4'))

    expect(query).toEqual({ offset: 0, limit: 20 })
    expect(query).not.toHaveProperty('bantLabelIds')
  })

  it('does not count the old BANT keys as an active filter', () => {
    expect(hasActiveFilter(params('budget=1&authority=2&need=3&timeline=4'))).toBe(false)
  })

  it('keeps the other conditions when old BANT keys are present', () => {
    expect(listQueryFromParams(params('budget=1&status=best'))).toEqual({ offset: 0, limit: 20, statusKey: 'best' })
  })
})

describe('overdue and stale URL keys (AC-9)', () => {
  it('maps overdue=1 and stale=1 to true, each alone', () => {
    expect(listQueryFromParams(params('overdue=1'))).toEqual({ offset: 0, limit: 20, overdue: true })
    expect(listQueryFromParams(params('stale=1'))).toEqual({ offset: 0, limit: 20, stale: true })
  })

  it.each(['0', 'yes', 'true', '', '2'])('ignores the value %j for overdue and stale like mine', (raw) => {
    expect(listQueryFromParams(params(`overdue=${raw}&stale=${raw}`))).toEqual({ offset: 0, limit: 20 })
  })

  it('counts them as active filters', () => {
    expect(hasActiveFilter(params('overdue=1'))).toBe(true)
    expect(hasActiveFilter(params('stale=1'))).toBe(true)
    expect(hasActiveFilter(params('overdue=&stale='))).toBe(false)
  })

  it('returns to the first page when one changes and drops the key when it is cleared', () => {
    const on = updateParams(params('page=3'), { overdue: '1' })
    expect(on.get('overdue')).toBe('1')
    expect(on.has('page')).toBe(false)
    expect(updateParams(on, { overdue: '' }).has('overdue')).toBe(false)
    expect(updateParams(params('page=2'), { stale: '1' }).has('page')).toBe(false)
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

describe('month URL key (P6 Q3-b)', () => {
  it('maps month with a year', () => {
    expect(listQueryFromParams(params('year=2026&month=3'))).toEqual({ offset: 0, limit: 20, year: 2026, month: 3 })
  })

  it('sends a month without a year (it means this year on the server)', () => {
    expect(listQueryFromParams(params('month=3'))).toEqual({ offset: 0, limit: 20, month: 3 })
  })

  it.each(['0', '13', 'abc', '1.5', ''])('ignores the month %j outside 1 to 12', (raw) => {
    expect(listQueryFromParams(params(`month=${raw}`))).toEqual({ offset: 0, limit: 20 })
  })

  it('sends only the month when it belongs to the chosen quarter', () => {
    const query = listQueryFromParams(params('year=2026&quarter=4&month=11'))
    expect(query).toEqual({ offset: 0, limit: 20, year: 2026, month: 11 })
    expect(query).not.toHaveProperty('quarters')
  })

  it('counts a month as an active filter and returns to the first page when it changes', () => {
    expect(hasActiveFilter(params('month=3'))).toBe(true)
    expect(updateParams(params('page=3'), { month: '3' }).get('page')).toBeNull()
  })
})

describe('month URL value format matches the Forecast screen (R1 Nit)', () => {
  it.each(['03', '01', '012', '+3', ' 3', '3 '])('ignores the month %j like the Forecast URL parser', (raw) => {
    expect(listQueryFromParams(params(`year=2026&month=${encodeURIComponent(raw)}`))).toEqual({ offset: 0, limit: 20, year: 2026 })
  })

  it.each(['1', '9', '10', '12'])('accepts the plain month %j', (raw) => {
    expect(listQueryFromParams(params(`month=${raw}`))).toMatchObject({ month: Number(raw) })
  })
})

describe('forecast URL value is a comma separated key list (다중 조건 AC-11·12)', () => {
  it('reads sorted, de-duplicated keys', () => {
    expect(listQueryFromParams(params('forecast=pipeline%2Cbest'))).toEqual({ offset: 0, limit: 20, forecastKeys: ['best', 'pipeline'] })
    expect(listQueryFromParams(params('forecast=best%2Cbest%2C'))).toEqual({ offset: 0, limit: 20, forecastKeys: ['best'] })
  })

  it('reads an old single value as one key', () => {
    expect(listQueryFromParams(params('forecast=commit'))).toMatchObject({ forecastKeys: ['commit'] })
  })

  it('drops keys whose format is wrong', () => {
    expect(listQueryFromParams(params('forecast=Commit%2Cbest'))).toMatchObject({ forecastKeys: ['best'] })
    expect(listQueryFromParams(params('forecast=XYZ'))).not.toHaveProperty('forecastKeys')
  })

  it('keeps a well formed key that no code has (the server answers with zero deals)', () => {
    expect(listQueryFromParams(params('forecast=no_such'))).toMatchObject({ forecastKeys: ['no_such'] })
  })

  it('ignores the whole condition above one hundred distinct keys', () => {
    const many = Array.from({ length: 101 }, (_, i) => `k${i}`).join('%2C')
    expect(listQueryFromParams(params(`forecast=${many}`))).not.toHaveProperty('forecastKeys')
  })

  it('does not send the retired single key field', () => {
    expect(listQueryFromParams(params('forecast=commit'))).not.toHaveProperty('forecastKey')
  })

  it('still counts a malformed value as a condition key', () => {
    expect(hasListCondition(params('forecast=XYZ'))).toBe(true)
  })
})

describe('outcome URL key is retired', () => {
  it.each(['open', 'won', 'lost', 'not_lost'])('ignores outcome=%s', (value) => {
    const query = listQueryFromParams(params(`outcome=${value}`))
    expect(query).toEqual({ offset: 0, limit: 20 })
    expect(query).not.toHaveProperty('forecastOutcome')
  })

  it('ignores outcome next to the forecast key', () => {
    const query = listQueryFromParams(params('forecast=commit&outcome=open'))
    expect(query).toEqual({ offset: 0, limit: 20, forecastKeys: ['commit'] })
    expect(query).not.toHaveProperty('forecastOutcome')
  })

  it('does not count outcome as an active filter', () => {
    expect(hasActiveFilter(params('outcome=open'))).toBe(false)
  })
})

describe('year=all (AC-09, AC-18)', () => {
  it('is not sent as a year', () => {
    expect(listQueryFromParams(params('year=all&quarter=4'))).toEqual({ offset: 0, limit: 20, quarters: [4] })
  })

  it('is not an active filter for the empty-state wording', () => {
    expect(hasActiveFilter(params('year=all'))).toBe(false)
    expect(hasActiveFilter(params('year=all&quarter=4'))).toBe(true)
    expect(hasActiveFilter(params('year=2026'))).toBe(true)
    expect(hasActiveFilter(params('outcome=open'))).toBe(false)
  })
})

describe('defaultListParams (AC-04, AC-06)', () => {
  it.each([
    ['2026-10-26', 'year=2026'],
    ['2027-01-01', 'year=2027'],
    ['2026-03-31', 'year=2026'],
    ['2026-04-01', 'year=2026'],
  ])('uses this year only, without a quarter, on %s', (today, expected) => {
    expect(defaultListParams(today).toString()).toBe(expected)
  })

  it('keeps sort and order and drops page and unknown keys', () => {
    const current = params('sort=owner&order=asc&page=3&outcome=open')
    expect(defaultListParams('2026-10-26', current).toString()).toBe('year=2026&sort=owner&order=asc')
  })
})

describe('hasListCondition (AC-04, AC-09)', () => {
  it.each(['', 'q=', 'q=%20', 'sort=name&page=2', 'outcome=open', 'foo=1'])('is false for %j', (query) => {
    expect(hasListCondition(params(query))).toBe(false)
  })

  it.each(['year=all', 'quarter=4', 'overdue=1', 'owner=abc', 'month=3'])('is true for %j', (query) => {
    expect(hasListCondition(params(query))).toBe(true)
  })
})

describe('quarter and month rules (AC-10 to AC-13)', () => {
  it('never sends quarter and month together', () => {
    for (let quarter = 1; quarter <= 4; quarter += 1) {
      for (let month = 1; month <= 12; month += 1) {
        const query = listQueryFromParams(params(`year=2026&quarter=${quarter}&month=${month}`))
        expect(query.quarters !== undefined && query.month !== undefined).toBe(false)
        expect(query.quarters !== undefined || query.month !== undefined).toBe(true)
      }
    }
  })

  it('keeps only the quarter when the month is outside it', () => {
    expect(listQueryFromParams(params('year=2026&quarter=4&month=3'))).toEqual({ offset: 0, limit: 20, year: 2026, quarters: [4] })
  })

  it('keeps the month when the quarter is not a real quarter', () => {
    expect(listQueryFromParams(params('quarter=9&month=3'))).toEqual({ offset: 0, limit: 20, month: 3 })
  })

  it.each([
    ['quarter=4&month=11', 11],
    ['quarter=4&month=3', undefined],
    ['month=3', 3],
    ['quarter=9&month=3', 3],
    ['month=13', undefined],
    ['', undefined],
  ])('effectiveMonth of %j is %s', (query, expected) => {
    expect(effectiveMonth(params(query))).toBe(expected)
  })

  it('offers the three months of the chosen quarter and all twelve otherwise', () => {
    expect(monthOptions(params('quarter=2'))).toEqual([4, 5, 6])
    expect(monthOptions(params('quarter=4'))).toEqual([10, 11, 12])
    expect(monthOptions(params(''))).toEqual([1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12])
    expect(monthOptions(params('quarter=9'))).toHaveLength(12)
  })

  it('offers the union of the months of several chosen quarters (AC-24)', () => {
    expect(monthOptions(params('quarter=1%2C3'))).toEqual([1, 2, 3, 7, 8, 9])
    expect(monthOptions(params('quarter=4%2C2'))).toEqual([4, 5, 6, 10, 11, 12])
  })

  it('offers twelve months for all four quarters', () => {
    expect(monthOptions(params('quarter=1%2C2%2C3%2C4'))).toHaveLength(12)
  })

  it('clears the month when the toggled quarters no longer contain it (AC-25)', () => {
    // Q1만 고른 상태에서 월 2 → Q3 켜고 Q1 끔은 두 번의 토글이다. Q1을 끄면 Q3만 남아 월 2는 사라진다.
    expect(quarterTogglePatch(params('quarter=1%2C3&month=2'), 1, false)).toEqual({ quarter: '3', month: '' })
  })

  it('keeps the visible month when the new quarters still contain it (AC-25)', () => {
    expect(quarterTogglePatch(params('quarter=1&month=2'), 2, true)).toEqual({ quarter: '1,2' })
    expect(quarterTogglePatch(params('quarter=1%2C3&month=8'), 1, false)).toEqual({ quarter: '3' })
  })

  it('turns the first quarter on without touching a month that is visible', () => {
    expect(quarterTogglePatch(params('month=5'), 2, true)).toEqual({ quarter: '2' })
  })

  it('clears a month the first quarter does not contain', () => {
    expect(quarterTogglePatch(params('month=5'), 1, true)).toEqual({ quarter: '1', month: '' })
  })

  it('writes the toggled quarters ascending with commas', () => {
    expect(quarterTogglePatch(params('quarter=3'), 1, true).quarter).toBe('1,3')
    expect(quarterTogglePatch(params('quarter=1%2C3'), 3, false).quarter).toBe('1')
  })

  it('writes an empty quarter when the last one is turned off', () => {
    expect(quarterTogglePatch(params('quarter=2'), 2, false)).toEqual({ quarter: '' })
  })

  it('drops a month hidden by the current quarters even when the new quarters would include it', () => {
    expect(quarterTogglePatch(params('year=2026&quarter=1%2C3&month=5'), 2, true)).toEqual({ quarter: '1,2,3', month: '' })
  })

  it('keeps all four quarters in the URL when the fourth is turned on (U6)', () => {
    expect(quarterTogglePatch(params('quarter=1%2C2%2C3'), 4, true)).toEqual({ quarter: '1,2,3,4' })
  })

  it('keeps a visible month when the quarters are cleared with the all button', () => {
    expect(quarterClearPatch(params('quarter=4&month=11'))).toEqual({ quarter: '' })
    expect(quarterClearPatch(params('quarter=1%2C3&month=8'))).not.toHaveProperty('month')
  })

  it('clears a hidden month when the quarters are cleared with the all button', () => {
    expect(quarterClearPatch(params('quarter=4&month=3'))).toEqual({ quarter: '', month: '' })
  })
})

describe('Quarter multi-select in the URL (AC-23·26)', () => {
  it('reads several quarters into an ascending list', () => {
    expect(quartersOf(params('quarter=3%2C1'))).toEqual([1, 3])
    expect(listQueryFromParams(params('year=2026&quarter=1%2C3'))).toEqual({ offset: 0, limit: 20, year: 2026, quarters: [1, 3] })
  })

  it('sends only the month when it belongs to one of the chosen quarters', () => {
    const query = listQueryFromParams(params('year=2026&quarter=1%2C3&month=8'))

    expect(query).toEqual({ offset: 0, limit: 20, year: 2026, month: 8 })
  })

  it('sends only the quarters when the month is outside the chosen quarters', () => {
    expect(listQueryFromParams(params('year=2026&quarter=1%2C3&month=5'))).toEqual({ offset: 0, limit: 20, year: 2026, quarters: [1, 3] })
  })

  it('sends no quarters for all four (same as none) but keeps them readable for the screen', () => {
    expect(listQueryFromParams(params('year=2026&quarter=1%2C2%2C3%2C4'))).toEqual({ offset: 0, limit: 20, year: 2026 })
    expect(quartersOf(params('quarter=1%2C2%2C3%2C4'))).toEqual([1, 2, 3, 4])
  })

  it('opens an old single-quarter address as that one quarter', () => {
    expect(quartersOf(params('quarter=4'))).toEqual([4])
    expect(listQueryFromParams(params('quarter=4'))).toEqual({ offset: 0, limit: 20, quarters: [4] })
  })

  it('drops items in the wrong format', () => {
    expect(quartersOf(params('quarter=1%2C9%2Cx'))).toEqual([1])
    expect(listQueryFromParams(params('quarter=9%2Cx'))).toEqual({ offset: 0, limit: 20 })
  })

  it('keeps the month visible when several quarters hold it', () => {
    expect(effectiveMonth(params('quarter=1%2C3&month=8'))).toBe(8)
    expect(effectiveMonth(params('quarter=1%2C3&month=5'))).toBeUndefined()
    expect(effectiveMonth(params('quarter=1%2C2%2C3%2C4&month=5'))).toBe(5)
  })

  it('counts several quarters as a list condition', () => {
    expect(hasActiveFilter(params('quarter=1%2C3'))).toBe(true)
    expect(hasListCondition(params('quarter=1%2C3'))).toBe(true)
  })
})
