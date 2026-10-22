import { screen, waitFor, within } from '@testing-library/react'
import { afterEach, describe, expect, it, vi } from 'vitest'
import { gateway } from '../../../gateway'
import { renderAt } from '../../../test/mockApp'
import { dataRows } from './testHelpers'

/**
 * Deal 목록의 "Forecast 구분" 필터(Dashboard AC-19). URL 키 `outcome=open|won|lost|not_lost`로 저장·기억·초기화되고
 * 모르는 값은 '전체'로 보이며 조회에 쓰이지 않는다. 시드(샘플 픽스처): '새론병원 SSO'만 Lost, '새론병원 PAM'은 Best(Open).
 */

afterEach(() => vi.restoreAllMocks())

const lastQuery = (spy: ReturnType<typeof vi.spyOn>) => spy.mock.calls.at(-1)?.[0] as Record<string, unknown>

describe('Forecast 구분 필터 (AC-19)', () => {
  it('offers all, open, won, lost and not lost, next to the Forecast filter', async () => {
    await renderAt('/deals')
    await screen.findByRole('row', { name: /한빛은행 ITDR 도입/ })

    const select = screen.getByLabelText('Forecast 구분')
    const labels = within(select)
      .getAllByRole('option')
      .map((o) => o.textContent)

    expect(labels).toEqual(['전체', 'Open', 'Won', 'Lost', 'Lost 제외'])
    expect(select).toHaveDisplayValue('전체')
  })

  it('does not take over the Forecast filter label', async () => {
    await renderAt('/deals')
    await screen.findByRole('row', { name: /한빛은행 ITDR 도입/ })

    expect(screen.getByLabelText('Forecast')).not.toBe(screen.getByLabelText('Forecast 구분'))
  })

  it.each([
    ['Open', 'open'],
    ['Won', 'won'],
    ['Lost', 'lost'],
    ['Lost 제외', 'not_lost'],
  ])('puts %s in the URL as outcome=%s and sends it as forecastOutcome', async (label, wire) => {
    const list = vi.spyOn(gateway.deals, 'list')
    const { user, location } = await renderAt('/deals')
    await screen.findByRole('row', { name: /한빛은행 ITDR 도입/ })

    await user.selectOptions(screen.getByLabelText('Forecast 구분'), label)

    await waitFor(() => expect(location()).toContain(`outcome=${wire}`))
    await waitFor(() => expect(lastQuery(list)).toMatchObject({ forecastOutcome: wire }))
  })

  it('lists only the lost deal for Lost', async () => {
    const { user } = await renderAt('/deals')
    await screen.findByRole('row', { name: /한빛은행 ITDR 도입/ })

    await user.selectOptions(screen.getByLabelText('Forecast 구분'), 'Lost')

    await screen.findByRole('row', { name: /새론병원 SSO/ })
    await waitFor(() => expect(dataRows()).toHaveLength(1))
  })

  it('hides the lost deal for Lost 제외 and keeps the open one', async () => {
    await renderAt('/deals?outcome=not_lost&q=%EC%83%88%EB%A1%A0%EB%B3%91%EC%9B%90')

    await screen.findByRole('row', { name: /새론병원 PAM/ })
    expect(screen.queryByRole('row', { name: /새론병원 SSO/ })).not.toBeInTheDocument()
  })

  it('shows the chosen value when the page opens with the URL', async () => {
    await renderAt('/deals?outcome=not_lost')

    expect(await screen.findByLabelText('Forecast 구분')).toHaveDisplayValue('Lost 제외')
  })

  it('removes outcome from the URL when it is set back to all', async () => {
    const { user, location } = await renderAt('/deals?outcome=open&year=2026')
    await screen.findByLabelText('Forecast 구분')

    await user.selectOptions(screen.getByLabelText('Forecast 구분'), '전체')

    await waitFor(() => expect(location()).not.toContain('outcome'))
    expect(location()).toContain('year=2026')
  })

  it('combines with the Forecast filter by AND', async () => {
    const { user } = await renderAt('/deals?outcome=not_lost')
    await screen.findByLabelText('Forecast 구분')
    // Forecast 선택지는 코드 목록이 도착한 뒤에 채워진다.
    await within(screen.getByLabelText('Forecast')).findByRole('option', { name: 'Lost' })

    await user.selectOptions(screen.getByLabelText('Forecast'), 'Lost')

    expect(await screen.findByText('조건에 맞는 Deal이 없습니다.')).toBeVisible()
  })

  it('is cleared by the reset button together with the other filters', async () => {
    const { user, location } = await renderAt('/deals?outcome=lost&year=2026')
    await screen.findByRole('row', { name: /새론병원 SSO/ })

    await user.click(screen.getByRole('button', { name: '초기화' }))

    await waitFor(() => expect(location()).toBe('/deals'))
    expect(screen.getByLabelText('Forecast 구분')).toHaveDisplayValue('전체')
  })

  it('treats outcome as an active filter in the empty message', async () => {
    await renderAt('/deals?outcome=won&q=%EC%83%88%EB%A1%A0%EB%B3%91%EC%9B%90')

    expect(await screen.findByText('조건에 맞는 Deal이 없습니다.')).toBeVisible()
  })

  it.each(['foo', 'OPEN', 'not-lost', ''])('shows all and does not query with the unknown value %j', async (value) => {
    const list = vi.spyOn(gateway.deals, 'list')
    await renderAt(`/deals?outcome=${encodeURIComponent(value)}`)

    expect(await screen.findByLabelText('Forecast 구분')).toHaveDisplayValue('전체')
    await screen.findByRole('row', { name: /한빛은행 ITDR 도입/ })
    expect(lastQuery(list)).not.toHaveProperty('forecastOutcome')
  })
})
