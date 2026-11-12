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
  // 테스트 코드: FC-066
  it('Vendor 목록을 읽지 못하면 필터 근처에 오류 배너를 보인다', async () => {
    // given: 실패하는 Vendor 목록 조회
    vi.spyOn(gateway.vendors, 'list').mockRejectedValue(failure())
    // when: Vendor id가 담긴 URL로 화면을 연다
    await renderAt(`/forecast?year=2026&vendor=${seedVendorId('Okta')}`)

    // then: 서버 문구가 배너로 보인다
    expect(await screen.findByRole('alert')).toHaveTextContent('Vendor 목록을 불러오지 못했습니다.')
  })

  // 테스트 코드: FC-066
  it('Vendor 목록 실패 시 "선택한 Vendor"를 선택된 상태로 보이고 URL id로 조회한다', async () => {
    // given: 실패하는 Vendor 목록 조회와 요약 조회 스파이
    vi.spyOn(gateway.vendors, 'list').mockRejectedValue(failure())
    const summary = vi.spyOn(gateway.forecast, 'summary')
    // when: Vendor id가 담긴 URL로 화면을 연다
    await renderAt(`/forecast?year=2026&vendor=${seedVendorId('Okta')}`)
    // then: 마지막 요약 조회에 URL의 vendorId가 담기고 Vendor 칸이 "선택한 Vendor"다
    await screen.findByRole('alert')

    await waitFor(() => expect(summary.mock.calls.at(-1)?.[0]).toMatchObject({ vendorId: seedVendorId('Okta') }))
    expect(screen.getByLabelText('Vendor')).toHaveDisplayValue('선택한 Vendor')
  })
})
