import { describe, expect, it } from 'vitest'
import { listQueryFromParams } from '../deals/list/listQuery'
import {
  closingMonthPath,
  closingQuarterPath,
  forecastTilePath,
  openTotalPath,
  overduePath,
  quarterCellPath,
  quarterTotalPath,
  stalePath,
  statusPath,
  statusTotalPath,
} from './drillDown'

/**
 * Drill-down URL(계획 4.5절 표). 키 순서는 year, quarter, month, owner, vendor, status, forecast, outcome, overdue, stale로 고정한다.
 * scope = 대시보드 필터(연도·Quarter·담당자·Vendor). Vendor는 목록에 있는 id만 호출자가 넘긴다.
 */

const FULL = { year: 2026, quarter: 4, ownerId: 7, vendor: 3 } as const
const YEAR_ONLY = { year: 2026 } as const
const OWNER_ONLY = { year: 2026, ownerId: 7 } as const
const VENDOR_ONLY = { year: 2026, vendor: 3 } as const

const queryOf = (path: string) => listQueryFromParams(new URLSearchParams(path.split('?')[1] ?? ''))
const PAGING = { offset: 0, limit: 20 }

describe('Forecast tile and Open total (공통)', () => {
  it('opens the deals of one forecast code with the whole filter', () => {
    expect(forecastTilePath(FULL, 'commit')).toBe('/deals?year=2026&quarter=4&owner=7&vendor=3&forecast=commit')
  })

  it('leaves out the quarter, owner and vendor that are not chosen', () => {
    expect(forecastTilePath(YEAR_ONLY, 'pipeline')).toBe('/deals?year=2026&forecast=pipeline')
    expect(forecastTilePath(OWNER_ONLY, 'best')).toBe('/deals?year=2026&owner=7&forecast=best')
    expect(forecastTilePath(VENDOR_ONLY, 'won')).toBe('/deals?year=2026&vendor=3&forecast=won')
  })

  it('opens the open deals for the Open total tile', () => {
    expect(openTotalPath(FULL)).toBe('/deals?year=2026&quarter=4&owner=7&vendor=3&outcome=open')
    expect(openTotalPath(YEAR_ONLY)).toBe('/deals?year=2026&outcome=open')
  })
})

describe('Status bar and table (Status 탭)', () => {
  it('opens one status without Lost deals', () => {
    expect(statusPath(FULL, 'poc_completed')).toBe('/deals?year=2026&quarter=4&owner=7&vendor=3&status=poc_completed&outcome=not_lost')
  })

  it('matches the documented example: year 2026, owner 7, no vendor, POC완료', () => {
    expect(statusPath(OWNER_ONLY, 'poc_completed')).toBe('/deals?year=2026&owner=7&status=poc_completed&outcome=not_lost')
  })

  it('opens all non-lost deals for the total row', () => {
    expect(statusTotalPath(FULL)).toBe('/deals?year=2026&quarter=4&owner=7&vendor=3&outcome=not_lost')
    expect(statusTotalPath(YEAR_ONLY)).toBe('/deals?year=2026&outcome=not_lost')
  })
})

describe('attention tiles', () => {
  it('ignores the period for the overdue tile and keeps owner and vendor', () => {
    expect(overduePath(FULL)).toBe('/deals?owner=7&vendor=3&overdue=1')
    expect(overduePath(YEAR_ONLY)).toBe('/deals?overdue=1')
  })

  it('ignores the period for the stale tile and keeps owner and vendor', () => {
    expect(stalePath(FULL)).toBe('/deals?owner=7&vendor=3&stale=1')
    expect(stalePath(VENDOR_ONLY)).toBe('/deals?vendor=3&stale=1')
  })

  it('uses the server year and quarter of this quarter, not the chosen period', () => {
    expect(closingQuarterPath(FULL, { year: 2026, quarter: 4 })).toBe('/deals?year=2026&quarter=4&owner=7&vendor=3&outcome=open')
    expect(closingQuarterPath({ year: 2020, quarter: 1 }, { year: 2027, quarter: 1 })).toBe('/deals?year=2027&quarter=1&outcome=open')
  })

  it('uses the server year and month of this month, not the chosen period', () => {
    expect(closingMonthPath(FULL, { year: 2026, month: 10 })).toBe('/deals?year=2026&month=10&owner=7&vendor=3&outcome=open')
    expect(closingMonthPath({ year: 2020, quarter: 1 }, { year: 2027, month: 1 })).toBe('/deals?year=2027&month=1&outcome=open')
  })
})

describe('quarter chart and table (Forecast 탭)', () => {
  it('opens one forecast code of one quarter whatever quarter is chosen', () => {
    expect(quarterCellPath(FULL, 2, 'commit')).toBe('/deals?year=2026&quarter=2&owner=7&vendor=3&forecast=commit')
    expect(quarterCellPath(YEAR_ONLY, 3, 'won')).toBe('/deals?year=2026&quarter=3&forecast=won')
  })

  it('opens the non-lost deals of one quarter for the quarter total', () => {
    expect(quarterTotalPath(FULL, 1)).toBe('/deals?year=2026&quarter=1&owner=7&vendor=3&outcome=not_lost')
    expect(quarterTotalPath(OWNER_ONLY, 4)).toBe('/deals?year=2026&quarter=4&owner=7&outcome=not_lost')
  })
})

describe('round trip: the Deals list reads back the same condition (AC-16·19)', () => {
  it('forecast tile', () => {
    expect(queryOf(forecastTilePath(FULL, 'commit'))).toEqual({ ...PAGING, year: 2026, quarter: 4, ownerId: 7, vendorId: 3, forecastKey: 'commit' })
  })

  it('Open total', () => {
    expect(queryOf(openTotalPath(OWNER_ONLY))).toEqual({ ...PAGING, year: 2026, ownerId: 7, forecastOutcome: 'open' })
  })

  it('status bar', () => {
    expect(queryOf(statusPath(FULL, 'poc_completed'))).toEqual({
      ...PAGING,
      year: 2026,
      quarter: 4,
      ownerId: 7,
      vendorId: 3,
      statusKey: 'poc_completed',
      forecastOutcome: 'not_lost',
    })
  })

  it('status total', () => {
    expect(queryOf(statusTotalPath(YEAR_ONLY))).toEqual({ ...PAGING, year: 2026, forecastOutcome: 'not_lost' })
  })

  it('overdue and stale tiles', () => {
    expect(queryOf(overduePath(FULL))).toEqual({ ...PAGING, ownerId: 7, vendorId: 3, overdue: true })
    expect(queryOf(stalePath(FULL))).toEqual({ ...PAGING, ownerId: 7, vendorId: 3, stale: true })
  })

  it('closing quarter and closing month tiles', () => {
    expect(queryOf(closingQuarterPath(FULL, { year: 2026, quarter: 4 }))).toEqual({
      ...PAGING,
      year: 2026,
      quarter: 4,
      ownerId: 7,
      vendorId: 3,
      forecastOutcome: 'open',
    })
    expect(queryOf(closingMonthPath(OWNER_ONLY, { year: 2026, month: 10 }))).toEqual({
      ...PAGING,
      year: 2026,
      month: 10,
      ownerId: 7,
      forecastOutcome: 'open',
    })
  })

  it('quarter cell and quarter total', () => {
    expect(queryOf(quarterCellPath(FULL, 2, 'commit'))).toEqual({ ...PAGING, year: 2026, quarter: 2, ownerId: 7, vendorId: 3, forecastKey: 'commit' })
    expect(queryOf(quarterTotalPath(FULL, 3))).toEqual({ ...PAGING, year: 2026, quarter: 3, ownerId: 7, vendorId: 3, forecastOutcome: 'not_lost' })
  })

  it('never carries sort, order or page (the list opens on its default order, page 1)', () => {
    const paths = [
      forecastTilePath(FULL, 'commit'),
      openTotalPath(FULL),
      statusPath(FULL, 'prospecting'),
      statusTotalPath(FULL),
      overduePath(FULL),
      stalePath(FULL),
      closingQuarterPath(FULL, { year: 2026, quarter: 4 }),
      closingMonthPath(FULL, { year: 2026, month: 10 }),
      quarterCellPath(FULL, 2, 'commit'),
      quarterTotalPath(FULL, 2),
    ]

    for (const path of paths) {
      const keys = [...new URLSearchParams(path.split('?')[1] ?? '').keys()]
      expect(keys).not.toContain('sort')
      expect(keys).not.toContain('order')
      expect(keys).not.toContain('page')
      expect(path.startsWith('/deals?')).toBe(true)
    }
  })
})
