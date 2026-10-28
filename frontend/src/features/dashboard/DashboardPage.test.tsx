import { screen, waitFor, within } from '@testing-library/react'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { gateway } from '../../gateway'
import { ApiError } from '../../shared/api/problem'
import { resetMock } from '../../test/fake/default'
import { USER_ID } from '../../test/fake/seed/ids'
import { dashboardSummaryFixture, emptyDashboardSummary } from '../../test/fixtures/dashboardSummary'
import { seedVendorId } from '../../test/fixtures/vendors'
import { renderAt } from '../../test/mockApp'
import { NO_SUCH_ID } from '../../test/fake/seed/ids'
import { lastQuery, mockSummary, NOW } from './testHelpers'

/** Dashboard 화면의 틀(탭·필터·URL·빈 상태·오류·이전 값 유지). AC-10·11·20. */

beforeEach(() => resetMock({ now: NOW }))
afterEach(() => {
  vi.restoreAllMocks()
  resetMock({ now: null })
})

const STATUS_HEADING = /전체 Status Pipeline/
const FORECAST_HEADING = /Quarter Closing Forecast/

/** 필터 줄의 Quarter 토글 묶음(Q1~Q4 버튼)과 그 버튼. */
const quarterGroup = () => screen.getByRole('group', { name: 'Quarter' })
const quarterButton = (n: number) => within(quarterGroup()).getByRole('button', { name: `Q${n}` })

describe('Dashboard 화면과 탭 (AC-10)', () => {
  it('replaces the coming soon page with the Dashboard and two tabs', async () => {
    await renderAt('/dashboard')

    expect(await screen.findByRole('heading', { level: 1, name: 'Dashboard' })).toBeVisible()
    expect(screen.queryByText(/준비 중입니다/)).not.toBeInTheDocument()
    expect(screen.getByRole('tab', { name: 'Status' })).toBeVisible()
    expect(screen.getByRole('tab', { name: 'Forecast' })).toBeVisible()
  })

  it('starts on the Status tab', async () => {
    await renderAt('/dashboard')

    expect(await screen.findByRole('tab', { name: 'Status' })).toHaveAttribute('aria-selected', 'true')
    expect(screen.getByRole('tab', { name: 'Forecast' })).toHaveAttribute('aria-selected', 'false')
    expect(await screen.findByRole('heading', { name: STATUS_HEADING })).toBeVisible()
  })

  it('opens the Forecast tab named in the URL', async () => {
    await renderAt('/dashboard?tab=forecast')

    expect(await screen.findByRole('tab', { name: 'Forecast' })).toHaveAttribute('aria-selected', 'true')
    expect(await screen.findByRole('heading', { name: FORECAST_HEADING })).toBeVisible()
  })

  it.each(['reports', 'FORECAST', ''])('shows the Status tab for the unknown tab %j', async (value) => {
    await renderAt(`/dashboard?tab=${encodeURIComponent(value)}`)

    expect(await screen.findByRole('tab', { name: 'Status' })).toHaveAttribute('aria-selected', 'true')
  })

  it('puts the tab in the URL when it is switched and keeps the conditions of both tabs', async () => {
    const { user, location } = await renderAt('/dashboard?tab=status&status.year=2026&status.quarter=3')
    await screen.findByRole('heading', { name: STATUS_HEADING })

    await user.click(screen.getByRole('tab', { name: 'Forecast' }))

    await waitFor(() => expect(location()).toContain('tab=forecast'))
    expect(location()).toContain('status.year=2026')
    expect(location()).toContain('status.quarter=3')
    expect(location()).toContain('forecast.year=2026')
    expect(await screen.findByRole('heading', { name: FORECAST_HEADING })).toBeVisible()
  })

  it('shares one request between both tabs (switching does not fetch again)', async () => {
    const summary = vi.spyOn(gateway.dashboard, 'summary')
    const { user } = await renderAt('/dashboard')
    await screen.findByRole('heading', { name: STATUS_HEADING })
    const calls = summary.mock.calls.length

    await user.click(screen.getByRole('tab', { name: 'Forecast' }))
    await screen.findByRole('heading', { name: FORECAST_HEADING })
    await user.click(screen.getByRole('tab', { name: 'Status' }))
    await screen.findByRole('heading', { name: STATUS_HEADING })

    expect(summary.mock.calls.length).toBe(calls)
  })
})

describe('필터 (AC-11)', () => {
  it('starts with this year and nothing else chosen', async () => {
    const summary = vi.spyOn(gateway.dashboard, 'summary')
    await renderAt('/dashboard')

    expect(await screen.findByLabelText('연도')).toHaveValue('2026')
    for (const n of [1, 2, 3, 4]) expect(quarterButton(n)).toHaveAttribute('aria-pressed', 'false')
    expect(screen.getByLabelText('담당자')).toHaveDisplayValue('전체')
    expect(screen.getByLabelText('Vendor')).toHaveDisplayValue('전체')
    await waitFor(() => expect(lastQuery(summary)).toEqual({ year: 2026 }))
  })

  it('has no month filter', async () => {
    await renderAt('/dashboard')
    await screen.findByLabelText('연도')

    expect(screen.queryByLabelText('월')).not.toBeInTheDocument()
  })

  it('lists the years from the earliest deal to next year and the one in the URL', async () => {
    await renderAt('/dashboard?year=2031')

    const year = await screen.findByLabelText('연도')
    await waitFor(() => expect(within(year).getAllByRole('option').map((o) => o.textContent)).toEqual(['2026', '2027', '2031']))
    expect(year).toHaveValue('2031')
  })

  it('puts a chosen quarter in the URL, keeps the tab and sends it to the server', async () => {
    const summary = vi.spyOn(gateway.dashboard, 'summary')
    const { user, location } = await renderAt('/dashboard?tab=status')
    await screen.findByRole('group', { name: 'Quarter' })

    await user.click(quarterButton(2))

    await waitFor(() => expect(location()).toContain('status.quarter=2'))
    expect(location()).toContain('tab=status')
    expect(location()).toContain('status.year=2026')
    await waitFor(() => expect(lastQuery(summary)).toEqual({ year: 2026, quarters: [2] }))
  })

  it('puts a chosen owner and vendor in the URL as ids', async () => {
    const summary = vi.spyOn(gateway.dashboard, 'summary')
    const { user, location } = await renderAt('/dashboard')
    const vendor = await screen.findByLabelText('Vendor')
    await within(vendor).findByRole('option', { name: 'Okta' })
    await within(screen.getByLabelText('담당자')).findByRole('option', { name: '김영업' })

    await user.selectOptions(screen.getByLabelText('담당자'), '김영업')
    await user.selectOptions(screen.getByLabelText('Vendor'), 'Okta')

    await waitFor(() => expect(location()).toContain(`status.owner=${USER_ID.kim}`))
    expect(location()).toContain(`status.vendor=${seedVendorId('Okta')}`)
    await waitFor(() => expect(lastQuery(summary)).toEqual({ year: 2026, ownerId: USER_ID.kim, vendorId: seedVendorId('Okta') }))
  })

  it('offers resigned owners', async () => {
    await renderAt('/dashboard')

    expect(await within(await screen.findByLabelText('담당자')).findByRole('option', { name: '강퇴사(퇴사)' })).toBeInTheDocument()
  })

  it('shows the same selection after a reload (the URL is the truth)', async () => {
    await renderAt(`/dashboard?tab=forecast&forecast.year=2027&forecast.quarter=3&forecast.owner=${USER_ID.park}&forecast.vendor=${seedVendorId('Okta')}`)

    expect(await screen.findByRole('tab', { name: 'Forecast' })).toHaveAttribute('aria-selected', 'true')
    expect(screen.getByLabelText('연도')).toHaveValue('2027')
    expect(quarterButton(3)).toHaveAttribute('aria-pressed', 'true')
    await waitFor(() => expect(screen.getByLabelText('담당자')).toHaveDisplayValue('박영업'))
    await waitFor(() => expect(screen.getByLabelText('Vendor')).toHaveDisplayValue('Okta'))
  })

  it('opens an old shared address: year and owner on both tabs, the quarter on the Status tab only (AC-34)', async () => {
    const summary = vi.spyOn(gateway.dashboard, 'summary')
    const { user } = await renderAt(`/dashboard?year=2026&quarter=3&owner=${USER_ID.kim}`)
    await screen.findByRole('heading', { name: STATUS_HEADING })
    expect(lastQuery(summary)).toEqual({ year: 2026, quarters: [3], ownerId: USER_ID.kim })

    await user.click(screen.getByRole('tab', { name: 'Forecast' }))
    await screen.findByRole('heading', { name: FORECAST_HEADING })

    expect(screen.getByLabelText('담당자')).toHaveDisplayValue('김영업')
    for (const n of [1, 2, 3, 4]) expect(quarterButton(n)).toHaveAttribute('aria-pressed', 'false')
    await waitFor(() => expect(lastQuery(summary)).toEqual({ year: 2026, ownerId: USER_ID.kim }))
  })

  it('has year, Quarter toggles, owner and vendor on the Forecast tab too (AC-12)', async () => {
    await renderAt('/dashboard?tab=forecast&forecast.year=2026&forecast.quarter=2')
    await screen.findByRole('heading', { name: FORECAST_HEADING })

    expect(screen.getByLabelText('연도')).toBeVisible()
    expect(screen.getByLabelText('담당자')).toBeVisible()
    expect(screen.getByLabelText('Vendor')).toBeVisible()
    expect(quarterButton(2)).toHaveAttribute('aria-pressed', 'true')
    expect(screen.queryByRole('combobox', { name: 'Quarter' })).not.toBeInTheDocument()
  })

  it('brings the Status quarters back with the same value after the Forecast tab (AC-31)', async () => {
    const { user } = await renderAt('/dashboard?tab=status&status.year=2026&status.quarter=2')
    await screen.findByRole('group', { name: 'Quarter' })
    expect(quarterButton(2)).toHaveAttribute('aria-pressed', 'true')

    await user.click(screen.getByRole('tab', { name: 'Forecast' }))
    await screen.findByRole('heading', { name: FORECAST_HEADING })
    expect(quarterButton(2)).toHaveAttribute('aria-pressed', 'false')
    await user.click(screen.getByRole('tab', { name: 'Status' }))

    await screen.findByRole('heading', { name: STATUS_HEADING })
    expect(quarterButton(2)).toHaveAttribute('aria-pressed', 'true')
  })

  it('shows an unregistered vendor id as all and leaves it out of the request', async () => {
    const summary = vi.spyOn(gateway.dashboard, 'summary')
    await renderAt(`/dashboard?year=2026&vendor=${NO_SUCH_ID}`)
    await within(await screen.findByLabelText('Vendor')).findByRole('option', { name: 'Okta' })

    await waitFor(() => expect(screen.getByLabelText('Vendor')).toHaveDisplayValue('전체'))
    await waitFor(() => expect(lastQuery(summary).vendorId).toBeUndefined())
  })

  it.each(['abc', '0', '-3'])('ignores the broken owner %j', async (value) => {
    const summary = vi.spyOn(gateway.dashboard, 'summary')
    await renderAt(`/dashboard?owner=${value}`)

    expect(await screen.findByLabelText('담당자')).toHaveDisplayValue('전체')
    await waitFor(() => expect(lastQuery(summary).ownerId).toBeUndefined())
  })
})

describe('빈 상태·오류·이전 값 유지 (AC-20)', () => {
  it('shows the empty message and zero everywhere when no deal matches', async () => {
    mockSummary(emptyDashboardSummary())
    await renderAt('/dashboard')

    expect(await screen.findByText('조건에 맞는 Deal이 없습니다.')).toBeVisible()
    expect(screen.getByRole('table')).toBeVisible()
    expect(screen.getByRole('row', { name: /기회발굴/ })).toBeVisible()
  })

  it('shows the empty message on the Forecast tab too', async () => {
    mockSummary(emptyDashboardSummary())
    await renderAt('/dashboard?tab=forecast')

    expect(await screen.findByText('조건에 맞는 Deal이 없습니다.')).toBeVisible()
    expect(screen.getByRole('table')).toBeVisible()
  })

  it('shows no empty message when there are deals', async () => {
    mockSummary(dashboardSummaryFixture())
    await renderAt('/dashboard')

    await screen.findByRole('table')
    expect(screen.queryByText('조건에 맞는 Deal이 없습니다.')).not.toBeInTheDocument()
  })

  it('shows an error banner for a failed request and keeps the filters usable', async () => {
    const summary = vi
      .spyOn(gateway.dashboard, 'summary')
      .mockRejectedValue(new ApiError(500, { type: 'https://sales.neoine.test/problems/internal-error', title: 'x', status: 500, detail: '서버 오류가 발생했습니다.' }))
    const { user, location } = await renderAt('/dashboard')

    expect(await screen.findByRole('alert')).toHaveTextContent('서버 오류가 발생했습니다.')
    expect(screen.getByLabelText('연도')).toBeEnabled()
    await user.click(quarterButton(1))

    await waitFor(() => expect(location()).toContain('status.quarter=1'))
    await waitFor(() => expect(lastQuery(summary)).toEqual({ year: 2026, quarters: [1] }))
  })

  it('does not show the coming soon text for a 501 either', async () => {
    vi.spyOn(gateway.dashboard, 'summary').mockRejectedValue(
      new ApiError(501, { type: 'https://sales.neoine.test/problems/not-implemented', title: 'x', status: 501, detail: '아직 연결되지 않았습니다.' }),
    )
    await renderAt('/dashboard')

    expect(await screen.findByRole('alert')).toBeVisible()
    expect(screen.queryByText(/준비 중입니다/)).not.toBeInTheDocument()
  })

  it('keeps the previous numbers on screen while the next condition loads', async () => {
    const original = gateway.dashboard.summary.bind(gateway.dashboard)
    const { user, location } = await renderAt('/dashboard')
    const table = await screen.findByRole('table')
    expect(table).toBeVisible()
    let release: () => void = () => undefined
    const gate = new Promise<void>((resolve) => {
      release = resolve
    })
    vi.spyOn(gateway.dashboard, 'summary').mockImplementation(async (query) => {
      await gate
      return original(query)
    })

    await user.click(quarterButton(2))
    expect(location()).toContain('status.quarter=2')

    expect(screen.getByRole('table')).toBeVisible()
    expect(screen.queryByText('조건에 맞는 Deal이 없습니다.')).not.toBeInTheDocument()
    release()
    await waitFor(() => expect(gateway.dashboard.summary).toHaveBeenCalledTimes(1))
    expect(screen.getByRole('table')).toBeVisible()
  })
})
