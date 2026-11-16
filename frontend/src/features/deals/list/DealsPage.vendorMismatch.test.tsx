import { screen, waitFor, within } from '@testing-library/react'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { gateway } from '../../../gateway'
import { resetMock } from '../../../test/fake/default'
import { NO_SUCH_ID } from '../../../test/fake/seed/ids'
import { seedVendorId } from '../../../test/fixtures/vendors'
import { renderAt } from '../../../test/mockApp'
import { dataRows } from './testHelpers'

/**
 * 목록 필터의 표시와 조회 조건 일치 계약(리뷰 Minor 2).
 * Vendor 목록을 받은 뒤, 목록에 없는 vendor 정수 id는 화면에서 '전체'로 보일 뿐 아니라
 * 조회 조건(vendorId)에서도 제외한다. Product는 Vendor와 무관한 텍스트라 어떤 경우에도 그대로 유지한다.
 * 목록을 받기 전에는 판단하지 않으므로 이 테스트는 목록 로딩 뒤의 마지막 조회만 본다.
 */
const NOW = '2026-10-15T09:00:00+09:00'
/** 서버 허용 범위 안의 정수지만 어떤 Vendor도 갖지 않은 id. */
const UNKNOWN = NO_SUCH_ID

beforeEach(() => resetMock({ now: NOW }))
afterEach(() => {
  vi.restoreAllMocks()
  resetMock({ now: null })
})

async function vendorsLoaded() {
  await within(await screen.findByLabelText('Vendor')).findByRole('option', { name: 'Silverfort' })
}
const lastQuery = (spy: ReturnType<typeof vi.spyOn>) => spy.mock.calls.at(-1)?.[0] as Record<string, unknown>

describe('목록 필터: 표시와 조건 일치', () => {
  // 등록되지 않은 Vendor id는 전체로 보이고 조회에서 뺀다
  // 테스트 코드: DL-067
  it('drops a vendor id that is not registered from the query and lists everything', async () => {
    // given: 없는 Vendor id가 든 주소
    const list = vi.spyOn(gateway.deals, 'list')
    await renderAt(`/deals?vendor=${UNKNOWN}`)
    // when: 그 주소를 연다
    await vendorsLoaded()

    // then: 선택은 전체이고 조회에 Vendor가 없다
    await waitFor(() => expect(dataRows()).toHaveLength(20))
    expect(screen.getByLabelText('Vendor')).toHaveDisplayValue('전체')
    expect(lastQuery(list).vendorId).toBeUndefined()
  })

  // 없는 Vendor여도 Product 텍스트는 유지한다
  // 테스트 코드: DL-067
  it('keeps the product text even when the vendor id is not registered', async () => {
    // given: 없는 Vendor와 Product가 든 주소
    const list = vi.spyOn(gateway.deals, 'list')
    await renderAt(`/deals?vendor=${UNKNOWN}&product=ITDR`)
    // when: 그 주소를 연다
    await vendorsLoaded()

    // then: Product가 조회에 남는다
    await waitFor(() => expect(lastQuery(list).vendorId).toBeUndefined())
    expect(lastQuery(list).product).toBe('ITDR')
    expect(screen.getByLabelText('Product')).toHaveValue('ITDR')
  })

  // 등록된 Vendor와 Product는 조회에 함께 쓴다
  // 테스트 코드: DL-067
  it('keeps a registered vendor and the product text in the query', async () => {
    // given: 등록된 Vendor와 Product가 든 주소
    const list = vi.spyOn(gateway.deals, 'list')
    await renderAt(`/deals?vendor=${seedVendorId('Silverfort')}&product=ITDR`)
    // when: 그 주소를 연다
    await vendorsLoaded()

    // then: 둘 다 조회에 실린다
    await waitFor(() => expect(dataRows()).toHaveLength(4))
    expect(lastQuery(list)).toMatchObject({ vendorId: seedVendorId('Silverfort'), product: 'ITDR' })
  })

  // 어느 Vendor에도 없는 Product도 Vendor와 독립적으로 유지한다
  // 테스트 코드: DL-067
  it('keeps a product text that no vendor owns together with a vendor that does not have it', async () => {
    // given: Vendor와 맞지 않는 Product가 든 주소
    const list = vi.spyOn(gateway.deals, 'list')
    await renderAt(`/deals?vendor=${seedVendorId('Okta')}&product=ITDR`)
    // when: 그 주소를 연다
    await vendorsLoaded()

    // then: 둘 다 조건으로 남는다
    await waitFor(() => expect(lastQuery(list)).toMatchObject({ vendorId: seedVendorId('Okta'), product: 'ITDR' }))
  })
})
