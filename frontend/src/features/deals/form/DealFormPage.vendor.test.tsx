import { fireEvent, screen, waitFor, within } from '@testing-library/react'
import { afterEach, describe, expect, it, vi } from 'vitest'
import { gateway } from '../../../gateway'
import { ApiError } from '../../../shared/api/problem'
import { renderAt } from '../../../test/mockApp'
import { seedVendorId } from '../../../test/fixtures/vendors'
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
const solutionInput = () => screen.getByLabelText('Solution')

/** Vendor 목록이 로딩된 뒤의 select. */
async function loadedVendor() {
  await within(vendorSelect()).findByRole('option', { name: 'Silverfort' })
  return vendorSelect()
}

async function fillRequired(user: Awaited<ReturnType<typeof openNew>>['user'], name: string) {
  await user.type(screen.getByLabelText('Deal Name'), name)
  await pickPerson(user, '고객', '한빛은행', /정민수/)
  await user.type(screen.getByLabelText('금액(단위:천원)'), '100000')
  await user.type(screen.getByLabelText('Users'), '10')
  fireEvent.change(screen.getByLabelText('Expected Close'), { target: { value: '2027-05-01' } })
}

describe('Vendor 선택과 Solution 텍스트 (AC-12)', () => {
  it('lists none plus every registered vendor in the Vendor select', async () => {
    await openNew()
    const vendor = await loadedVendor()

    expect(vendor.tagName).toBe('SELECT')
    expect(optionNames(vendor)).toEqual([
      '선택 안 함', 'CrowdStrike', 'CyberArk', 'Okta', 'Palo Alto', 'SentinelOne', 'Silverfort', 'Splunk', 'Tenable', 'Veeam', 'Zscaler',
    ])
    expect(vendor).toHaveDisplayValue('선택 안 함')
  })

  it('solution is a text input enabled without a vendor', async () => {
    await openNew()
    await loadedVendor()

    expect(solutionInput().tagName).toBe('INPUT')
    expect(solutionInput()).toHaveAttribute('name', 'solution')
    expect(solutionInput()).toBeEnabled()
    expect(screen.queryByText('Vendor를 먼저 선택하세요.')).not.toBeInTheDocument()
  })

  it('marks Solution as required', async () => {
    await openNew()

    expect(solutionInput().closest('.field')).toHaveClass('required')
  })

  it('changing the vendor keeps the typed solution', async () => {
    const { user } = await openNew()
    await loadedVendor()
    await user.type(solutionInput(), 'ITDR')

    await user.selectOptions(vendorSelect(), 'Silverfort')
    await user.selectOptions(vendorSelect(), 'Okta')
    await user.selectOptions(vendorSelect(), '선택 안 함')

    expect(solutionInput()).toHaveValue('ITDR')
    expect(solutionInput()).toBeEnabled()
  })

  it('offers no way to create a vendor on the form and no solution list', async () => {
    await openNew()
    await loadedVendor()
    const info = screen.getByRole('region', { name: 'Deal 정보' })

    expect(within(info).queryByRole('button', { name: /새 (Vendor|Solution)|(Vendor|Solution) (추가|등록)/ })).not.toBeInTheDocument()
    expect(within(info).queryByRole('combobox', { name: 'Solution' })).not.toBeInTheDocument()
    expect(within(info).queryByRole('textbox', { name: 'Vendor' })).not.toBeInTheDocument()
  })
})

describe('Solution 필수 (Q1 변경)', () => {
  it('asks for a solution and does not call the gateway when it is blank', async () => {
    const create = vi.spyOn(gateway.deals, 'create')
    const { user, location } = await openNew()
    await loadedVendor()
    await fillRequired(user, 'Solution 비움')
    await user.type(solutionInput(), '   ')

    await save(user)

    const row = solutionInput().closest('.kv-row, .field') as HTMLElement
    expect(await within(row).findByRole('alert')).toHaveTextContent('Solution을 입력하세요.')
    expect(create).not.toHaveBeenCalled()
    expect(location()).toBe('/deals/new')
  })

  it('is listed with the other required messages when the form is saved empty', async () => {
    const { user } = await openNew()

    await save(user)

    const alerts = (await screen.findAllByRole('alert')).map((a) => a.textContent)
    expect(alerts).toContain('Solution을 입력하세요.')
  })
})

describe('저장 (AC-12, AC-7)', () => {
  it('saves the trimmed solution text with the chosen vendor id', async () => {
    const { user, location } = await openNew()
    await loadedVendor()
    await user.selectOptions(vendorSelect(), 'Silverfort')
    await user.type(solutionInput(), '  ITDR ')
    await fillRequired(user, 'Vendor 연동 등록')

    await save(user)

    await waitFor(() => expect(location()).toMatch(DETAIL_URL))
    const saved = await gateway.deals.get(location().replace('/deals/', ''))
    expect(saved.vendor).toEqual({ id: seedVendorId('Silverfort'), name: 'Silverfort' })
    expect(saved.solution).toBe('ITDR')
  })

  it('registers a deal without a vendor but with a solution text', async () => {
    const { user, location } = await openNew()
    await user.type(solutionInput(), 'MFA')
    await fillRequired(user, 'Vendor 없는 등록')

    await save(user)

    await waitFor(() => expect(location()).toMatch(DETAIL_URL))
    const saved = await gateway.deals.get(location().replace('/deals/', ''))
    expect(saved.vendor).toBeNull()
    expect(saved.solution).toBe('MFA')
  })

  it('loads the saved vendor and solution into the edit form and keeps the solution when the vendor changes', async () => {
    const { user, location, code } = await openEdit('누리통신 MFA') // Silverfort / MFA
    await waitFor(() => expect(vendorSelect()).toHaveDisplayValue('Silverfort'))
    expect(solutionInput()).toHaveValue('MFA')

    await user.selectOptions(vendorSelect(), 'Okta')
    expect(solutionInput()).toHaveValue('MFA')
    await save(user)

    await waitFor(() => expect(location()).toBe(`/deals/${code}`))
    const saved = await gateway.deals.get(code)
    expect(saved.vendor?.name).toBe('Okta')
    expect(saved.solution).toBe('MFA')
  })

  it('saves a changed solution text from the edit form', async () => {
    const { user, location, code } = await openEdit('누리통신 MFA')
    await waitFor(() => expect(solutionInput()).toHaveValue('MFA'))

    await user.clear(solutionInput())
    await user.type(solutionInput(), 'Identity Threat')
    await save(user)

    await waitFor(() => expect(location()).toBe(`/deals/${code}`))
    expect((await gateway.deals.get(code)).solution).toBe('Identity Threat')
  })

  it('does not save the edit form when the solution is cleared', async () => {
    const update = vi.spyOn(gateway.deals, 'update')
    const { user, location, code } = await openEdit('누리통신 MFA')
    await waitFor(() => expect(solutionInput()).toHaveValue('MFA'))

    await user.clear(solutionInput())
    await save(user)

    expect(await screen.findByText('Solution을 입력하세요.')).toBeVisible()
    expect(update).not.toHaveBeenCalled()
    expect(location()).toBe(`/deals/${code}/edit`)
  })

  it.each([
    '선택한 Vendor가 없습니다. 목록에서 다시 선택하세요.',
    'Solution은 200자 이내로 입력하세요.',
  ])('shows the server message "%s" in the error banner and stays on the form', async (detail) => {
    vi.spyOn(gateway.deals, 'create').mockRejectedValue(
      new ApiError(422, { type: 'https://sales.neoine.test/problems/invalid-value', title: 'x', status: 422, detail }),
    )
    const { user, location } = await openNew()
    await loadedVendor()
    await user.type(solutionInput(), 'ITDR')
    await fillRequired(user, '422 확인')

    await save(user)

    expect(await screen.findByRole('alert')).toHaveTextContent(detail)
    expect(location()).toBe('/deals/new')
  })

  it('shows the server message for a solution over 200 characters from the real fake gateway', async () => {
    const { user, location } = await openNew()
    fireEvent.change(solutionInput(), { target: { value: 'a'.repeat(201) } })
    await fillRequired(user, '길이 초과')

    await save(user)

    expect(await screen.findByRole('alert')).toHaveTextContent('Solution은 200자 이내로 입력하세요.')
    expect(location()).toBe('/deals/new')
  })
})
