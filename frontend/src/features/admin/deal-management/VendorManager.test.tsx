import { screen, waitFor, within } from '@testing-library/react'
import { describe, expect, it } from 'vitest'
import { gateway } from '../../../gateway'
import { seedVendorId } from '../../../test/fixtures/vendors'
import { renderAt } from '../../../test/mockApp'

type View = Awaited<ReturnType<typeof renderAt>>

const GUIDE = 'Vendor 이름은 대소문자 구분 없이 중복될 수 없습니다. 사용 중인 Vendor는 이름을 바꿀 수 있지만 삭제할 수 없습니다.'

async function openVendors(seed: 'sample' | 'empty' = 'sample') {
  const view = await renderAt('/admin/deal?tab=vendor', { role: 'admin', seed })
  await screen.findByRole('table', { name: 'Vendor 목록' })
  if (seed === 'sample') await screen.findByText('Silverfort')
  return view
}

const table = () => screen.getByRole('table', { name: 'Vendor 목록' })
const vendorRow = (name: string) => within(within(table()).getByRole('row', { name: new RegExp(name) }))

async function addVendor(user: View['user'], name: string) {
  const form = screen.getByRole('form', { name: 'Vendor 추가' })
  await user.type(within(form).getByLabelText('새 Vendor 이름'), name)
  await user.click(within(form).getByRole('button', { name: 'Vendor 추가' }))
}

describe('Vendor 탭', () => {
  // 탭 이름은 Vendor이고 ?tab=vendor 주소로 열리면 선택된다.
  // 테스트 코드: CL-077
  it('is named Vendor, opens at ?tab=vendor and is selected', async () => {
    // when: ?tab=vendor 주소로 연다
    await openVendors()

    // then: Vendor 탭이 선택되어 있고 예전 탭 이름은 없다
    expect(screen.getByRole('tab', { name: 'Vendor' })).toHaveAttribute('aria-selected', 'true')
    expect(screen.queryByRole('tab', { name: 'Vendor·Solution' })).not.toBeInTheDocument()
  })

  // 탭을 누르면 Vendor 탭이 열리고 주소가 ?tab=vendor로 바뀐다.
  // 테스트 코드: CL-077
  it('is reached from the tab list and keeps the choice in the URL', async () => {
    // given: 탭 없이 Deal 관리 화면을 연다
    const { user, location } = await renderAt('/admin/deal', { role: 'admin' })
    // when: Vendor 탭을 누른다
    await user.click(await screen.findByRole('tab', { name: 'Vendor' }))

    // then: 주소가 ?tab=vendor이고 Vendor 표가 보인다
    expect(location()).toBe('/admin/deal?tab=vendor')
    expect(await screen.findByRole('table', { name: 'Vendor 목록' })).toBeVisible()
  })

  // Vendor 탭은 Solution 언급 없이 이름·삭제 규칙을 안내한다.
  // 테스트 코드: CL-087
  it('explains the naming and deletion rules without mentioning solutions', async () => {
    // when: Vendor 탭을 연다
    await openVendors()

    // then: 안내 문구가 보인다
    expect(screen.getByText(GUIDE)).toBeVisible()
  })

  // Vendor는 이름순 단일 표에 사용 Deal 수와 함께 나온다.
  // 테스트 코드: CL-087
  it('lists vendors in a single table in name order with the number of deals using each', async () => {
    // when: Vendor 탭을 연다
    await openVendors()

    // then: 머리글 3칸, 이름순 행, 'Deal n건'과 행 버튼이 보인다
    const headers = within(table()).getAllByRole('columnheader').map((h) => h.textContent)
    expect(headers).toEqual(['이름', '사용', '작업'])
    const names = within(table())
      .getAllByRole('row')
      .slice(1)
      .map((r) => within(r).getAllByRole('cell')[0]?.textContent)
    expect(names).toEqual(['CrowdStrike', 'CyberArk', 'Okta', 'Palo Alto', 'SentinelOne', 'Silverfort', 'Splunk', 'Tenable', 'Veeam', 'Zscaler'])
    expect(vendorRow('Silverfort').getByText('Deal 7건')).toBeVisible()
    expect(vendorRow('Splunk').getByText('Deal 0건')).toBeVisible()
    expect(vendorRow('Silverfort').getByRole('button', { name: '이름 수정' })).toBeVisible()
    expect(vendorRow('Silverfort').getByRole('button', { name: '삭제' })).toBeVisible()
  })

  // Vendor 탭에는 Solution 관련 칸·버튼·문구가 없다.
  // 테스트 코드: CL-087, CL-062
  it('has no solution controls at all', async () => {
    // when: Vendor 탭을 연다
    await openVendors()

    // then: Solution 컨트롤이 하나도 없다
    expect(screen.queryByRole('button', { name: 'Solution 추가' })).not.toBeInTheDocument()
    expect(screen.queryByLabelText('새 Solution 이름')).not.toBeInTheDocument()
    expect(screen.queryByText('Solution이 없습니다.')).not.toBeInTheDocument()
    expect(screen.queryByRole('region', { name: 'Silverfort' })).not.toBeInTheDocument()
    expect(screen.queryByText('ITDR')).not.toBeInTheDocument()
  })

  // Vendor가 없는 시스템은 안내 문구를 보인다.
  // 테스트 코드: CL-087
  it('says so on a system without any vendor', async () => {
    // when: Vendor가 없는 시스템에서 탭을 연다
    await openVendors('empty')

    // then: '등록된 Vendor가 없습니다.'가 보인다
    expect(await screen.findByText('등록된 Vendor가 없습니다.')).toBeVisible()
  })
})

describe('Vendor 추가·이름 수정', () => {
  // Vendor를 추가하면 'Deal 0건'으로 나타나고 입력이 비워진다.
  // 테스트 코드: CL-088
  it('adds a vendor, shows it with zero deals and clears the input', async () => {
    // given: Vendor 탭이 열려 있다
    const { user } = await openVendors()

    // when: 'Acme'를 추가한다
    await addVendor(user, 'Acme')

    // then: 'Deal 0건'으로 보이고 입력은 비어 있다
    expect(await screen.findByText('Acme')).toBeVisible()
    expect(vendorRow('Acme').getByText('Deal 0건')).toBeVisible()
    expect(screen.getByLabelText('새 Vendor 이름')).toHaveValue('')
  })

  // Deal이 쓰는 Vendor도 이름을 바꿔 저장하면 같은 자리에서 새 이름과 사용 수가 보인다.
  // 테스트 코드: CL-088
  it('renames a vendor in place, including one that deals use', async () => {
    // given: Vendor 탭이 열려 있다
    const { user } = await openVendors()

    // when: 'Silverfort'를 'Silverfort Inc'로 바꿔 저장한다
    await user.click(vendorRow('Silverfort').getByRole('button', { name: '이름 수정' }))
    const input = screen.getByLabelText('Vendor 이름')
    await user.clear(input)
    await user.type(input, 'Silverfort Inc')
    await user.click(screen.getByRole('button', { name: '저장' }))

    // then: 새 이름과 'Deal 7건'이 보인다
    expect(await screen.findByText('Silverfort Inc')).toBeVisible()
    expect(vendorRow('Silverfort Inc').getByText('Deal 7건')).toBeVisible()
  })

  // 중복·빈 이름·101자 이름의 추가는 서버 문구를 오류 배너에 보인다.
  // 테스트 코드: CL-088
  it.each([
    ['silverfort', '이미 있는 Vendor 이름입니다.'],
    ['   ', 'Vendor 이름을 입력하세요.'],
    ['v'.repeat(101), 'Vendor 이름은 100자 이내로 입력하세요.'],
  ])('shows the server message for the vendor name "%s"', async (name, message) => {
    // given: Vendor 탭이 열려 있다
    const { user } = await openVendors()

    // when: 해당 이름으로 Vendor를 추가한다
    if (name.trim() === '') await user.click(screen.getByRole('button', { name: 'Vendor 추가' }))
    else await addVendor(user, name)

    // then: 서버 문구가 오류 배너에 보인다
    expect(await screen.findByRole('alert')).toHaveTextContent(message)
  })
})

describe('삭제', () => {
  // 삭제 확인 창은 Solution 언급 없이 Vendor 이름만 묻는다.
  // 테스트 코드: CL-089
  it('confirms with a plain message that does not mention solutions', async () => {
    // given: Vendor 탭이 열려 있다
    const { user } = await openVendors()

    // when: 'Splunk'의 삭제 버튼을 누른다
    await user.click(vendorRow('Splunk').getByRole('button', { name: '삭제' }))

    // then: 'Vendor 삭제' 창에 문구가 보이고 Solution은 없다
    const dialog = await screen.findByRole('dialog', { name: 'Vendor 삭제' })
    expect(dialog).toHaveTextContent("'Splunk' Vendor를 삭제할까요?")
    expect(dialog).not.toHaveTextContent('Solution')
  })

  // 쓰이지 않는 Vendor는 확인하면 삭제된다.
  // 테스트 코드: CL-089
  it('deletes an unused vendor after confirmation', async () => {
    // given: Vendor 탭이 열려 있다
    const { user } = await openVendors()

    // when: 'Splunk'를 삭제 확인한다
    await user.click(vendorRow('Splunk').getByRole('button', { name: '삭제' }))
    await user.click(within(await screen.findByRole('dialog', { name: 'Vendor 삭제' })).getByRole('button', { name: '삭제' }))

    // then: 표와 목록에서 사라진다
    await waitFor(() => expect(within(table()).queryByText('Splunk')).not.toBeInTheDocument())
    expect((await gateway.vendors.list()).some((v) => v.name === 'Splunk')).toBe(false)
  })

  // 삭제 확인에서 취소하면 Vendor가 남는다.
  // 테스트 코드: CL-089
  it('keeps the vendor when the confirmation is declined', async () => {
    // given: Vendor 탭이 열려 있다
    const { user } = await openVendors()

    // when: 'Veeam'의 삭제 확인에서 취소한다
    await user.click(vendorRow('Veeam').getByRole('button', { name: '삭제' }))
    await user.click(within(await screen.findByRole('dialog')).getByRole('button', { name: '취소' }))

    // then: Vendor가 그대로 있다
    expect(within(table()).getByText('Veeam')).toBeVisible()
  })

  // Deal이 쓰는 Vendor를 지우면 서버 문구가 배너에 보이고 Vendor는 남는다.
  // 테스트 코드: CL-089
  it('shows the server message in the error banner when a deal uses the vendor and keeps it', async () => {
    // given: Vendor 탭이 열려 있다
    const { user } = await openVendors()

    // when: 'Silverfort'를 삭제 확인한다
    await user.click(vendorRow('Silverfort').getByRole('button', { name: '삭제' }))
    await user.click(within(await screen.findByRole('dialog', { name: 'Vendor 삭제' })).getByRole('button', { name: '삭제' }))

    // then: '(Deal 7건)' 문구가 배너에 보이고 Vendor가 남는다
    expect(await screen.findByRole('alert')).toHaveTextContent('사용 중인 Vendor는 삭제할 수 없습니다. (Deal 7건)')
    expect(within(table()).getByText('Silverfort')).toBeVisible()
    expect((await gateway.vendors.list()).some((v) => v.id === seedVendorId('Silverfort'))).toBe(true)
  })
})
