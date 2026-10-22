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

describe('Vendor 탭 (AC-5)', () => {
  it('is named Vendor, opens at ?tab=vendor and is selected', async () => {
    await openVendors()

    expect(screen.getByRole('tab', { name: 'Vendor' })).toHaveAttribute('aria-selected', 'true')
    expect(screen.queryByRole('tab', { name: 'Vendor·Solution' })).not.toBeInTheDocument()
  })

  it('is reached from the tab list and keeps the choice in the URL', async () => {
    const { user, location } = await renderAt('/admin/deal', { role: 'admin' })
    await user.click(await screen.findByRole('tab', { name: 'Vendor' }))

    expect(location()).toBe('/admin/deal?tab=vendor')
    expect(await screen.findByRole('table', { name: 'Vendor 목록' })).toBeVisible()
  })

  it('explains the naming and deletion rules without mentioning solutions', async () => {
    await openVendors()

    expect(screen.getByText(GUIDE)).toBeVisible()
  })

  it('lists vendors in a single table in name order with the number of deals using each', async () => {
    await openVendors()

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

  it('has no solution controls at all', async () => {
    await openVendors()

    expect(screen.queryByRole('button', { name: 'Solution 추가' })).not.toBeInTheDocument()
    expect(screen.queryByLabelText('새 Solution 이름')).not.toBeInTheDocument()
    expect(screen.queryByText('Solution이 없습니다.')).not.toBeInTheDocument()
    expect(screen.queryByRole('region', { name: 'Silverfort' })).not.toBeInTheDocument()
    expect(screen.queryByText('ITDR')).not.toBeInTheDocument()
  })

  it('says so on a system without any vendor', async () => {
    await openVendors('empty')

    expect(await screen.findByText('등록된 Vendor가 없습니다.')).toBeVisible()
  })
})

describe('Vendor 추가·이름 수정 (AC-5)', () => {
  it('adds a vendor, shows it with zero deals and clears the input', async () => {
    const { user } = await openVendors()

    await addVendor(user, 'Acme')

    expect(await screen.findByText('Acme')).toBeVisible()
    expect(vendorRow('Acme').getByText('Deal 0건')).toBeVisible()
    expect(screen.getByLabelText('새 Vendor 이름')).toHaveValue('')
  })

  it('renames a vendor in place, including one that deals use', async () => {
    const { user } = await openVendors()

    await user.click(vendorRow('Silverfort').getByRole('button', { name: '이름 수정' }))
    const input = screen.getByLabelText('Vendor 이름')
    await user.clear(input)
    await user.type(input, 'Silverfort Inc')
    await user.click(screen.getByRole('button', { name: '저장' }))

    expect(await screen.findByText('Silverfort Inc')).toBeVisible()
    expect(vendorRow('Silverfort Inc').getByText('Deal 7건')).toBeVisible()
  })

  it.each([
    ['silverfort', '이미 있는 Vendor 이름입니다.'],
    ['   ', 'Vendor 이름을 입력하세요.'],
    ['v'.repeat(101), 'Vendor 이름은 100자 이내로 입력하세요.'],
  ])('shows the server message for the vendor name "%s"', async (name, message) => {
    const { user } = await openVendors()

    if (name.trim() === '') await user.click(screen.getByRole('button', { name: 'Vendor 추가' }))
    else await addVendor(user, name)

    expect(await screen.findByRole('alert')).toHaveTextContent(message)
  })
})

describe('삭제 (AC-4, AC-5)', () => {
  it('confirms with a plain message that does not mention solutions', async () => {
    const { user } = await openVendors()

    await user.click(vendorRow('Splunk').getByRole('button', { name: '삭제' }))

    const dialog = await screen.findByRole('dialog', { name: 'Vendor 삭제' })
    expect(dialog).toHaveTextContent("'Splunk' Vendor를 삭제할까요?")
    expect(dialog).not.toHaveTextContent('Solution')
  })

  it('deletes an unused vendor after confirmation', async () => {
    const { user } = await openVendors()

    await user.click(vendorRow('Splunk').getByRole('button', { name: '삭제' }))
    await user.click(within(await screen.findByRole('dialog', { name: 'Vendor 삭제' })).getByRole('button', { name: '삭제' }))

    await waitFor(() => expect(within(table()).queryByText('Splunk')).not.toBeInTheDocument())
    expect((await gateway.vendors.list()).some((v) => v.name === 'Splunk')).toBe(false)
  })

  it('keeps the vendor when the confirmation is declined', async () => {
    const { user } = await openVendors()

    await user.click(vendorRow('Veeam').getByRole('button', { name: '삭제' }))
    await user.click(within(await screen.findByRole('dialog')).getByRole('button', { name: '취소' }))

    expect(within(table()).getByText('Veeam')).toBeVisible()
  })

  it('shows the server message in the error banner when a deal uses the vendor and keeps it', async () => {
    const { user } = await openVendors()

    await user.click(vendorRow('Silverfort').getByRole('button', { name: '삭제' }))
    await user.click(within(await screen.findByRole('dialog', { name: 'Vendor 삭제' })).getByRole('button', { name: '삭제' }))

    expect(await screen.findByRole('alert')).toHaveTextContent('사용 중인 Vendor는 삭제할 수 없습니다. (Deal 7건)')
    expect(within(table()).getByText('Silverfort')).toBeVisible()
    expect((await gateway.vendors.list()).some((v) => v.id === seedVendorId('Silverfort'))).toBe(true)
  })
})
