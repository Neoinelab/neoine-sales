import { screen, waitFor } from '@testing-library/react'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { gateway } from '../../gateway'
import { ApiError } from '../../shared/api/problem'
import { resetMock } from '../../test/fake/default'
import { seedVendorId } from '../../test/fixtures/vendors'
import { renderAt } from '../../test/mockApp'
import { lastQuery, NOW } from './testHelpers'

/**
 * Vendor 목록을 읽는 동안·읽지 못했을 때의 Dashboard 필터: 목록이 없으면 URL의 Vendor id를 조회에 쓰고
 * Vendor 칸은 "전체"가 아니라 "선택한 Vendor" 선택지가 선택된 상태로 보인다(DSH-R16).
 */

beforeEach(() => resetMock({ now: NOW }))
afterEach(() => {
  vi.restoreAllMocks()
  resetMock({ now: null })
})

const failure = () =>
  new ApiError(500, { type: 'https://sales.neoine.test/problems/internal', title: 'x', status: 500, detail: 'Vendor 목록을 불러오지 못했습니다.' })

describe('Dashboard 필터: Vendor 목록을 읽는 동안과 실패', () => {
  // 테스트 코드: DSH-036
  it('Vendor 목록을 읽는 동안에는 "선택한 Vendor"가 선택된 채 URL id로 조회한다', async () => {
    // given: 끝나지 않는 Vendor 목록 조회와 요약 조회 스파이
    vi.spyOn(gateway.vendors, 'list').mockReturnValue(new Promise(() => {}))
    const summary = vi.spyOn(gateway.dashboard, 'summary')

    // when: 등록된 Vendor id가 담긴 주소를 연다
    await renderAt(`/dashboard?year=2026&vendor=${seedVendorId('Okta')}`)
    await screen.findByLabelText('Vendor')

    // then: 조회에 그 Vendor id가 실리고 Vendor 칸은 "선택한 Vendor"다
    await waitFor(() => expect(lastQuery(summary)).toMatchObject({ vendorId: seedVendorId('Okta') }))
    expect(screen.getByLabelText('Vendor')).toHaveDisplayValue('선택한 Vendor')
  })

  // 테스트 코드: DSH-036
  it('Vendor 목록을 읽지 못하면 "선택한 Vendor"가 선택된 채 URL id로 조회하고 오류 배너를 보인다', async () => {
    // given: 실패하는 Vendor 목록 조회와 요약 조회 스파이
    vi.spyOn(gateway.vendors, 'list').mockRejectedValue(failure())
    const summary = vi.spyOn(gateway.dashboard, 'summary')

    // when: 등록된 Vendor id가 담긴 주소를 연다
    await renderAt(`/dashboard?year=2026&vendor=${seedVendorId('Okta')}`)

    // then: 필터 안에 서버 문구의 오류 배너가 보인다
    expect(await screen.findByRole('alert')).toHaveTextContent('Vendor 목록을 불러오지 못했습니다.')
    // then: 조회에 그 Vendor id가 실리고 Vendor 칸은 "선택한 Vendor"다
    await waitFor(() => expect(lastQuery(summary)).toMatchObject({ vendorId: seedVendorId('Okta') }))
    expect(screen.getByLabelText('Vendor')).toHaveDisplayValue('선택한 Vendor')
  })
})
