import { screen, waitFor } from '@testing-library/react'
import { afterEach, describe, expect, it, vi } from 'vitest'
import { gateway } from '../../gateway'
import { ApiError } from '../../shared/api/problem'
import { seedVendorId } from '../../test/fixtures/vendors'
import { renderAt } from '../../test/mockApp'

/**
 * Vendor 목록 조회 실패 시 Forecast 필터 계약(재리뷰 R-1).
 * ErrorBanner(role="alert")를 보이고, URL의 vendor id가 요약 조회 조건으로 쓰이는 동안
 * Vendor select는 '전체'가 아니라 `선택한 Vendor` 옵션이 선택된 상태로 보인다.
 */
afterEach(() => vi.restoreAllMocks())

const failure = () =>
  new ApiError(500, { type: 'https://sales.neoine.test/problems/internal', title: 'x', status: 500, detail: 'Vendor 목록을 불러오지 못했습니다.' })

describe('Forecast 필터: Vendor 목록 조회 실패', () => {
  it('shows an error banner near the filters', async () => {
    vi.spyOn(gateway.vendors, 'list').mockRejectedValue(failure())
    await renderAt(`/forecast?year=2026&vendor=${seedVendorId('Okta')}`)

    expect(await screen.findByRole('alert')).toHaveTextContent('Vendor 목록을 불러오지 못했습니다.')
  })

  it('shows the url vendor as selected instead of all while the summary query keeps using it', async () => {
    vi.spyOn(gateway.vendors, 'list').mockRejectedValue(failure())
    const summary = vi.spyOn(gateway.forecast, 'summary')
    await renderAt(`/forecast?year=2026&vendor=${seedVendorId('Okta')}`)
    await screen.findByRole('alert')

    await waitFor(() => expect(summary.mock.calls.at(-1)?.[0]).toMatchObject({ vendorId: seedVendorId('Okta') }))
    expect(screen.getByLabelText('Vendor')).toHaveDisplayValue('선택한 Vendor')
  })
})
