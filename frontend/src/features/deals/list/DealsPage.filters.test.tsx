import { fireEvent, screen, waitFor, within } from '@testing-library/react'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { gateway } from '../../../gateway'
import { ApiError } from '../../../shared/api/problem'
import { resetMock } from '../../../test/fake/default'
import { renderAt } from '../../../test/mockApp'
import { seedSolutionId, seedVendorId } from '../../../test/fixtures/vendors'
import { dealInput } from '../../../test/fake/testing'
import { dataRows } from './testHelpers'
import { USER_ID } from '../../../test/fake/seed/ids'

describe('필터와 정렬 (T-LIST-05~09)', () => {
  it('filters by keyword on submit and keeps it in the URL', async () => {
    const { user, location } = await renderAt('/deals')
    await screen.findByRole('row', { name: /한빛은행 ITDR 도입/ })
    await user.type(screen.getByLabelText('키워드'), '한빛은행')
    await user.click(screen.getByRole('button', { name: '검색' }))
    expect(location()).toBe(`/deals?q=${encodeURIComponent('한빛은행')}`)
    await screen.findByRole('row', { name: /한빛은행 PAM/ })
    expect(dataRows()).toHaveLength(3)
  })

  it('filters by owner', async () => {
    const { user, location } = await renderAt('/deals')
    await screen.findByRole('row', { name: /한빛은행 ITDR 도입/ })
    await user.selectOptions(await screen.findByLabelText('담당자'), '박영업')
    await screen.findByRole('row', { name: /미래전자 EDR 교체/ })
    expect(location()).toContain(`owner=${USER_ID.park}`)
    expect(dataRows()).toHaveLength(6)
  })

  it('offers resigned owners in the owner filter', async () => {
    const { user } = await renderAt('/deals')
    const owner = await screen.findByLabelText('담당자')
    await within(owner).findByRole('option', { name: '강퇴사(퇴사)' })
    await user.selectOptions(owner, '강퇴사(퇴사)')
    await screen.findByRole('row', { name: /한빛은행 PAM/ })
    expect(dataRows()).toHaveLength(1)
  })

  it('filters by vendor, status and forecast', async () => {
    const { user, location } = await renderAt('/deals')
    await screen.findByRole('row', { name: /한빛은행 ITDR 도입/ })
    const vendor = await screen.findByLabelText('Vendor')
    await within(vendor).findByRole('option', { name: 'Silverfort' })
    await user.selectOptions(vendor, 'Silverfort')
    await screen.findByRole('row', { name: /도담건설 MFA/ })
    expect(dataRows()).toHaveLength(7)
    expect(location()).toContain(`vendor=${seedVendorId('Silverfort')}`)

    await user.selectOptions(screen.getByLabelText('Status'), '계약완료')
    await screen.findByText(/도담건설 MFA/)
    expect(dataRows()).toHaveLength(1)
    expect(location()).toContain('status=contract_completed')

    await user.selectOptions(screen.getByLabelText('Status'), '전체')
    await user.selectOptions(screen.getByLabelText('Vendor'), '전체')
    await user.selectOptions(screen.getByLabelText('Forecast'), 'Lost')
    await screen.findByRole('row', { name: /새론병원 SSO/ })
    expect(dataRows()).toHaveLength(1)
    expect(location()).toContain('forecast=lost')
  })

  it('filters by solution', async () => {
    const { user, location } = await renderAt('/deals')
    const solution = await screen.findByLabelText('Solution')
    await within(solution).findByRole('option', { name: 'Silverfort / ITDR' })
    await user.selectOptions(solution, 'Silverfort / ITDR')
    await screen.findByRole('row', { name: /미래전자 ITDR/ })
    expect(dataRows()).toHaveLength(4)
    expect(location()).toContain(`solution=${seedSolutionId('Silverfort', 'ITDR')}`)
  })

  it('puts year and quarter in the URL', async () => {
    const { user, location } = await renderAt('/deals')
    await screen.findByRole('row', { name: /한빛은행 ITDR 도입/ })
    const year = String(new Date().getFullYear())
    await user.selectOptions(screen.getByLabelText('연도'), year)
    await user.selectOptions(screen.getByLabelText('Quarter'), 'Q4')
    expect(location()).toContain(`year=${year}`)
    expect(location()).toContain('quarter=4')
  })

  it('puts the month in the URL and clears the quarter (P6 Q3-b)', async () => {
    const { user, location } = await renderAt('/deals?year=2026&quarter=4')
    await screen.findByRole('row', { name: /한빛은행 ITDR 도입/ })

    await user.selectOptions(screen.getByLabelText('월'), '3월')

    expect(location()).toContain('month=3')
    expect(location()).not.toContain('quarter=')
  })

  it('clears the month when a quarter is chosen', async () => {
    const { user, location } = await renderAt('/deals?year=2026&month=11')
    await screen.findByLabelText('월')

    await user.selectOptions(screen.getByLabelText('Quarter'), 'Q4')

    expect(location()).toContain('quarter=4')
    expect(location()).not.toContain('month=')
  })

  it('restores the month control from the URL and lists only that month', async () => {
    const { client } = await renderAt('/deals?year=2028&month=2')
    await screen.findByLabelText('월')
    await gateway.deals.create(dealInput(USER_ID.kim, { name: '월필터 2월', revenueDate: '2028-02-10' }))
    await gateway.deals.create(dealInput(USER_ID.kim, { name: '월필터 3월', revenueDate: '2028-03-10' }))
    await client.invalidateQueries()

    expect(await screen.findByRole('row', { name: /월필터 2월/ })).toBeVisible()
    expect(screen.getByLabelText('월')).toHaveDisplayValue('2월')
    expect(screen.queryByRole('row', { name: /월필터 3월/ })).not.toBeInTheDocument()
    expect(dataRows()).toHaveLength(1)
  })

  it('shows only my deals with the my-deals toggle and removes the filter when turned off', async () => {
    const { user, location } = await renderAt('/deals')
    await screen.findByRole('row', { name: /한빛은행 ITDR 도입/ })
    await user.click(screen.getByRole('checkbox', { name: '내 딜만' }))
    expect(location()).toContain('mine=1')
    await screen.findByRole('row', { name: /새론병원 SSO/ })
    expect(dataRows()).toHaveLength(8)
    await user.click(screen.getByRole('checkbox', { name: '내 딜만' }))
    expect(location()).toBe('/deals')
  })

  it('restores every control from the URL, as when coming back from a detail page', async () => {
    await renderAt('/deals?mine=1&status=contract_completed&sort=name&order=asc')
    await screen.findByRole('row', { name: /청명대학교 SSO\/MFA/ })
    expect(dataRows()).toHaveLength(2)
    expect(screen.getByRole('checkbox', { name: '내 딜만' })).toBeChecked()
    expect(screen.getByLabelText('Status')).toHaveDisplayValue('계약완료')
  })

  it('clears every condition with the reset button', async () => {
    const { user, location } = await renderAt(`/deals?q=한빛&vendor=${seedVendorId('Okta')}&sort=name&order=asc`)
    await user.click(await screen.findByRole('button', { name: '초기화' }))
    expect(location()).toBe('/deals')
    await screen.findByRole('row', { name: /한빛은행 ITDR 도입/ })
    expect(screen.getByLabelText('키워드')).toHaveValue('')
  })

  it('sorts by Expected Close and flips the direction', async () => {
    const { user, location } = await renderAt('/deals')
    await screen.findByRole('row', { name: /한빛은행 ITDR 도입/ })
    await user.click(screen.getByRole('button', { name: 'Expected Close' }))
    expect(location()).toContain('sort=revenueDate')
    await waitFor(() => expect(screen.getByRole('columnheader', { name: 'Expected Close' })).toHaveAttribute('aria-sort', 'ascending'))
    expect(dataRows()[0]).toHaveTextContent('도담건설 MFA')
    await user.click(screen.getByRole('button', { name: 'Expected Close' }))
    await waitFor(() => expect(screen.getByRole('columnheader', { name: 'Expected Close' })).toHaveAttribute('aria-sort', 'descending'))
    expect(dataRows()[0]).toHaveTextContent('대한제조 NGFW')
  })

  it('sorts by amount with the largest first and marks the default sort on the last update', async () => {
    const { user } = await renderAt('/deals')
    await screen.findByRole('row', { name: /한빛은행 ITDR 도입/ })
    expect(screen.getByRole('columnheader', { name: '최종 업데이트' })).toHaveAttribute('aria-sort', 'descending')
    await user.click(screen.getByRole('button', { name: '금액(단위:천원)' }))
    await waitFor(() => expect(screen.getByRole('columnheader', { name: '금액(단위:천원)' })).toHaveAttribute('aria-sort', 'descending'))
    expect(dataRows()[0]).toHaveTextContent('한빛은행 ITDR 도입')
  })

  it('tells that nothing matches when a condition finds no deal', async () => {
    await renderAt('/deals?q=없는이름')
    expect(await screen.findByText('조건에 맞는 Deal이 없습니다.')).toBeVisible()
  })
})

/** 최종 업데이트 기간(AC-13~23). Fake 시계를 고정하고, 기대 결과는 같은 Fake 게이트웨이의 날짜 조회로 만든다. */
describe('최종 업데이트 기간 필터', () => {
  const NOW = '2026-10-15T09:00:00+09:00'
  const TWO_WEEKS = { from: '2026-10-01', to: '2026-10-15' }
  const THREE_MONTHS = { from: '2026-07-15', to: '2026-10-15' }

  beforeEach(() => resetMock({ now: NOW }))
  afterEach(() => {
    vi.restoreAllMocks()
    resetMock({ now: null })
  })

  const search = (location: string) => new URLSearchParams(location.split('?')[1] ?? '')
  const expectedIn = async (range: { from?: string; to?: string }) =>
    gateway.deals.list({ updatedFrom: range.from, updatedTo: range.to, limit: 100 })

  async function waitForRows(total: number) {
    await waitFor(() => expect(dataRows()).toHaveLength(total))
  }

  it('no longer shows the Expected Close period inputs and offers seven options', async () => {
    await renderAt('/deals')
    await screen.findByRole('row', { name: /한빛은행 ITDR 도입/ })

    expect(screen.queryByLabelText('기간 시작')).not.toBeInTheDocument()
    expect(screen.queryByLabelText('기간 끝')).not.toBeInTheDocument()
    const select = screen.getByLabelText('최종 업데이트')
    expect(select).toHaveDisplayValue('전체')
    const labels = within(select).getAllByRole('option').map((o) => o.textContent)
    expect(labels).toEqual(['전체', '최근 2주', '최근 1개월', '최근 2개월', '최근 3개월', '최근 6개월', '직접 지정'])
    expect(screen.queryByLabelText('시작일')).not.toBeInTheDocument()
    expect(screen.queryByLabelText('종료일')).not.toBeInTheDocument()
  })

  it('filters by the recent-two-weeks preset and puts the server dates in the URL', async () => {
    const { user, location } = await renderAt('/deals?page=2')
    await waitFor(() => expect(dataRows().length).toBeGreaterThan(0))
    const all = await expectedIn({})
    const expected = await expectedIn(TWO_WEEKS)
    expect(expected.total).toBeGreaterThan(0)
    expect(expected.total).toBeLessThan(all.total)

    const select = await screen.findByLabelText('최종 업데이트')
    await waitFor(() => expect(within(select).getByRole('option', { name: '최근 2주' })).toBeEnabled())
    await user.selectOptions(select, '최근 2주')

    await waitForRows(expected.total)
    expect(search(location()).get('updated_from')).toBe(TWO_WEEKS.from)
    expect(search(location()).get('updated_to')).toBe(TWO_WEEKS.to)
    expect(search(location()).get('page')).toBeNull()
    expect(screen.getByLabelText('최종 업데이트')).toHaveDisplayValue('최근 2주')
    expect(search(location()).has('updated_period')).toBe(false)
  })

  it('uses the dates the server resolved for a longer preset', async () => {
    const { user, location } = await renderAt('/deals')
    await screen.findByRole('row', { name: /한빛은행 ITDR 도입/ })
    const select = await screen.findByLabelText('최종 업데이트')
    await waitFor(() => expect(within(select).getByRole('option', { name: '최근 3개월' })).toBeEnabled())

    await user.selectOptions(select, '최근 3개월')

    await waitFor(() => expect(search(location()).get('updated_from')).toBe(THREE_MONTHS.from))
    expect(search(location()).get('updated_to')).toBe(THREE_MONTHS.to)
  })

  it('clears the period with 전체 and with the reset button', async () => {
    const { user, location } = await renderAt(`/deals?updated_from=${TWO_WEEKS.from}&updated_to=${TWO_WEEKS.to}&status=prospecting`)
    const select = await screen.findByLabelText('최종 업데이트')
    await waitFor(() => expect(select).toHaveDisplayValue('최근 2주'))

    await user.selectOptions(select, '전체')
    expect(search(location()).has('updated_from')).toBe(false)
    expect(search(location()).has('updated_to')).toBe(false)
    expect(search(location()).get('status')).toBe('prospecting')

    await user.selectOptions(screen.getByLabelText('최종 업데이트'), '최근 2주')
    await waitFor(() => expect(search(location()).get('updated_from')).toBe(TWO_WEEKS.from))
    await user.click(screen.getByRole('button', { name: '초기화' }))

    expect(location()).toBe('/deals')
    expect(screen.getByLabelText('최종 업데이트')).toHaveDisplayValue('전체')
    expect(screen.queryByLabelText('시작일')).not.toBeInTheDocument()
  })

  it('shows date inputs for 직접 지정, prefilled from the preset without changing the URL', async () => {
    const { user, location } = await renderAt(`/deals?updated_from=${TWO_WEEKS.from}&updated_to=${TWO_WEEKS.to}`)
    const select = await screen.findByLabelText('최종 업데이트')
    await waitFor(() => expect(select).toHaveDisplayValue('최근 2주'))
    const before = location()

    await user.selectOptions(select, '직접 지정')

    expect(screen.getByLabelText('시작일')).toHaveValue(TWO_WEEKS.from)
    expect(screen.getByLabelText('종료일')).toHaveValue(TWO_WEEKS.to)
    expect(location()).toBe(before)
  })

  it('opens empty date inputs from 전체 and filters with only a start date, then clears it', async () => {
    const { user, location } = await renderAt('/deals')
    await screen.findByRole('row', { name: /한빛은행 ITDR 도입/ })
    await user.selectOptions(await screen.findByLabelText('최종 업데이트'), '직접 지정')
    expect(screen.getByLabelText('시작일')).toHaveValue('')
    const since = await expectedIn({ from: '2026-10-01' })

    fireEvent.change(screen.getByLabelText('시작일'), { target: { value: '2026-10-01' } })

    await waitForRows(Math.min(since.total, 20))
    expect(search(location()).get('updated_from')).toBe('2026-10-01')
    expect(search(location()).has('updated_to')).toBe(false)
    expect(screen.getByLabelText('최종 업데이트')).toHaveDisplayValue('직접 지정')

    fireEvent.change(screen.getByLabelText('시작일'), { target: { value: '' } })
    await waitFor(() => expect(search(location()).has('updated_from')).toBe(false))
  })

  it('shows the server error when the start date is after the end date', async () => {
    const { user, location } = await renderAt('/deals')
    await screen.findByRole('row', { name: /한빛은행 ITDR 도입/ })
    await user.selectOptions(await screen.findByLabelText('최종 업데이트'), '직접 지정')

    fireEvent.change(screen.getByLabelText('시작일'), { target: { value: '2026-10-10' } })
    fireEvent.change(screen.getByLabelText('종료일'), { target: { value: '2026-10-01' } })

    expect(await screen.findByRole('alert')).toHaveTextContent('최종 업데이트 기간의 시작은 끝보다 늦을 수 없습니다')
    expect(search(location()).get('updated_from')).toBe('2026-10-10')
    expect(search(location()).get('updated_to')).toBe('2026-10-01')
  })

  it('restores the preset from matching dates in the URL', async () => {
    await renderAt(`/deals?updated_from=${TWO_WEEKS.from}&updated_to=${TWO_WEEKS.to}`)
    const select = await screen.findByLabelText('최종 업데이트')

    await waitFor(() => expect(select).toHaveDisplayValue('최근 2주'))
    expect(screen.queryByLabelText('시작일')).not.toBeInTheDocument()
  })

  it('shows 직접 지정 with the dates when they match no preset of today', async () => {
    await renderAt('/deals?updated_from=2026-10-02&updated_to=2026-10-15')
    const select = await screen.findByLabelText('최종 업데이트')

    await waitFor(() => expect(select).toHaveDisplayValue('직접 지정'))
    expect(screen.getByLabelText('시작일')).toHaveValue('2026-10-02')
    expect(screen.getByLabelText('종료일')).toHaveValue('2026-10-15')
  })

  it('shows 직접 지정 when only one side is in the URL', async () => {
    await renderAt('/deals?updated_to=2026-10-15')
    const select = await screen.findByLabelText('최종 업데이트')

    await waitFor(() => expect(select).toHaveDisplayValue('직접 지정'))
    expect(screen.getByLabelText('시작일')).toHaveValue('')
    expect(screen.getByLabelText('종료일')).toHaveValue('2026-10-15')
  })

  it('ignores a malformed updated date in the URL for the query', async () => {
    const list = vi.spyOn(gateway.deals, 'list')
    await renderAt('/deals?updated_from=2026-02-30&updated_to=abc')
    await screen.findByRole('row', { name: /한빛은행 ITDR 도입/ })

    const query = list.mock.calls.at(-1)?.[0]
    expect(query?.updatedFrom).toBeUndefined()
    expect(query?.updatedTo).toBeUndefined()
  })

  it('ignores the old from/to keys: no Expected Close period and no filter marker', async () => {
    const list = vi.spyOn(gateway.deals, 'list')
    await renderAt('/deals?from=2099-01-01&to=2099-12-31')
    await screen.findByRole('row', { name: /한빛은행 ITDR 도입/ })

    expect(Object.keys(list.mock.calls.at(-1)?.[0] ?? {}).sort()).toEqual(['limit', 'offset'])
    expect(screen.getByLabelText('최종 업데이트')).toHaveDisplayValue('전체')
  })

  it('keeps using the URL dates when the presets fail to load', async () => {
    const failure = new ApiError(500, {
      type: 'https://sales.neoine.test/problems/internal',
      title: 'x',
      status: 500,
      detail: '기간 정보를 불러오지 못했습니다.',
    })
    vi.spyOn(gateway.deals, 'updatedPeriods').mockRejectedValue(failure)
    const list = vi.spyOn(gateway.deals, 'list')
    await renderAt(`/deals?updated_from=${TWO_WEEKS.from}&updated_to=${TWO_WEEKS.to}`)

    expect(await screen.findByRole('alert')).toHaveTextContent('기간 정보를 불러오지 못했습니다.')
    await waitFor(() => expect(list.mock.calls.at(-1)?.[0]).toMatchObject({ updatedFrom: TWO_WEEKS.from, updatedTo: TWO_WEEKS.to }))
    const select = screen.getByLabelText('최종 업데이트')
    expect(select).toHaveDisplayValue('직접 지정')
    expect(screen.getByLabelText('시작일')).toHaveValue(TWO_WEEKS.from)
    expect(within(select).getByRole('option', { name: '최근 2주' })).toBeDisabled()
    expect(within(select).getByRole('option', { name: '최근 6개월' })).toBeDisabled()
  })

  it('goes back to 전체 and hides the date inputs when browser back removes the custom dates', async () => {
    const { user, location, goTo } = await renderAt('/deals')
    await screen.findByRole('row', { name: /한빛은행 ITDR 도입/ })
    await user.selectOptions(await screen.findByLabelText('최종 업데이트'), '직접 지정')
    fireEvent.change(screen.getByLabelText('시작일'), { target: { value: '2026-10-01' } })
    await waitFor(() => expect(search(location()).get('updated_from')).toBe('2026-10-01'))

    goTo(-1)

    await waitFor(() => expect(location()).toBe('/deals'))
    await waitFor(() => expect(screen.getByLabelText('최종 업데이트')).toHaveDisplayValue('전체'))
    expect(screen.queryByLabelText('시작일')).not.toBeInTheDocument()
    expect(screen.queryByLabelText('종료일')).not.toBeInTheDocument()
  })

  it('shows the matching preset when browser back returns the custom dates to a preset range', async () => {
    const { user, location, goTo } = await renderAt(`/deals?updated_from=${TWO_WEEKS.from}&updated_to=${TWO_WEEKS.to}`)
    const select = await screen.findByLabelText('최종 업데이트')
    await waitFor(() => expect(select).toHaveDisplayValue('최근 2주'))
    await user.selectOptions(select, '직접 지정')
    fireEvent.change(screen.getByLabelText('종료일'), { target: { value: '2026-10-14' } })
    await waitFor(() => expect(search(location()).get('updated_to')).toBe('2026-10-14'))
    expect(screen.getByLabelText('최종 업데이트')).toHaveDisplayValue('직접 지정')

    goTo(-1)

    await waitFor(() => expect(search(location()).get('updated_to')).toBe(TWO_WEEKS.to))
    await waitFor(() => expect(screen.getByLabelText('최종 업데이트')).toHaveDisplayValue('최근 2주'))
    expect(screen.queryByLabelText('시작일')).not.toBeInTheDocument()
  })

  it('asks the server for the periods again when a preset is chosen and uses the new dates', async () => {
    // 첫 응답은 화면을 열 때의 날짜(10-15), 두 번째부터는 자정이 지난 날짜(10-16)로 응답한다.
    const original = gateway.deals.updatedPeriods.bind(gateway.deals)
    const nextDay = { from: '2026-10-02', to: '2026-10-16' }
    const spy = vi.spyOn(gateway.deals, 'updatedPeriods').mockImplementation(async () => {
      if (spy.mock.calls.length === 1) return original()
      const first = await original()
      return {
        today: nextDay.to,
        periods: first.periods.map((p) => (p.key === '2w' ? { ...p, ...nextDay } : p)),
        upcoming: first.upcoming,
      }
    })
    const { user, location } = await renderAt('/deals')
    await screen.findByRole('row', { name: /한빛은행 ITDR 도입/ })
    const select = await screen.findByLabelText('최종 업데이트')
    await waitFor(() => expect(within(select).getByRole('option', { name: '최근 2주' })).toBeEnabled())
    const callsBeforeChoosing = spy.mock.calls.length

    await user.selectOptions(select, '최근 2주')

    await waitFor(() => expect(search(location()).get('updated_from')).toBe(nextDay.from))
    expect(search(location()).get('updated_to')).toBe(nextDay.to)
    expect(spy.mock.calls.length).toBeGreaterThan(callsBeforeChoosing)
  })

  it('keeps the URL dates and shows the error when asking for the periods again fails on choosing a preset', async () => {
    const failure = new ApiError(500, {
      type: 'https://sales.neoine.test/problems/internal',
      title: 'x',
      status: 500,
      detail: '기간 정보를 다시 불러오지 못했습니다.',
    })
    const original = gateway.deals.updatedPeriods.bind(gateway.deals)
    let failing = false
    vi.spyOn(gateway.deals, 'updatedPeriods').mockImplementation(async () => {
      if (failing) throw failure
      return original()
    })
    const { user, location } = await renderAt('/deals')
    await screen.findByRole('row', { name: /한빛은행 ITDR 도입/ })
    const select = await screen.findByLabelText('최종 업데이트')
    await waitFor(() => expect(within(select).getByRole('option', { name: '최근 2주' })).toBeEnabled())
    failing = true

    await user.selectOptions(select, '최근 2주')

    // 같은 쿼리를 쓰는 화면 쪽 배너와 겹쳐 alert가 둘일 수 있어 모두 모아 본다.
    const alerts = await screen.findAllByRole('alert', undefined, { timeout: 15000 })
    expect(alerts.map((a) => a.textContent)).toContain('기간 정보를 다시 불러오지 못했습니다.')
    expect(search(location()).has('updated_from')).toBe(false)
    expect(search(location()).has('updated_to')).toBe(false)
    // 재시도 횟수·간격은 구현에 맡기므로 재시도가 끝날 때까지 넉넉히 기다린다.
  }, 20000)
})
