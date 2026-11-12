import { screen, waitFor, within } from '@testing-library/react'
import { afterEach, describe, expect, it, vi } from 'vitest'
import { gateway } from '../../gateway'
import { seedVendorId } from '../../test/fixtures/vendors'
import { renderAt } from '../../test/mockApp'
import { NO_SUCH_ID, USER_ID } from '../../test/fake/seed/ids'

/**
 * Forecast 필터의 표시와 조회 조건 일치 계약.
 * Vendor 목록을 받은 뒤, 목록에 없는 정수 vendor id는 'Vendor 전체'로 보일 뿐 아니라
 * 요약 조회 조건(vendorId)과 선택한 담당자의 Deal 목록 조회에서도 제외한다.
 * 목록을 받기 전에는 판단하지 않으므로 목록 로딩 뒤의 마지막 조회만 본다.
 */
afterEach(() => vi.restoreAllMocks())

/** 서버 허용 범위 안의 정수지만 어떤 Vendor도 갖지 않은 id. */
const UNKNOWN = NO_SUCH_ID

async function vendorsLoaded() {
  await within(await screen.findByLabelText('Vendor')).findByRole('option', { name: 'Okta' })
}
const lastQuery = (spy: ReturnType<typeof vi.spyOn>) => spy.mock.calls.at(-1)?.[0] as Record<string, unknown>

describe('Forecast 필터: 표시와 조건 일치', () => {
  // 테스트 코드: FC-065
  it('등록되지 않은 Vendor id는 요약 조회 조건에서 뺀다', async () => {
    // given: 요약 조회 스파이
    const summary = vi.spyOn(gateway.forecast, 'summary')
    // when: 어떤 Vendor도 갖지 않은 id로 화면을 연다
    await renderAt(`/forecast?year=2026&vendor=${UNKNOWN}`)
    // then: Vendor 목록을 읽은 뒤 마지막 요약 조회에 vendorId가 없고 Vendor 칸이 "전체"다
    await vendorsLoaded()

    await waitFor(() => expect(lastQuery(summary).vendorId).toBeUndefined())
    expect(screen.getByLabelText('Vendor')).toHaveDisplayValue('전체')
  })

  // 테스트 코드: FC-065
  it('등록되지 않은 Vendor id는 담당자 Deal 목록 조회 조건에서도 뺀다', async () => {
    // given: Deal 목록 조회 스파이
    const list = vi.spyOn(gateway.deals, 'list')
    // when: 어떤 Vendor도 갖지 않은 id와 선택한 담당자로 화면을 연다
    await renderAt(`/forecast?year=2026&vendor=${UNKNOWN}&sel=${USER_ID.kim}`)
    // then: Vendor 목록을 읽은 뒤 마지막 Deal 목록 조회에 vendorId가 없다
    await screen.findByRole('heading', { name: /선택한 담당자/ })
    await vendorsLoaded()

    await waitFor(() => expect(lastQuery(list)).toMatchObject({ ownerId: USER_ID.kim, year: 2026 }))
    await waitFor(() => expect(lastQuery(list).vendorId).toBeUndefined())
  })

  // 테스트 코드: FC-065
  it('등록된 Vendor id는 요약 조회 조건에 남는다', async () => {
    // given: 요약 조회 스파이
    const summary = vi.spyOn(gateway.forecast, 'summary')
    // when: 등록 Vendor(Okta) id로 화면을 연다
    await renderAt(`/forecast?year=2026&vendor=${seedVendorId('Okta')}`)
    // then: Vendor 칸이 Okta이고 마지막 요약 조회에 그 id가 담긴다
    await vendorsLoaded()

    await waitFor(() => expect(screen.getByLabelText('Vendor')).toHaveDisplayValue('Okta'))
    expect(lastQuery(summary).vendorId).toBe(seedVendorId('Okta'))
  })
})
