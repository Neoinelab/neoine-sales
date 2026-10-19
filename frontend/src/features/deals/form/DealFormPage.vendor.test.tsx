import { fireEvent, screen, waitFor, within } from '@testing-library/react'
import { afterEach, describe, expect, it, vi } from 'vitest'
import { gateway } from '../../../gateway'
import { ApiError } from '../../../shared/api/problem'
import { renderAt } from '../../../test/mockApp'
import { seedSolutionId, seedVendorId } from '../../../test/fixtures/vendors'
import { DETAIL_URL, openEdit, pickPerson, save } from './testHelpers'

afterEach(() => vi.restoreAllMocks())

async function openNew() {
  const view = await renderAt('/deals/new')
  await screen.findByRole('heading', { name: 'Deal 등록' })
  await screen.findByLabelText('Deal Name')
  return view
}

const optionNames = (select: HTMLElement) => within(select).getAllByRole('option').map((o) => o.textContent)
const vendorSelect = () => screen.getByLabelText('Vendor')
const solutionSelect = () => screen.getByLabelText('Solution')

/** Vendor 목록이 로딩된 뒤의 select. */
async function loadedVendor() {
  await within(vendorSelect()).findByRole('option', { name: 'Silverfort' })
  return vendorSelect()
}

describe('Vendor·Solution 선택 (AC-9)', () => {
  it('lists none plus every registered vendor in the Vendor select', async () => {
    await openNew()
    const vendor = await loadedVendor()

    expect(vendor.tagName).toBe('SELECT')
    expect(optionNames(vendor)).toEqual([
      '선택 안 함', 'CrowdStrike', 'CyberArk', 'Okta', 'Palo Alto', 'SentinelOne', 'Silverfort', 'Splunk', 'Tenable', 'Veeam', 'Zscaler',
    ])
    expect(vendor).toHaveDisplayValue('선택 안 함')
  })

  it('disables Solution with a hint until a vendor is chosen', async () => {
    const { user } = await openNew()
    await loadedVendor()

    expect(solutionSelect()).toBeDisabled()
    expect(screen.getByText('Vendor를 먼저 선택하세요.')).toBeVisible()

    await user.selectOptions(vendorSelect(), 'Silverfort')

    expect(solutionSelect()).toBeEnabled()
    expect(screen.queryByText('Vendor를 먼저 선택하세요.')).not.toBeInTheDocument()
  })

  it('shows only the solutions of the chosen vendor, plus none', async () => {
    const { user } = await openNew()
    await loadedVendor()

    await user.selectOptions(vendorSelect(), 'Silverfort')
    expect(optionNames(solutionSelect())).toEqual(['선택 안 함', 'ITDR', 'MFA'])

    await user.selectOptions(vendorSelect(), 'Okta')
    expect(optionNames(solutionSelect())).toEqual(['선택 안 함', 'SSO'])

    await user.selectOptions(vendorSelect(), 'Veeam')
    expect(optionNames(solutionSelect())).toEqual(['선택 안 함'])
  })

  it('offers no way to create a vendor or a solution on the form', async () => {
    await openNew()
    await loadedVendor()
    const info = screen.getByRole('region', { name: 'Deal 정보' })

    expect(within(info).queryByRole('button', { name: /새 (Vendor|Solution)|(Vendor|Solution) (추가|등록)/ })).not.toBeInTheDocument()
    expect(within(info).queryByRole('option', { name: /새로|직접 입력|\+/ })).not.toBeInTheDocument()
    expect(within(info).queryByRole('textbox', { name: /Vendor|Solution/ })).not.toBeInTheDocument()
  })

  it('AC-22 puts Vendor and Solution in div.kv-row > SelectField rows like Status', async () => {
    await openNew()
    await loadedVendor()

    for (const label of ['Status', 'Vendor', 'Solution']) {
      const row = screen.getByLabelText(label).closest('label')?.parentElement as HTMLElement
      expect(row.tagName).toBe('DIV')
      expect(row).toHaveClass('kv-row')
    }
  })
})

describe('Vendor를 바꾸면 Solution을 비운다 (AC-10)', () => {
  it('clears the solution when another vendor is chosen', async () => {
    const { user } = await openNew()
    await loadedVendor()
    await user.selectOptions(vendorSelect(), 'Silverfort')
    await user.selectOptions(solutionSelect(), 'ITDR')
    expect(solutionSelect()).toHaveDisplayValue('ITDR')

    await user.selectOptions(vendorSelect(), 'Okta')

    expect(solutionSelect()).toHaveDisplayValue('선택 안 함')
  })

  it('clears the solution and disables it again when the vendor is set back to none', async () => {
    const { user } = await openNew()
    await loadedVendor()
    await user.selectOptions(vendorSelect(), 'Silverfort')
    await user.selectOptions(solutionSelect(), 'MFA')

    await user.selectOptions(vendorSelect(), '선택 안 함')

    expect(solutionSelect()).toBeDisabled()
    expect(solutionSelect()).toHaveDisplayValue('선택 안 함')
    expect(screen.getByText('Vendor를 먼저 선택하세요.')).toBeVisible()
  })

  it('keeps the solution when the same vendor is chosen again', async () => {
    const { user } = await openNew()
    await loadedVendor()
    await user.selectOptions(vendorSelect(), 'Silverfort')
    await user.selectOptions(solutionSelect(), 'ITDR')

    await user.selectOptions(vendorSelect(), 'Silverfort')

    expect(solutionSelect()).toHaveDisplayValue('ITDR')
  })
})

describe('저장 (AC-9, AC-10, AC-13)', () => {
  it('registers a deal with the chosen vendor and solution ids', async () => {
    const { user, location } = await openNew()
    await loadedVendor()
    await user.type(screen.getByLabelText('Deal Name'), 'Vendor 연동 등록')
    await user.selectOptions(vendorSelect(), 'Silverfort')
    await user.selectOptions(solutionSelect(), 'ITDR')
    await pickPerson(user, '고객', '한빛은행', /정민수/)
    await user.type(screen.getByLabelText('금액'), '100000000')
    fireEvent.change(screen.getByLabelText('Expected Close'), { target: { value: '2027-05-01' } })

    await save(user)

    await waitFor(() => expect(location()).toMatch(DETAIL_URL))
    const code = location().replace('/deals/', '')
    const saved = await gateway.deals.get(code)
    expect(saved.vendor).toEqual({ id: seedVendorId('Silverfort'), name: 'Silverfort' })
    expect(saved.solution).toEqual({ id: seedSolutionId('Silverfort', 'ITDR'), name: 'ITDR' })
  })

  it('registers a deal without vendor and solution as null', async () => {
    const { user, location } = await openNew()
    await user.type(screen.getByLabelText('Deal Name'), 'Vendor 없는 등록')
    await pickPerson(user, '고객', '한빛은행', /정민수/)
    await user.type(screen.getByLabelText('금액'), '100000000')
    fireEvent.change(screen.getByLabelText('Expected Close'), { target: { value: '2027-05-01' } })

    await save(user)

    await waitFor(() => expect(location()).toMatch(DETAIL_URL))
    const saved = await gateway.deals.get(location().replace('/deals/', ''))
    expect(saved.vendor).toBeNull()
    expect(saved.solution).toBeNull()
  })

  it('loads the saved vendor and solution into the edit form and saves a changed vendor with an empty solution', async () => {
    const { user, location, code } = await openEdit('누리통신 MFA') // Silverfort / MFA
    await waitFor(() => expect(vendorSelect()).toHaveDisplayValue('Silverfort'))
    await waitFor(() => expect(solutionSelect()).toHaveDisplayValue('MFA'))

    await user.selectOptions(vendorSelect(), 'Okta')
    expect(solutionSelect()).toHaveDisplayValue('선택 안 함')
    await save(user)

    await waitFor(() => expect(location()).toBe(`/deals/${code}`))
    const saved = await gateway.deals.get(code)
    expect(saved.vendor?.name).toBe('Okta')
    expect(saved.solution).toBeNull()
  })

  it.each([
    'Solution을 선택하려면 Vendor를 먼저 선택하세요.',
    '선택한 Vendor가 없습니다. 목록에서 다시 선택하세요.',
    '선택한 Solution은 이 Vendor에 속하지 않습니다.',
  ])('shows the server message "%s" in the error banner and stays on the form', async (detail) => {
    vi.spyOn(gateway.deals, 'create').mockRejectedValue(
      new ApiError(422, { type: 'https://sales.neoine.test/problems/invalid-value', title: 'x', status: 422, detail }),
    )
    const { user, location } = await openNew()
    await loadedVendor()
    await user.type(screen.getByLabelText('Deal Name'), '422 확인')
    await pickPerson(user, '고객', '한빛은행', /정민수/)
    await user.type(screen.getByLabelText('금액'), '100000000')
    fireEvent.change(screen.getByLabelText('Expected Close'), { target: { value: '2027-05-01' } })

    await save(user)

    expect(await screen.findByRole('alert')).toHaveTextContent(detail)
    expect(location()).toBe('/deals/new')
  })
})
