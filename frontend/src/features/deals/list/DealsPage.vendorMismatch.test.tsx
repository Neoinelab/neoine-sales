import { screen, waitFor, within } from '@testing-library/react'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { gateway } from '../../../gateway'
import { resetMock } from '../../../test/fake/default'
import { seedSolutionId, seedVendorId } from '../../../test/fixtures/vendors'
import { renderAt } from '../../../test/mockApp'
import { dataRows } from './testHelpers'

/**
 * 목록 필터의 표시와 조회 조건 일치 계약(리뷰 Minor 2).
 * Vendor 목록을 받은 뒤, 목록에 없는 vendor/solution UUID나 선택된 Vendor 소속이 아닌 Solution은
 * 화면에서 '전체'로 보일 뿐 아니라 조회 조건(vendorId·solutionId)에서도 제외한다.
 * 목록을 받기 전에는 판단하지 않으므로 이 테스트는 목록 로딩 뒤의 마지막 조회만 본다.
 */
const NOW = '2026-10-15T09:00:00+09:00'
const UNKNOWN = '99999999-9999-4999-8999-999999999999'

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

  it('drops a solution id that is not registered from the query', async () => {
    const list = vi.spyOn(gateway.deals, 'list')
    await renderAt(`/deals?solution=${UNKNOWN}`)
    await vendorsLoaded()

    await waitFor(() => expect(dataRows()).toHaveLength(20))
    expect(screen.getByLabelText('Solution')).toHaveDisplayValue('전체')
    expect(lastQuery(list).solutionId).toBeUndefined()
  })

  it('drops a solution that does not belong to the chosen vendor but keeps the vendor', async () => {
    const list = vi.spyOn(gateway.deals, 'list')
    await renderAt(`/deals?vendor=${seedVendorId('Okta')}&solution=${seedSolutionId('Silverfort', 'ITDR')}`)
    await vendorsLoaded()

    await waitFor(() => expect(lastQuery(list).solutionId).toBeUndefined())
    expect(lastQuery(list).vendorId).toBe(seedVendorId('Okta'))
    expect(screen.getByLabelText('Vendor')).toHaveDisplayValue('Okta')
    expect(screen.getByLabelText('Solution')).toHaveDisplayValue('전체')
  })

  it('drops an unregistered vendor but keeps a registered solution', async () => {
    const list = vi.spyOn(gateway.deals, 'list')
    await renderAt(`/deals?vendor=${UNKNOWN}&solution=${seedSolutionId('Silverfort', 'ITDR')}`)
    await vendorsLoaded()

    await waitFor(() => expect(lastQuery(list).vendorId).toBeUndefined())
    expect(lastQuery(list).solutionId).toBe(seedSolutionId('Silverfort', 'ITDR'))
    expect(screen.getByLabelText('Solution')).toHaveDisplayValue('Silverfort / ITDR')
  })

  it('keeps a registered vendor and its own solution in the query', async () => {
    const list = vi.spyOn(gateway.deals, 'list')
    await renderAt(`/deals?vendor=${seedVendorId('Silverfort')}&solution=${seedSolutionId('Silverfort', 'ITDR')}`)
    await vendorsLoaded()

    await waitFor(() => expect(dataRows()).toHaveLength(4))
    expect(lastQuery(list)).toMatchObject({ vendorId: seedVendorId('Silverfort'), solutionId: seedSolutionId('Silverfort', 'ITDR') })
  })
})
