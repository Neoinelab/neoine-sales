import { screen, waitFor, within } from '@testing-library/react'
import { afterEach, describe, expect, it, vi } from 'vitest'
import { gateway } from '../../gateway'
import { seedVendorId } from '../../test/fixtures/vendors'
import { renderAt } from '../../test/mockApp'

/**
 * Forecast 필터의 표시와 조회 조건 일치 계약(리뷰 Minor 2).
 * Vendor 목록을 받은 뒤, 목록에 없는 vendor UUID는 'Vendor 전체'로 보일 뿐 아니라
 * 요약 조회 조건(vendorId)과 선택한 담당자의 Deal 목록 조회에서도 제외한다.
 * 목록을 받기 전에는 판단하지 않으므로 목록 로딩 뒤의 마지막 조회만 본다.
 */
afterEach(() => vi.restoreAllMocks())

const UNKNOWN = '99999999-9999-4999-8999-999999999999'

async function vendorsLoaded() {
  await within(await screen.findByLabelText('Vendor')).findByRole('option', { name: 'Okta' })
}
const lastQuery = (spy: ReturnType<typeof vi.spyOn>) => spy.mock.calls.at(-1)?.[0] as Record<string, unknown>

describe('Forecast 필터: 표시와 조건 일치', () => {
  it('drops an unregistered vendor id from the summary query', async () => {
    const summary = vi.spyOn(gateway.forecast, 'summary')
    await renderAt(`/forecast?year=2026&vendor=${UNKNOWN}`)
    await vendorsLoaded()

    await waitFor(() => expect(lastQuery(summary).vendorId).toBeUndefined())
    expect(screen.getByLabelText('Vendor')).toHaveDisplayValue('전체')
  })

  it('drops an unregistered vendor id from the deal list of the selected owner', async () => {
    const list = vi.spyOn(gateway.deals, 'list')
    await renderAt(`/forecast?year=2026&vendor=${UNKNOWN}&sel=u-kim`)
    await screen.findByRole('heading', { name: /선택한 담당자/ })
    await vendorsLoaded()

    await waitFor(() => expect(lastQuery(list)).toMatchObject({ ownerId: 'u-kim', year: 2026 }))
    await waitFor(() => expect(lastQuery(list).vendorId).toBeUndefined())
  })

  it('keeps a registered vendor id in the summary query', async () => {
    const summary = vi.spyOn(gateway.forecast, 'summary')
    await renderAt(`/forecast?year=2026&vendor=${seedVendorId('Okta')}`)
    await vendorsLoaded()

    await waitFor(() => expect(screen.getByLabelText('Vendor')).toHaveDisplayValue('Okta'))
    expect(lastQuery(summary).vendorId).toBe(seedVendorId('Okta'))
  })
})
