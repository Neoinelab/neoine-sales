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
 * 조회 조건(vendorId)에서도 제외한다. Solution은 Vendor와 무관한 텍스트라 어떤 경우에도 그대로 유지한다.
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
  it('drops a vendor id that is not registered from the query and lists everything', async () => {
    const list = vi.spyOn(gateway.deals, 'list')
    await renderAt(`/deals?vendor=${UNKNOWN}`)
    await vendorsLoaded()

    await waitFor(() => expect(dataRows()).toHaveLength(20))
    expect(screen.getByLabelText('Vendor')).toHaveDisplayValue('전체')
    expect(lastQuery(list).vendorId).toBeUndefined()
  })

  it('keeps the solution text even when the vendor id is not registered', async () => {
    const list = vi.spyOn(gateway.deals, 'list')
    await renderAt(`/deals?vendor=${UNKNOWN}&solution=ITDR`)
    await vendorsLoaded()

    await waitFor(() => expect(lastQuery(list).vendorId).toBeUndefined())
    expect(lastQuery(list).solution).toBe('ITDR')
    expect(screen.getByLabelText('Solution')).toHaveValue('ITDR')
  })

  it('keeps a registered vendor and the solution text in the query', async () => {
    const list = vi.spyOn(gateway.deals, 'list')
    await renderAt(`/deals?vendor=${seedVendorId('Silverfort')}&solution=ITDR`)
    await vendorsLoaded()

    await waitFor(() => expect(dataRows()).toHaveLength(4))
    expect(lastQuery(list)).toMatchObject({ vendorId: seedVendorId('Silverfort'), solution: 'ITDR' })
  })

  it('keeps a solution text that no vendor owns together with a vendor that does not have it', async () => {
    const list = vi.spyOn(gateway.deals, 'list')
    await renderAt(`/deals?vendor=${seedVendorId('Okta')}&solution=ITDR`)
    await vendorsLoaded()

    await waitFor(() => expect(lastQuery(list)).toMatchObject({ vendorId: seedVendorId('Okta'), solution: 'ITDR' }))
  })
})
