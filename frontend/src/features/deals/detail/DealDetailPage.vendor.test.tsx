import { screen, waitFor, within } from '@testing-library/react'
import { afterEach, describe, expect, it, vi } from 'vitest'
import { gateway } from '../../../gateway'
import { detailPath } from '../../../test/detailTestUtils'
import { kvValue } from '../../../test/kvPairs'
import { renderAt } from '../../../test/mockApp'
import { seedVendorId } from '../../../test/fixtures/vendors'

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

describe('Vendor·Solution 인라인 편집 (AC-13)', () => {
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

  it('edits the solution as text and sends only solution', async () => {
    const { user, code } = await openDeal1()
    const update = vi.spyOn(gateway.deals, 'update')

    await user.click(screen.getByRole('button', { name: 'Solution 수정' }))
    const input = screen.getByLabelText('Solution')
    expect(input).toHaveValue('ITDR')
    await user.clear(input)
    await user.type(input, '  Identity Threat {Enter}')

    expect(await screen.findByText('Solution이 변경되었습니다.')).toBeVisible()
    expect(update).toHaveBeenCalledWith(code, { solution: 'Identity Threat' })
    await waitFor(() => expect(screen.getByRole('button', { name: 'Solution 수정' })).toHaveTextContent('Identity Threat'))
    expect((await gateway.deals.get(code)).solution).toBe('Identity Threat')
  })

  it('does not send a request when the solution text is unchanged', async () => {
    const { user } = await openDeal1()
    const update = vi.spyOn(gateway.deals, 'update')

    await user.click(screen.getByRole('button', { name: 'Solution 수정' }))
    await user.type(screen.getByLabelText('Solution'), '  ')
    await user.tab()

    expect(update).not.toHaveBeenCalled()
  })

  it('allows the solution edit when the deal has no vendor', async () => {
    const { user, code, client } = await openDeal1()
    await gateway.deals.update(code, { vendorId: null })
    await client.invalidateQueries()
    await waitFor(() => expect(screen.getByRole('button', { name: 'Vendor 수정' })).toHaveTextContent('—'))

    await user.click(screen.getByRole('button', { name: 'Solution 수정' }))
    const input = screen.getByLabelText('Solution')
    await user.clear(input)
    await user.type(input, 'MFA{Enter}')

    expect(await screen.findByText('Solution이 변경되었습니다.')).toBeVisible()
    expect((await gateway.deals.get(code)).solution).toBe('MFA')
  })

  it('vendor change sends only vendor and keeps the solution', async () => {
    const { user, code } = await openDeal1()
    const update = vi.spyOn(gateway.deals, 'update')

    await user.click(screen.getByRole('button', { name: 'Vendor 수정' }))
    const select = screen.getByRole('combobox', { name: 'Vendor' })
    await within(select).findByRole('option', { name: 'Okta' })
    await user.selectOptions(select, 'Okta')

    expect(await screen.findByText('Vendor가 변경되었습니다.')).toBeVisible()
    expect(screen.queryByText(/Solution은 비워졌습니다/)).not.toBeInTheDocument()
    expect(update).toHaveBeenCalledWith(code, { vendorId: seedVendorId('Okta') })
    await waitFor(() => expect(screen.getByRole('button', { name: 'Vendor 수정' })).toHaveTextContent('Okta'))
    expect(screen.getByRole('button', { name: 'Solution 수정' })).toHaveTextContent('ITDR')
    const saved = await gateway.deals.get(code)
    expect(saved.vendor?.name).toBe('Okta')
    expect(saved.solution).toBe('ITDR')
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

  it('shows a deal without a vendor as a dash for the vendor and keeps the solution text', async () => {
    const { code, client } = await openDeal1()
    await gateway.deals.update(code, { vendorId: null })
    await client.invalidateQueries()

    await waitFor(() => expect(screen.getByRole('button', { name: 'Vendor 수정' })).toHaveTextContent('—'))
    expect(screen.getByRole('button', { name: 'Solution 수정' })).toHaveTextContent('ITDR')
    expect(kvValue(infoTile(), 'Solution')).toHaveTextContent('ITDR')
  })

  it('changes the vendor inline on a legacy deal whose solution is empty', async () => {
    const path = await detailPath(1)
    const { user } = await renderAt(path, { seed: 'legacy-solution' })
    await screen.findByRole('heading', { level: 1, name: '한빛은행 ITDR 도입' })
    const code = path.replace('/deals/', '')
    const update = vi.spyOn(gateway.deals, 'update')

    await user.click(screen.getByRole('button', { name: 'Vendor 수정' }))
    const select = screen.getByRole('combobox', { name: 'Vendor' })
    await within(select).findByRole('option', { name: 'Okta' })
    await user.selectOptions(select, 'Okta')

    expect(await screen.findByText('Vendor가 변경되었습니다.')).toBeVisible()
    expect(update).toHaveBeenCalledWith(code, { vendorId: seedVendorId('Okta') })
    const stored = await gateway.deals.get(code)
    expect([stored.vendor?.name, stored.solution]).toEqual(['Okta', ''])
  })

  it('shows the names as plain text without edit buttons for a viewer', async () => {
    await renderAt(await detailPath(1), { role: 'user' })
    await screen.findByRole('heading', { level: 1, name: '한빛은행 ITDR 도입' })

    expect(kvValue(infoTile(), 'Vendor')).toHaveTextContent('Silverfort')
    expect(kvValue(infoTile(), 'Solution')).toHaveTextContent('ITDR')
    expect(screen.queryByRole('button', { name: 'Vendor 수정' })).not.toBeInTheDocument()
    expect(screen.queryByRole('button', { name: 'Solution 수정' })).not.toBeInTheDocument()
  })

  it('records only the vendor change in the Deal History when the vendor changes', async () => {
    const { user, code } = await openDeal1()

    await user.click(screen.getByRole('button', { name: 'Vendor 수정' }))
    const select = screen.getByRole('combobox', { name: 'Vendor' })
    await within(select).findByRole('option', { name: 'Okta' })
    await user.selectOptions(select, 'Okta')
    await screen.findByText('Vendor가 변경되었습니다.')

    const entries = await gateway.history.list(code, {})
    const pairs = entries.filter((h) => h.target === 'Vendor' || h.target === 'Solution').map((h) => [h.target, h.before, h.after])
    expect(pairs).toEqual([['Vendor', 'Silverfort', 'Okta']])
  })

  it('records the solution text change in the Deal History', async () => {
    const { user, code } = await openDeal1()

    await user.click(screen.getByRole('button', { name: 'Solution 수정' }))
    const input = screen.getByLabelText('Solution')
    await user.clear(input)
    await user.type(input, 'MFA{Enter}')
    await screen.findByText('Solution이 변경되었습니다.')

    const entries = await gateway.history.list(code, {})
    expect(entries.filter((h) => h.target === 'Solution').map((h) => [h.before, h.after])).toEqual([['ITDR', 'MFA']])
  })
})
