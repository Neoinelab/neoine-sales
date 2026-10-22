import { screen, waitFor } from '@testing-library/react'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { gateway } from '../../../gateway'
import { ApiError } from '../../../shared/api/problem'
import { resetMock } from '../../../test/fake/default'
import { seedVendorId } from '../../../test/fixtures/vendors'
import { renderAt } from '../../../test/mockApp'

/**
 * Vendor 목록 조회 실패 시 목록 필터 계약(재리뷰 R-1).
 * - 필터 근처에 ErrorBanner(role="alert")를 보인다.
 * - URL의 vendor id가 조회 조건으로 쓰이는 동안 select는 '전체'가 아니라
 *   옵션 하나(`선택한 Vendor`)가 선택된 상태로 보인다.
 * - Solution 텍스트 조건은 Vendor 목록과 무관하게 그대로 쓰이고 입력란에 보인다.
 */
beforeEach(() => resetMock({ now: '2026-10-15T09:00:00+09:00' }))
afterEach(() => {
  vi.restoreAllMocks()
  resetMock({ now: null })
})

const failure = () =>
  new ApiError(500, { type: 'https://sales.neoine.test/problems/internal', title: 'x', status: 500, detail: 'Vendor 목록을 불러오지 못했습니다.' })
const lastQuery = (spy: ReturnType<typeof vi.spyOn>) => spy.mock.calls.at(-1)?.[0] as Record<string, unknown>

describe('목록 필터: Vendor 목록 조회 실패', () => {
  it('shows an error banner near the filters', async () => {
    vi.spyOn(gateway.vendors, 'list').mockRejectedValue(failure())
    await renderAt(`/deals?vendor=${seedVendorId('Silverfort')}`)

    expect(await screen.findByRole('alert')).toHaveTextContent('Vendor 목록을 불러오지 못했습니다.')
  })

  it('shows the url vendor as selected instead of all while the query keeps using it', async () => {
    vi.spyOn(gateway.vendors, 'list').mockRejectedValue(failure())
    const list = vi.spyOn(gateway.deals, 'list')
    await renderAt(`/deals?vendor=${seedVendorId('Silverfort')}`)
    await screen.findByRole('alert')

    await waitFor(() => expect(lastQuery(list).vendorId).toBe(seedVendorId('Silverfort')))
    expect(screen.getByLabelText('Vendor')).toHaveDisplayValue('선택한 Vendor')
  })

  it('keeps using the solution text and shows it in the input', async () => {
    vi.spyOn(gateway.vendors, 'list').mockRejectedValue(failure())
    const list = vi.spyOn(gateway.deals, 'list')
    await renderAt('/deals?solution=ITDR')
    await screen.findByRole('alert')

    await waitFor(() => expect(lastQuery(list).solution).toBe('ITDR'))
    expect(screen.getByLabelText('Solution')).toHaveValue('ITDR')
  })
})
