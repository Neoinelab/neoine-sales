import { screen, waitFor, within } from '@testing-library/react'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { gateway } from '../../gateway'
import { resetMock } from '../../test/fake/default'
import { USER_ID } from '../../test/fake/seed/ids'
import { seedVendorId } from '../../test/fixtures/vendors'
import { renderAt } from '../../test/mockApp'
import { lastQuery, NOW, OPEN_PARAM } from './testHelpers'

/**
 * Dashboard 탭별 검색 조건(U7, AC-30~36): 연도·Quarter·담당자·Vendor를 Status 탭과 Forecast 탭이 각자 따로 가진다.
 * URL에는 `tab`과 두 탭의 조건이 접두사 키(`status.*`, `forecast.*`)로 모두 남고, 조회와 Drill-down은 활성 탭 조건만 쓴다.
 */

beforeEach(() => resetMock({ now: NOW }))
afterEach(() => {
  vi.restoreAllMocks()
  resetMock({ now: null })
})

const group = () => screen.getByRole('group', { name: 'Quarter' })
const button = (n: number) => within(group()).getByRole('button', { name: `Q${n}` })
const pressed = () => [1, 2, 3, 4].filter((n) => button(n).getAttribute('aria-pressed') === 'true')

async function waitForOptions() {
  await within(await screen.findByLabelText('Vendor')).findByRole('option', { name: 'Okta' })
  await within(screen.getByLabelText('담당자')).findByRole('option', { name: '김영업' })
}

describe('탭마다 조건을 따로 가진다 (AC-30·31)', () => {
  it('keeps the conditions of each tab when the tab is switched back and forth', async () => {
    const summary = vi.spyOn(gateway.dashboard, 'summary')
    const { user } = await renderAt('/dashboard')
    await waitForOptions()

    await within(screen.getByLabelText('연도')).findByRole('option', { name: '2027' })
    // Status 탭: 2027(다음 해) · Q2 · 담당자
    await user.selectOptions(screen.getByLabelText('연도'), '2027')
    await user.click(button(2))
    await user.selectOptions(screen.getByLabelText('담당자'), '김영업')
    await waitFor(() => expect(lastQuery(summary)).toEqual({ year: 2027, quarters: [2], ownerId: USER_ID.kim }))

    // Forecast 탭: 한 번도 연 적 없으므로 기본값
    await user.click(screen.getByRole('tab', { name: 'Forecast' }))
    await screen.findByRole('heading', { name: /Quarter Closing Forecast/ })
    expect(screen.getByLabelText('연도')).toHaveValue('2026')
    expect(pressed()).toEqual([])
    expect(screen.getByLabelText('담당자')).toHaveDisplayValue('전체')
    await waitFor(() => expect(lastQuery(summary)).toEqual({ year: 2026 }))

    // Forecast 탭에서 Q4 · Vendor
    await user.click(button(4))
    await user.selectOptions(screen.getByLabelText('Vendor'), 'Okta')
    await waitFor(() => expect(lastQuery(summary)).toEqual({ year: 2026, quarters: [4], vendorId: seedVendorId('Okta') }))

    // 다시 Status 탭: 마지막으로 가졌던 조건
    await user.click(screen.getByRole('tab', { name: 'Status' }))
    await screen.findByRole('heading', { name: /전체 Status Pipeline/ })
    expect(screen.getByLabelText('연도')).toHaveValue('2027')
    expect(pressed()).toEqual([2])
    expect(screen.getByLabelText('담당자')).toHaveDisplayValue('김영업')
    expect(screen.getByLabelText('Vendor')).toHaveDisplayValue('전체')
    await waitFor(() => expect(lastQuery(summary)).toEqual({ year: 2027, quarters: [2], ownerId: USER_ID.kim }))

    // 다시 Forecast 탭: Q4 · Vendor 유지
    await user.click(screen.getByRole('tab', { name: 'Forecast' }))
    await screen.findByRole('heading', { name: /Quarter Closing Forecast/ })
    expect(screen.getByLabelText('연도')).toHaveValue('2026')
    expect(pressed()).toEqual([4])
    expect(screen.getByLabelText('Vendor')).toHaveDisplayValue('Okta')
    expect(screen.getByLabelText('담당자')).toHaveDisplayValue('전체')
  })

  it('does not change the other tab when a condition is changed', async () => {
    const { user, location } = await renderAt('/dashboard?tab=status&status.year=2026&forecast.year=2026&forecast.quarter=3')
    await screen.findByRole('group', { name: 'Quarter' })

    await user.click(button(1))

    await waitFor(() => expect(location()).toContain('status.quarter=1'))
    expect(location()).toContain('forecast.quarter=3')
  })
})

describe('주소에 두 탭의 조건이 모두 남는다 (AC-32·33)', () => {
  it('restores both tabs from the address', async () => {
    const { user } = await renderAt('/dashboard?tab=status&status.year=2025&status.quarter=2&forecast.year=2026&forecast.quarter=1%2C3&forecast.vendor=' + seedVendorId('Okta'))
    await waitForOptions()

    expect(screen.getByLabelText('연도')).toHaveValue('2025')
    expect(pressed()).toEqual([2])
    expect(screen.getByLabelText('Vendor')).toHaveDisplayValue('전체')

    await user.click(screen.getByRole('tab', { name: 'Forecast' }))
    await screen.findByRole('heading', { name: /Quarter Closing Forecast/ })

    expect(screen.getByLabelText('연도')).toHaveValue('2026')
    expect(pressed()).toEqual([1, 3])
    await waitFor(() => expect(screen.getByLabelText('Vendor')).toHaveDisplayValue('Okta'))
  })

  it('writes the tab and both years on the first change, with empty values left out', async () => {
    const { user, location } = await renderAt('/dashboard')
    await screen.findByRole('group', { name: 'Quarter' })

    await user.click(button(2))

    await waitFor(() => expect(location()).toBe('/dashboard?tab=status&status.year=2026&status.quarter=2&forecast.year=2026'))
  })

  it('writes both tabs and the new tab when the tab is switched', async () => {
    const { user, location } = await renderAt('/dashboard?tab=status&status.year=2026&status.quarter=2&status.owner=' + USER_ID.kim)
    await screen.findByRole('group', { name: 'Quarter' })

    await user.click(screen.getByRole('tab', { name: 'Forecast' }))

    await waitFor(() => expect(location()).toBe(`/dashboard?tab=forecast&status.year=2026&status.quarter=2&status.owner=${USER_ID.kim}&forecast.year=2026`))
  })

  it('shows the defaults for both tabs and the Status tab when the address has no query (menu entry)', async () => {
    const summary = vi.spyOn(gateway.dashboard, 'summary')
    const { user } = await renderAt('/dashboard')

    expect(await screen.findByRole('tab', { name: 'Status' })).toHaveAttribute('aria-selected', 'true')
    expect(screen.getByLabelText('연도')).toHaveValue('2026')
    expect(pressed()).toEqual([])
    await user.click(screen.getByRole('tab', { name: 'Forecast' }))
    await screen.findByRole('heading', { name: /Quarter Closing Forecast/ })
    expect(screen.getByLabelText('연도')).toHaveValue('2026')
    expect(pressed()).toEqual([])
    await waitFor(() => expect(lastQuery(summary)).toEqual({ year: 2026 }))
  })
})

describe('예전 공용 주소 (AC-34)', () => {
  it('opens an old shared address: owner on both tabs, the quarter on the Status tab only, sq ignored', async () => {
    const { user, location } = await renderAt(`/dashboard?tab=forecast&year=2025&quarter=2&owner=${USER_ID.kim}&sq=3`)
    await waitForOptions()

    expect(screen.getByLabelText('연도')).toHaveValue('2025')
    expect(pressed()).toEqual([])
    expect(screen.getByLabelText('담당자')).toHaveDisplayValue('김영업')

    await user.click(screen.getByRole('tab', { name: 'Status' }))
    await screen.findByRole('heading', { name: /전체 Status Pipeline/ })

    expect(screen.getByLabelText('연도')).toHaveValue('2025')
    expect(pressed()).toEqual([2])
    expect(screen.getByLabelText('담당자')).toHaveDisplayValue('김영업')
    const keys = [...new URLSearchParams(location().split('?')[1]).keys()]
    expect(keys).not.toContain('year')
    expect(keys).not.toContain('quarter')
    expect(keys).not.toContain('owner')
    expect(keys).not.toContain('sq')
    expect(keys).toEqual(expect.arrayContaining(['tab', 'status.year', 'status.quarter', 'status.owner', 'forecast.year', 'forecast.owner']))
  })

  it('does not rewrite the address just by opening it', async () => {
    const start = '/dashboard?tab=forecast&year=2025&quarter=2&owner=7&sq=3'
    const { location } = await renderAt(start)
    await screen.findByRole('group', { name: 'Quarter' })

    expect(location()).toBe(start)
  })
})

describe('조회는 활성 탭 조건만 쓴다 (AC-35)', () => {
  it('requests once with the active tab and does not fetch again when the other tab has the same conditions', async () => {
    const summary = vi.spyOn(gateway.dashboard, 'summary')
    const { user } = await renderAt('/dashboard')
    await screen.findByRole('heading', { name: /전체 Status Pipeline/ })
    const calls = summary.mock.calls.length

    await user.click(screen.getByRole('tab', { name: 'Forecast' }))
    await screen.findByRole('heading', { name: /Quarter Closing Forecast/ })

    expect(calls).toBe(1)
    expect(summary.mock.calls.length).toBe(calls)
  })

  it('queries with the conditions of the tab it switches to, never with the previous tab conditions again', async () => {
    const summary = vi.spyOn(gateway.dashboard, 'summary')
    const { user } = await renderAt('/dashboard')
    await screen.findByRole('group', { name: 'Quarter' })
    await user.click(button(2))
    await waitFor(() => expect(lastQuery(summary)).toEqual({ year: 2026, quarters: [2] }))
    summary.mockClear()

    await user.click(screen.getByRole('tab', { name: 'Forecast' }))
    await screen.findByRole('heading', { name: /Quarter Closing Forecast/ })

    await waitFor(() => expect(lastQuery(summary)).toEqual({ year: 2026 }))
    expect(summary.mock.calls.every(([query]) => query.quarters === undefined)).toBe(true)
  })

  it('uses the cache when going back to a tab whose conditions were already loaded', async () => {
    const summary = vi.spyOn(gateway.dashboard, 'summary')
    const { user } = await renderAt('/dashboard?tab=status&status.year=2026&status.quarter=2&forecast.year=2026')
    await screen.findByRole('heading', { name: /전체 Status Pipeline/ })
    await user.click(screen.getByRole('tab', { name: 'Forecast' }))
    await screen.findByRole('heading', { name: /Quarter Closing Forecast/ })
    await waitFor(() => expect(lastQuery(summary)).toEqual({ year: 2026 }))

    await user.click(screen.getByRole('tab', { name: 'Status' }))

    // AC-35 '캐시를 쓴다' = 이미 받은 결과를 로딩 표시 없이 바로 보여 준다(백그라운드 재조회는 허용).
    expect(screen.getByRole('heading', { name: /전체 Status Pipeline/ })).toBeInTheDocument()
    expect(screen.queryByText(/불러오는 중|로딩/)).not.toBeInTheDocument()
    expect(pressed()).toEqual([2])
  })
})

describe('Drill-down과 Vendor 판정은 활성 탭 조건을 쓴다 (AC-36)', () => {
  it('links the Forecast tab with its own conditions while the Status tab has others', async () => {
    await renderAt(`/dashboard?tab=forecast&status.year=2025&status.quarter=2&status.owner=${USER_ID.kim}&forecast.year=2026`)

    const tile = await screen.findByRole('link', { name: /Open 합계/ })

    expect(tile).toHaveAttribute('href', `/deals?year=2026&forecast=${OPEN_PARAM}`)
  })

  it('links the Status tab with its own conditions while the Forecast tab has others', async () => {
    await renderAt(`/dashboard?tab=status&status.year=2025&status.quarter=2&status.owner=${USER_ID.kim}&forecast.year=2026&forecast.quarter=4`)

    const tile = await screen.findByRole('link', { name: /Open 합계/ })

    expect(tile).toHaveAttribute('href', `/deals?year=2025&quarter=2&owner=${USER_ID.kim}&forecast=${OPEN_PARAM}`)
  })

  it('drops an unregistered vendor of the active tab only', async () => {
    const summary = vi.spyOn(gateway.dashboard, 'summary')
    await renderAt(`/dashboard?tab=forecast&status.vendor=${seedVendorId('Okta')}&forecast.vendor=999999999`)
    await within(await screen.findByLabelText('Vendor')).findByRole('option', { name: 'Okta' })

    await waitFor(() => expect(screen.getByLabelText('Vendor')).toHaveDisplayValue('전체'))
    await waitFor(() => expect(lastQuery(summary).vendorId).toBeUndefined())
  })
})
