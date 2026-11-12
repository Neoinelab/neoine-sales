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
  await user.type(screen.getByLabelText('금액(단위:원)'), '100000000')
  await user.type(screen.getByLabelText('Users count'), '10')
  fireEvent.change(screen.getByLabelText('Expected Close'), { target: { value: '2027-05-01' } })
}

describe('Vendor 선택과 Solution 텍스트', () => {
  // Vendor 선택 상자는 '선택 안 함'과 등록된 Vendor 전체를 보인다.
  // 테스트 코드: DE-086
  it('lists none plus every registered vendor in the Vendor select', async () => {
    // when: Deal 등록 화면을 연다.
    await openNew()
    const vendor = await loadedVendor()

    // then: 선택 안 함과 모든 Vendor가 선택지다.
    expect(vendor.tagName).toBe('SELECT')
    expect(optionNames(vendor)).toEqual([
      '선택 안 함', 'CrowdStrike', 'CyberArk', 'Okta', 'Palo Alto', 'SentinelOne', 'Silverfort', 'Splunk', 'Tenable', 'Veeam', 'Zscaler',
    ])
    expect(vendor).toHaveDisplayValue('선택 안 함')
  })

  // Solution은 Vendor 없이도 입력할 수 있는 텍스트 칸이다.
  // 테스트 코드: DE-086
  it('solution is a text input enabled without a vendor', async () => {
    // when: Deal 등록 화면을 연다.
    await openNew()
    await loadedVendor()

    // then: Solution 칸이 활성인 텍스트 입력이다.
    expect(solutionInput().tagName).toBe('INPUT')
    expect(solutionInput()).toHaveAttribute('name', 'solution')
    expect(solutionInput()).toBeEnabled()
    expect(screen.queryByText('Vendor를 먼저 선택하세요.')).not.toBeInTheDocument()
  })

  // Solution은 필수로 표시된다.
  // 테스트 코드: DE-086
  it('marks Solution as required', async () => {
    // when: Deal 등록 화면을 연다.
    await openNew()

    // then: Solution이 필수 표시다.
    expect(solutionInput().closest('.field')).toHaveClass('required')
  })

  // Vendor를 바꿔도 입력한 Solution은 그대로다.
  // 테스트 코드: DE-086
  it('changing the vendor keeps the typed solution', async () => {
    // given: Solution을 입력했다.
    const { user } = await openNew()
    await loadedVendor()

    // when: Vendor를 바꾼다.
    await user.type(solutionInput(), 'ITDR')

    await user.selectOptions(vendorSelect(), 'Silverfort')
    await user.selectOptions(vendorSelect(), 'Okta')
    await user.selectOptions(vendorSelect(), '선택 안 함')

    // then: Solution 값이 그대로다.
    expect(solutionInput()).toHaveValue('ITDR')
    expect(solutionInput()).toBeEnabled()
  })

  // 폼에서 Vendor를 만들거나 Solution 목록을 고를 수 없다.
  // 테스트 코드: DE-086
  it('offers no way to create a vendor on the form and no solution list', async () => {
    // when: Deal 등록 화면을 연다.
    await openNew()
    await loadedVendor()
    const info = screen.getByRole('region', { name: 'Deal 정보' })

    // then: Vendor 생성 버튼과 Solution 선택 목록이 없다.
    expect(within(info).queryByRole('button', { name: /새 (Vendor|Solution)|(Vendor|Solution) (추가|등록)/ })).not.toBeInTheDocument()
    expect(within(info).queryByRole('combobox', { name: 'Solution' })).not.toBeInTheDocument()
    expect(within(info).queryByRole('textbox', { name: 'Vendor' })).not.toBeInTheDocument()
  })
})

describe('Solution 필수 (Q1 변경)', () => {
  // Solution이 비면 요청 없이 문구를 보인다.
  // 테스트 코드: DE-087
  it('asks for a solution and does not call the gateway when it is blank', async () => {
    // given: Solution만 비운 채 필수 값을 입력했다.
    const create = vi.spyOn(gateway.deals, 'create')
    const { user, location } = await openNew()
    await loadedVendor()
    await fillRequired(user, 'Solution 비움')
    await user.type(solutionInput(), '   ')

    // when: 저장한다.
    await save(user)
    const row = solutionInput().closest('.kv-row, .field') as HTMLElement

    // then: 'Solution을 입력하세요.'가 나오고 등록 요청이 없다.
    expect(await within(row).findByRole('alert')).toHaveTextContent('Solution을 입력하세요.')
    expect(create).not.toHaveBeenCalled()
    expect(location()).toBe('/deals/new')
  })

  // 빈 폼을 저장하면 Solution 문구가 다른 필수 문구와 함께 나온다.
  // 테스트 코드: DE-087
  it('is listed with the other required messages when the form is saved empty', async () => {
    // when: 빈 폼을 저장한다.
    const { user } = await openNew()
    await save(user)

    // then: Solution 문구가 다른 필수 문구와 함께 있다.
    const alerts = (await screen.findAllByRole('alert')).map((a) => a.textContent)
    expect(alerts).toContain('Solution을 입력하세요.')
  })
})

describe('저장', () => {
  // Solution은 공백을 지우고 고른 Vendor id와 함께 저장된다.
  // 테스트 코드: DE-088
  it('saves the trimmed solution text with the chosen vendor id', async () => {
    // given: Vendor를 골랐다.
    const { user, location } = await openNew()
    await loadedVendor()
    await user.selectOptions(vendorSelect(), 'Silverfort')
    await user.type(solutionInput(), '  ITDR ')
    await fillRequired(user, 'Vendor 연동 등록')

    // when: 공백이 든 Solution으로 저장한다.
    await save(user)

    // then: 요청에 Vendor id와 공백 없는 Solution이 담긴다.
    await waitFor(() => expect(location()).toMatch(DETAIL_URL))
    const saved = await gateway.deals.get(location().replace('/deals/', ''))
    expect(saved.vendor).toEqual({ id: seedVendorId('Silverfort'), name: 'Silverfort' })
    expect(saved.solution).toBe('ITDR')
  })

  // Vendor 없이 Solution만으로 저장된다.
  // 테스트 코드: DE-088
  it('registers a deal without a vendor but with a solution text', async () => {
    // given: Vendor 없이 Solution만 입력했다.
    const { user, location } = await openNew()
    await user.type(solutionInput(), 'MFA')
    await fillRequired(user, 'Vendor 없는 등록')

    // when: Vendor를 고르지 않고 저장한다.
    await save(user)

    // then: Vendor가 없고 Solution이 있는 Deal이 저장된다.
    await waitFor(() => expect(location()).toMatch(DETAIL_URL))
    const saved = await gateway.deals.get(location().replace('/deals/', ''))
    expect(saved.vendor).toBeNull()
    expect(saved.solution).toBe('MFA')
  })

  // 수정 폼은 Vendor·Solution을 채우고 Vendor를 바꿔도 Solution을 유지한다.
  // 테스트 코드: DE-090
  it('loads the saved vendor and solution into the edit form and keeps the solution when the vendor changes', async () => {
    // when: 수정 화면을 연다. (Silverfort / MFA인 Deal)
    const { user, location, code } = await openEdit('누리통신 MFA')

    // then: 저장된 Vendor와 Solution이 채워진다.
    await waitFor(() => expect(vendorSelect()).toHaveDisplayValue('Silverfort'))
    expect(solutionInput()).toHaveValue('MFA')

    // when: Vendor를 Okta로 바꾸고 저장한다.
    await user.selectOptions(vendorSelect(), 'Okta')
    expect(solutionInput()).toHaveValue('MFA')
    await save(user)

    // then: Vendor만 바뀌고 Solution이 유지된다.
    await waitFor(() => expect(location()).toBe(`/deals/${code}`))
    const saved = await gateway.deals.get(code)
    expect(saved.vendor?.name).toBe('Okta')
    expect(saved.solution).toBe('MFA')
  })

  // 수정 폼에서 바꾼 Solution이 저장된다.
  // 테스트 코드: DE-090
  it('saves a changed solution text from the edit form', async () => {
    // given: 수정 화면에 저장된 Solution이 채워져 있다.
    const { user, location, code } = await openEdit('누리통신 MFA')
    await waitFor(() => expect(solutionInput()).toHaveValue('MFA'))

    // when: Solution을 바꿔 저장한다.
    await user.clear(solutionInput())
    await user.type(solutionInput(), 'Identity Threat')
    await save(user)

    // then: 바뀐 Solution이 저장된다.
    await waitFor(() => expect(location()).toBe(`/deals/${code}`))
    expect((await gateway.deals.get(code)).solution).toBe('Identity Threat')
  })

  // Solution을 비우면 저장하지 않는다.
  // 테스트 코드: DE-090
  it('does not save the edit form when the solution is cleared', async () => {
    // given: 수정 화면에 저장된 Solution이 채워져 있다.
    const update = vi.spyOn(gateway.deals, 'update')
    const { user, location, code } = await openEdit('누리통신 MFA')
    await waitFor(() => expect(solutionInput()).toHaveValue('MFA'))

    // when: Solution을 비우고 저장한다.
    await user.clear(solutionInput())
    await save(user)

    // then: Solution 문구가 나오고 저장되지 않는다.
    expect(await screen.findByText('Solution을 입력하세요.')).toBeVisible()
    expect(update).not.toHaveBeenCalled()
    expect(location()).toBe(`/deals/${code}/edit`)
  })

  // 서버의 Vendor·Solution 오류 문구를 배너에 보이고 폼에 머문다.
  // 테스트 코드: DE-089
  it.each([
    '선택한 Vendor가 없습니다. 목록에서 다시 선택하세요.',
    'Solution은 200자 이내로 입력하세요.',
  ])('shows the server message "%s" in the error banner and stays on the form', async (detail) => {
    // given: 등록 요청이 서버 문구로 거절된다.
    vi.spyOn(gateway.deals, 'create').mockRejectedValue(
      new ApiError(422, { type: 'https://sales.neoine.test/problems/invalid-value', title: 'x', status: 422, detail }),
    )
    const { user, location } = await openNew()
    await loadedVendor()
    await user.type(solutionInput(), 'ITDR')
    await fillRequired(user, '422 확인')

    // when: 저장한다.
    await save(user)

    // then: 배너에 서버 문구가 나오고 등록 화면에 머문다.
    expect(await screen.findByRole('alert')).toHaveTextContent(detail)
    expect(location()).toBe('/deals/new')
  })

  // 201자 Solution은 서버 문구를 배너에 보인다.
  // 테스트 코드: DE-089
  it('shows the server message for a solution over 200 characters from the real fake gateway', async () => {
    // given: 201자 Solution을 입력했다.
    const { user, location } = await openNew()
    fireEvent.change(solutionInput(), { target: { value: 'a'.repeat(201) } })
    await fillRequired(user, '길이 초과')

    // when: 저장한다.
    await save(user)

    // then: 'Solution은 200자 이내로 입력하세요.'가 배너에 나온다.
    expect(await screen.findByRole('alert')).toHaveTextContent('Solution은 200자 이내로 입력하세요.')
    expect(location()).toBe('/deals/new')
  })
})
