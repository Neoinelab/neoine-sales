import { screen, waitFor, within } from '@testing-library/react'
import { afterEach, describe, expect, it, vi } from 'vitest'
import { gateway } from '../../../gateway'
import { detailPath } from '../../../test/detailTestUtils'
import { kvValue } from '../../../test/kvPairs'
import { renderAt } from '../../../test/mockApp'
import { seedSolutionId, seedVendorId } from '../../../test/fixtures/vendors'

afterEach(() => vi.restoreAllMocks())

const infoTile = () => screen.getByRole('region', { name: 'Deal 정보' })
const optionNames = (select: HTMLElement) => within(select).getAllByRole('option').map((o) => o.textContent)

/** 시드 Deal 1(한빛은행 ITDR 도입, Silverfort / ITDR)의 상세를 연다. */
async function openDeal1() {
  const path = await detailPath(1)
  const view = await renderAt(path)
  await screen.findByRole('heading', { level: 1, name: '한빛은행 ITDR 도입' })
  return { ...view, code: path.replace('/deals/', '') }
}

describe('Vendor·Solution 인라인 편집 (AC-11)', () => {
  it('offers none plus every registered vendor in the Vendor select and the current one is selected', async () => {
    const { user } = await openDeal1()

    await user.click(screen.getByRole('button', { name: 'Vendor 수정' }))

    const select = screen.getByRole('combobox', { name: 'Vendor' })
    await within(select).findByRole('option', { name: 'Okta' })
    expect(optionNames(select)).toEqual([
      '선택 안 함', 'CrowdStrike', 'CyberArk', 'Okta', 'Palo Alto', 'SentinelOne', 'Silverfort', 'Splunk', 'Tenable', 'Veeam', 'Zscaler',
    ])
    expect(select).toHaveDisplayValue('Silverfort')
  })

  it('offers only the solutions of the current vendor', async () => {
    const { user } = await openDeal1()

    await user.click(screen.getByRole('button', { name: 'Solution 수정' }))

    const select = screen.getByRole('combobox', { name: 'Solution' })
    await within(select).findByRole('option', { name: 'MFA' })
    expect(optionNames(select)).toEqual(['선택 안 함', 'ITDR', 'MFA'])
    expect(select).toHaveDisplayValue('ITDR')
  })

  it('changing the vendor sends vendorId with solutionId null, clears the solution and says so', async () => {
    const { user, code } = await openDeal1()
    const update = vi.spyOn(gateway.deals, 'update')

    await user.click(screen.getByRole('button', { name: 'Vendor 수정' }))
    const select = screen.getByRole('combobox', { name: 'Vendor' })
    await within(select).findByRole('option', { name: 'Okta' })
    await user.selectOptions(select, 'Okta')

    expect(await screen.findByText('Vendor가 변경되었습니다. Solution은 비워졌습니다.')).toBeVisible()
    expect(update).toHaveBeenCalledWith(code, { vendorId: seedVendorId('Okta'), solutionId: null })
    await waitFor(() => expect(screen.getByRole('button', { name: 'Vendor 수정' })).toHaveTextContent('Okta'))
    expect(screen.getByRole('button', { name: 'Solution 수정' })).toHaveTextContent('—')
    const saved = await gateway.deals.get(code)
    expect(saved.vendor?.name).toBe('Okta')
    expect(saved.solution).toBeNull()
  })

  it('uses the short notice when the deal had no solution', async () => {
    const { user, code, client } = await openDeal1()
    await gateway.deals.update(code, { vendorId: seedVendorId('Silverfort'), solutionId: null })
    await client.invalidateQueries()
    await waitFor(() => expect(screen.getByRole('button', { name: 'Solution 수정' })).toHaveTextContent('—'))

    await user.click(screen.getByRole('button', { name: 'Vendor 수정' }))
    const select = screen.getByRole('combobox', { name: 'Vendor' })
    await within(select).findByRole('option', { name: 'Okta' })
    await user.selectOptions(select, 'Okta')

    expect(await screen.findByText('Vendor가 변경되었습니다.')).toBeVisible()
    expect(screen.queryByText('Vendor가 변경되었습니다. Solution은 비워졌습니다.')).not.toBeInTheDocument()
  })

  it('changing the solution keeps the vendor in the request', async () => {
    const { user, code } = await openDeal1()
    const update = vi.spyOn(gateway.deals, 'update')

    await user.click(screen.getByRole('button', { name: 'Solution 수정' }))
    const select = screen.getByRole('combobox', { name: 'Solution' })
    await within(select).findByRole('option', { name: 'MFA' })
    await user.selectOptions(select, 'MFA')

    expect(await screen.findByText('Solution이 변경되었습니다.')).toBeVisible()
    expect(update).toHaveBeenCalledWith(code, { vendorId: seedVendorId('Silverfort'), solutionId: seedSolutionId('Silverfort', 'MFA') })
    await waitFor(() => expect(screen.getByRole('button', { name: 'Solution 수정' })).toHaveTextContent('MFA'))
  })

  it('does nothing when the same vendor is chosen again', async () => {
    const { user } = await openDeal1()
    const update = vi.spyOn(gateway.deals, 'update')

    await user.click(screen.getByRole('button', { name: 'Vendor 수정' }))
    const select = screen.getByRole('combobox', { name: 'Vendor' })
    await within(select).findByRole('option', { name: 'Silverfort' })
    await user.selectOptions(select, 'Silverfort')
    await user.tab()

    expect(update).not.toHaveBeenCalled()
  })

  it('shows a deal without a vendor as a dash and offers no Solution edit button', async () => {
    const { code, client } = await openDeal1()
    await gateway.deals.update(code, { vendorId: null, solutionId: null })
    await client.invalidateQueries()

    await waitFor(() => expect(screen.getByRole('button', { name: 'Vendor 수정' })).toHaveTextContent('—'))
    expect(screen.queryByRole('button', { name: 'Solution 수정' })).not.toBeInTheDocument()
    expect(kvValue(infoTile(), 'Solution')).toHaveTextContent('—')
  })

  it('shows the names as plain text without edit buttons for a viewer', async () => {
    await renderAt(await detailPath(1), { role: 'user' })
    await screen.findByRole('heading', { level: 1, name: '한빛은행 ITDR 도입' })

    expect(kvValue(infoTile(), 'Vendor')).toHaveTextContent('Silverfort')
    expect(kvValue(infoTile(), 'Solution')).toHaveTextContent('ITDR')
    expect(screen.queryByRole('button', { name: 'Vendor 수정' })).not.toBeInTheDocument()
    expect(screen.queryByRole('button', { name: 'Solution 수정' })).not.toBeInTheDocument()
  })

  it('records the vendor change and the cleared solution in the Deal History with names', async () => {
    const { user, code } = await openDeal1()

    await user.click(screen.getByRole('button', { name: 'Vendor 수정' }))
    const select = screen.getByRole('combobox', { name: 'Vendor' })
    await within(select).findByRole('option', { name: 'Okta' })
    await user.selectOptions(select, 'Okta')
    await screen.findByText('Vendor가 변경되었습니다. Solution은 비워졌습니다.')

    const entries = await gateway.history.list(code, {})
    const pairs = entries.filter((h) => h.target === 'Vendor' || h.target === 'Solution').map((h) => [h.target, h.before, h.after])
    expect(pairs).toEqual(expect.arrayContaining([['Vendor', 'Silverfort', 'Okta'], ['Solution', 'ITDR', '선택 안 함']]))
  })
})
