import { fireEvent, screen, waitFor, within } from '@testing-library/react'
import { afterEach, describe, expect, it, vi } from 'vitest'
import { gateway } from '../../../gateway'
import { ApiError } from '../../../shared/api/problem'
import { renderAt } from '../../../test/mockApp'
import { seedVendorId } from '../../../test/fixtures/vendors'
import { pickVendor } from '../../../test/vendorPick'
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
const productInput = () => screen.getByLabelText('Product')

/** Vendor 목록이 로딩된 뒤의 select. */
async function loadedVendor() {
  await within(vendorSelect()).findByRole('option', { name: 'Silverfort' })
  return vendorSelect()
}

async function fillRequired(user: Awaited<ReturnType<typeof openNew>>['user'], name: string, withVendor = true) {
  await user.type(screen.getByLabelText('Deal Name'), name)
  if (withVendor) await pickVendor(user)
  await pickPerson(user, '고객', '한빛은행', /정민수/)
  await user.type(screen.getByLabelText('금액(단위:원)'), '100000000')
  await user.type(screen.getByLabelText('Users count'), '10')
  fireEvent.change(screen.getByLabelText('Expected Close'), { target: { value: '2027-05-01' } })
}

describe('Vendor 선택과 Product 텍스트', () => {
  // Vendor 선택 상자는 '선택하세요'와 등록된 Vendor 전체를 보이고 '선택 안 함'은 없다.
  // 테스트 코드: DE-086
  it('lists the placeholder plus every registered vendor in the Vendor select', async () => {
    // when: Deal 등록 화면을 연다.
    await openNew()
    const vendor = await loadedVendor()

    // then: 선택하세요와 모든 Vendor가 선택지이고 처음엔 선택하세요다.
    expect(vendor.tagName).toBe('SELECT')
    expect(optionNames(vendor)).toEqual([
      '선택하세요', 'CrowdStrike', 'CyberArk', 'Okta', 'Palo Alto', 'SentinelOne', 'Silverfort', 'Splunk', 'Tenable', 'Veeam', 'Zscaler',
    ])
    expect(vendor).toHaveDisplayValue('선택하세요')
  })

  // Product는 Vendor 없이도 입력할 수 있는 텍스트 칸이다.
  // 테스트 코드: DE-086
  it('product is a text input enabled without a vendor', async () => {
    // when: Deal 등록 화면을 연다.
    await openNew()
    await loadedVendor()

    // then: Product 칸이 활성인 텍스트 입력이다.
    expect(productInput().tagName).toBe('INPUT')
    expect(productInput()).toHaveAttribute('name', 'product')
    expect(productInput()).toBeEnabled()
    expect(screen.queryByText('Vendor를 먼저 선택하세요.')).not.toBeInTheDocument()
  })

  // Vendor를 바꿔도 입력한 Product는 그대로다.
  // 테스트 코드: DE-086
  it('changing the vendor keeps the typed product', async () => {
    // given: Product를 입력했다.
    const { user } = await openNew()
    await loadedVendor()

    // when: Vendor를 바꾼다.
    await user.type(productInput(), 'ITDR')

    await user.selectOptions(vendorSelect(), 'Silverfort')
    await user.selectOptions(vendorSelect(), 'Okta')
    await user.selectOptions(vendorSelect(), 'Zscaler')

    // then: Product 값이 그대로다.
    expect(productInput()).toHaveValue('ITDR')
    expect(productInput()).toBeEnabled()
  })

  // 폼에서 Vendor를 만들거나 Product 목록을 고를 수 없다.
  // 테스트 코드: DE-086
  it('offers no way to create a vendor on the form and no product list', async () => {
    // when: Deal 등록 화면을 연다.
    await openNew()
    await loadedVendor()
    const info = screen.getByRole('region', { name: 'Deal 정보' })

    // then: Vendor 생성 버튼과 Product 선택 목록이 없다.
    expect(within(info).queryByRole('button', { name: /새 (Vendor|Product)|(Vendor|Product) (추가|등록)/ })).not.toBeInTheDocument()
    expect(within(info).queryByRole('combobox', { name: 'Product' })).not.toBeInTheDocument()
    expect(within(info).queryByRole('textbox', { name: 'Vendor' })).not.toBeInTheDocument()
  })
})

describe('Product 선택', () => {
  // Product를 비우고 저장하면 문구 없이 빈 Product로 등록된다.
  // 테스트 코드: DE-087
  it('registers with an empty product without any message', async () => {
    // given: Product만 비운 채 필수 값을 입력했다.
    const create = vi.spyOn(gateway.deals, 'create')
    const { user, location } = await openNew()
    await loadedVendor()
    await fillRequired(user, 'Product 비움')
    await user.type(productInput(), '   ')

    // when: 저장한다.
    await save(user)

    // then: 'Product를 입력하세요.'가 없고 요청의 product이 ''이며 상세로 간다.
    await waitFor(() => expect(location()).toMatch(DETAIL_URL))
    expect(screen.queryByText('Product를 입력하세요.')).not.toBeInTheDocument()
    expect(create).toHaveBeenCalledWith(expect.objectContaining({ product: '' }))
    expect((await gateway.deals.get(location().replace('/deals/', ''))).product).toBe('')
  })

  // Product를 건드리지 않고 저장해도 빈 Product로 등록된다.
  // 테스트 코드: DE-087
  it('registers with an untouched product field as an empty product', async () => {
    // given: Product 칸을 비워 둔 채 필수 값을 입력했다.
    const { user, location } = await openNew()
    await loadedVendor()
    await fillRequired(user, 'Product 안 건드림')

    // when: 저장한다.
    await save(user)

    // then: 빈 Product로 저장된다.
    await waitFor(() => expect(location()).toMatch(DETAIL_URL))
    expect((await gateway.deals.get(location().replace('/deals/', ''))).product).toBe('')
  })
})

describe('Vendor 필수', () => {
  // Vendor를 고르지 않으면 요청 없이 문구로 막고 Vendor 칸으로 포커스한 뒤, 고르면 등록된다.
  // 테스트 코드: DE-117
  it('blocks without a request, focuses the Vendor select, and registers once a vendor is chosen', async () => {
    // given: Vendor만 빼고 필수 값을 입력했다.
    const create = vi.spyOn(gateway.deals, 'create')
    const { user, location } = await openNew()
    await loadedVendor()
    await fillRequired(user, 'Vendor 미선택', false)

    // when: 저장한다.
    await save(user)

    // then: Vendor 칸 아래 문구가 보이고 Vendor 칸에 포커스가 가며 요청이 없다.
    const row = vendorSelect().closest('.kv-row, .field') as HTMLElement
    expect(await within(row).findByRole('alert')).toHaveTextContent('Vendor를 선택하세요.')
    await waitFor(() => expect(vendorSelect()).toHaveFocus())
    expect(create).not.toHaveBeenCalled()
    expect(location()).toBe('/deals/new')

    // when: Vendor Silverfort를 골라 다시 저장한다.
    await user.selectOptions(vendorSelect(), 'Silverfort')
    await save(user)

    // then: vendorId가 Silverfort id로 등록되어 상세로 간다.
    await waitFor(() => expect(location()).toMatch(DETAIL_URL))
    expect(create).toHaveBeenCalledWith(expect.objectContaining({ vendorId: seedVendorId('Silverfort') }))
  })
})

describe('저장', () => {
  // Product는 공백을 지우고 고른 Vendor id와 함께 저장된다.
  // 테스트 코드: DE-088
  it('saves the trimmed product text with the chosen vendor id', async () => {
    // given: Vendor를 골랐다.
    const { user, location } = await openNew()
    await loadedVendor()
    await user.selectOptions(vendorSelect(), 'Silverfort')
    await user.type(productInput(), '  ITDR ')
    await fillRequired(user, 'Vendor 연동 등록')

    // when: 공백이 든 Product로 저장한다.
    await save(user)

    // then: 요청에 Vendor id와 공백 없는 Product가 담긴다.
    await waitFor(() => expect(location()).toMatch(DETAIL_URL))
    const saved = await gateway.deals.get(location().replace('/deals/', ''))
    expect(saved.vendor).toEqual({ id: seedVendorId('Silverfort'), name: 'Silverfort' })
    expect(saved.product).toBe('ITDR')
  })

  // 수정 폼은 Vendor·Product을 채우고 Vendor를 바꿔도 Product를 유지한다.
  // 테스트 코드: DE-090
  it('loads the saved vendor and product into the edit form and keeps the product when the vendor changes', async () => {
    // when: 수정 화면을 연다. (Silverfort / MFA인 Deal)
    const { user, location, code } = await openEdit('누리통신 MFA')

    // then: 저장된 Vendor와 Product가 채워진다.
    await waitFor(() => expect(vendorSelect()).toHaveDisplayValue('Silverfort'))
    expect(productInput()).toHaveValue('MFA')

    // when: Vendor를 Okta로 바꾸고 저장한다.
    await user.selectOptions(vendorSelect(), 'Okta')
    expect(productInput()).toHaveValue('MFA')
    await save(user)

    // then: Vendor만 바뀌고 Product가 유지된다.
    await waitFor(() => expect(location()).toBe(`/deals/${code}`))
    const saved = await gateway.deals.get(code)
    expect(saved.vendor?.name).toBe('Okta')
    expect(saved.product).toBe('MFA')
  })

  // 수정 폼에서 바꾼 Product가 저장된다.
  // 테스트 코드: DE-090
  it('saves a changed product text from the edit form', async () => {
    // given: 수정 화면에 저장된 Product가 채워져 있다.
    const { user, location, code } = await openEdit('누리통신 MFA')
    await waitFor(() => expect(productInput()).toHaveValue('MFA'))

    // when: Product를 바꿔 저장한다.
    await user.clear(productInput())
    await user.type(productInput(), 'Identity Threat')
    await save(user)

    // then: 바뀐 Product가 저장된다.
    await waitFor(() => expect(location()).toBe(`/deals/${code}`))
    expect((await gateway.deals.get(code)).product).toBe('Identity Threat')
  })

  // Product를 비우면 문구 없이 빈 Product로 저장한다.
  // 테스트 코드: DE-090
  it('saves an emptied product from the edit form without a message', async () => {
    // given: 수정 화면에 저장된 Product가 채워져 있다.
    const update = vi.spyOn(gateway.deals, 'update')
    const { user, location, code } = await openEdit('누리통신 MFA')
    await waitFor(() => expect(productInput()).toHaveValue('MFA'))

    // when: Product를 비우고 저장한다.
    await user.clear(productInput())
    await save(user)

    // then: 문구 없이 product ''로 저장되고 상세로 간다.
    await waitFor(() => expect(location()).toBe(`/deals/${code}`))
    expect(screen.queryByText('Product를 입력하세요.')).not.toBeInTheDocument()
    expect(update).toHaveBeenCalledWith(code, expect.objectContaining({ product: '' }))
    expect((await gateway.deals.get(code)).product).toBe('')
  })

  // 서버의 Vendor·Product 오류 문구를 배너에 보이고 폼에 머문다.
  // 테스트 코드: DE-089
  it.each([
    '선택한 Vendor가 없습니다. 목록에서 다시 선택하세요.',
    'Product는 200자 이내로 입력하세요.',
  ])('shows the server message "%s" in the error banner and stays on the form', async (detail) => {
    // given: 등록 요청이 서버 문구로 거절된다.
    vi.spyOn(gateway.deals, 'create').mockRejectedValue(
      new ApiError(422, { type: 'https://sales.neoine.test/problems/invalid-value', title: 'x', status: 422, detail }),
    )
    const { user, location } = await openNew()
    await loadedVendor()
    await user.type(productInput(), 'ITDR')
    await fillRequired(user, '422 확인')

    // when: 저장한다.
    await save(user)

    // then: 배너에 서버 문구가 나오고 등록 화면에 머문다.
    expect(await screen.findByRole('alert')).toHaveTextContent(detail)
    expect(location()).toBe('/deals/new')
  })

  // 201자 Product는 서버 문구를 배너에 보인다.
  // 테스트 코드: DE-089
  it('shows the server message for a product over 200 characters from the real fake gateway', async () => {
    // given: 201자 Product를 입력했다.
    const { user, location } = await openNew()
    fireEvent.change(productInput(), { target: { value: 'a'.repeat(201) } })
    await fillRequired(user, '길이 초과')

    // when: 저장한다.
    await save(user)

    // then: 'Product는 200자 이내로 입력하세요.'가 배너에 나온다.
    expect(await screen.findByRole('alert')).toHaveTextContent('Product는 200자 이내로 입력하세요.')
    expect(location()).toBe('/deals/new')
  })
})
