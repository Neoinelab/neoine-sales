import { screen, waitFor, within } from '@testing-library/react'
import { describe, expect, it } from 'vitest'
import { gateway } from '../../../gateway'
import { seedVendorId } from '../../../test/fixtures/vendors'
import { renderAt } from '../../../test/mockApp'

type View = Awaited<ReturnType<typeof renderAt>>

async function openVendors(seed: 'sample' | 'empty' = 'sample') {
  const view = await renderAt('/admin/deal?tab=vendor', { role: 'admin', seed })
  if (seed === 'sample') await screen.findByRole('region', { name: 'Silverfort' })
  return view
}

const card = (vendor: string) => within(screen.getByRole('region', { name: vendor }))
const solutionRow = (vendor: string, solution: string) => within(card(vendor).getByRole('row', { name: new RegExp(solution) }))

async function solutionRowFound(vendor: string, solution: string) {
  return card(vendor).findByRole('row', { name: new RegExp(solution) })
}

async function addVendor(user: View['user'], name: string) {
  await user.type(screen.getByLabelText('새 Vendor 이름'), name)
  await user.click(screen.getByRole('button', { name: 'Vendor 추가' }))
}

async function addSolution(user: View['user'], vendor: string, name: string) {
  await user.type(card(vendor).getByLabelText('새 Solution 이름'), name)
  await user.click(card(vendor).getByRole('button', { name: 'Solution 추가' }))
}

describe('Vendor·Solution 탭 (AC-8)', () => {
  it('opens at ?tab=vendor and is selected', async () => {
    await openVendors()

    expect(screen.getByRole('tab', { name: 'Vendor·Solution' })).toHaveAttribute('aria-selected', 'true')
  })

  it('is reached from the tab list and keeps the choice in the URL', async () => {
    const { user, location } = await renderAt('/admin/deal', { role: 'admin' })
    await user.click(await screen.findByRole('tab', { name: 'Vendor·Solution' }))

    expect(location()).toBe('/admin/deal?tab=vendor')
    expect(await screen.findByRole('region', { name: 'Silverfort' })).toBeVisible()
  })

  it('explains the naming and deletion rules', async () => {
    await openVendors()

    expect(
      screen.getByText(
        'Vendor 이름은 대소문자 구분 없이 중복될 수 없고, Solution 이름은 같은 Vendor 안에서 중복될 수 없습니다. 사용 중인 항목은 이름을 바꿀 수 있지만 삭제할 수 없습니다.',
      ),
    ).toBeVisible()
  })

  it('lists vendors in name order with their solutions and the number of deals using each', async () => {
    await openVendors()

    const names = within(screen.getByRole('tabpanel'))
      .getAllByRole('region')
      .map((region) => within(region).getByRole('heading', { level: 3 }).textContent)
    expect(names).toEqual(['CrowdStrike', 'CyberArk', 'Okta', 'Palo Alto', 'SentinelOne', 'Silverfort', 'Splunk', 'Tenable', 'Veeam', 'Zscaler'])
    expect(card('Silverfort').getByText('Deal 7건')).toBeVisible()
    expect(solutionRow('Silverfort', 'ITDR').getByText('Deal 4건')).toBeVisible()
    expect(solutionRow('Silverfort', 'MFA').getByText('Deal 3건')).toBeVisible()
    expect(solutionRow('Splunk', 'SIEM').getByText('Deal 0건')).toBeVisible()
  })

  it('says so when a vendor has no solution', async () => {
    await openVendors()

    expect(card('Veeam').getByText('Solution이 없습니다.')).toBeVisible()
  })

  it('says so on a system without any vendor', async () => {
    await openVendors('empty')

    expect(await screen.findByText('등록된 Vendor가 없습니다.')).toBeVisible()
  })
})

describe('Vendor 추가·이름 수정 (AC-8)', () => {
  it('adds a vendor, shows it with zero deals and clears the input', async () => {
    const { user } = await openVendors()

    await addVendor(user, 'Acme')

    expect(await screen.findByRole('region', { name: 'Acme' })).toBeVisible()
    expect(card('Acme').getByText('Solution이 없습니다.')).toBeVisible()
    expect(screen.getByLabelText('새 Vendor 이름')).toHaveValue('')
  })

  it('renames a vendor in place, including one that deals use', async () => {
    const { user } = await openVendors()

    await user.click(card('Silverfort').getByRole('button', { name: 'Vendor 이름 수정' }))
    const input = screen.getByLabelText('Vendor 이름')
    await user.clear(input)
    await user.type(input, 'Silverfort Inc')
    await user.click(screen.getByRole('button', { name: '저장' }))

    expect(await screen.findByRole('region', { name: 'Silverfort Inc' })).toBeVisible()
    expect(screen.queryByRole('region', { name: 'Silverfort' })).not.toBeInTheDocument()
    expect(solutionRow('Silverfort Inc', 'ITDR').getByText('Deal 4건')).toBeVisible()
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

describe('Solution 추가·이름 수정 (AC-8)', () => {
  it('adds a solution under its vendor with zero deals', async () => {
    const { user } = await openVendors()

    await addSolution(user, 'Veeam', 'Backup')

    expect(await solutionRowFound('Veeam', 'Backup')).toBeTruthy()
    expect(solutionRow('Veeam', 'Backup').getByText('Deal 0건')).toBeVisible()
    expect(card('Veeam').queryByText('Solution이 없습니다.')).not.toBeInTheDocument()
  })

  it('renames a solution in place', async () => {
    const { user } = await openVendors()

    await user.click(solutionRow('Okta', 'SSO').getByRole('button', { name: '이름 수정' }))
    const input = screen.getByLabelText('Solution 이름')
    await user.clear(input)
    await user.type(input, 'Workforce SSO')
    await user.click(screen.getByRole('button', { name: '저장' }))

    expect(await card('Okta').findByText('Workforce SSO')).toBeVisible()
    expect(card('Okta').queryByText('SSO')).not.toBeInTheDocument()
  })

  it('shows the duplicate message for a name of the same vendor ignoring case and accepts the same name under another vendor', async () => {
    const { user } = await openVendors()

    await addSolution(user, 'Silverfort', 'itdr')
    expect(await screen.findByRole('alert')).toHaveTextContent('이 Vendor에 이미 있는 Solution 이름입니다.')

    await addSolution(user, 'Okta', 'ITDR')
    expect(await card('Okta').findByText('ITDR')).toBeVisible()
  })
})

describe('삭제 (AC-8)', () => {
  it('asks with the number of solutions that go with the vendor', async () => {
    const { user } = await openVendors()

    await user.click(card('Splunk').getByRole('button', { name: 'Vendor 삭제' }))

    const dialog = await screen.findByRole('dialog', { name: 'Vendor 삭제' })
    expect(dialog).toHaveTextContent("'Splunk' Vendor를 삭제할까요? 소속 Solution 2개도 함께 삭제됩니다.")
  })

  it('omits the second sentence when the vendor has no solution', async () => {
    const { user } = await openVendors()

    await user.click(card('Veeam').getByRole('button', { name: 'Vendor 삭제' }))

    const dialog = await screen.findByRole('dialog', { name: 'Vendor 삭제' })
    expect(dialog).toHaveTextContent("'Veeam' Vendor를 삭제할까요?")
    expect(dialog).not.toHaveTextContent('함께 삭제됩니다')
  })

  it('deletes an unused vendor with its solutions after confirmation', async () => {
    const { user } = await openVendors()

    await user.click(card('Splunk').getByRole('button', { name: 'Vendor 삭제' }))
    await user.click(within(await screen.findByRole('dialog', { name: 'Vendor 삭제' })).getByRole('button', { name: '삭제' }))

    await waitFor(() => expect(screen.queryByRole('region', { name: 'Splunk' })).not.toBeInTheDocument())
    const remaining = await gateway.vendors.list()
    expect(remaining.some((v) => v.name === 'Splunk')).toBe(false)
  })

  it('keeps the vendor when the confirmation is declined', async () => {
    const { user } = await openVendors()

    await user.click(card('Veeam').getByRole('button', { name: 'Vendor 삭제' }))
    await user.click(within(await screen.findByRole('dialog')).getByRole('button', { name: '취소' }))

    expect(screen.getByRole('region', { name: 'Veeam' })).toBeVisible()
  })

  it('shows the 409 message in the error banner when a deal uses the vendor and keeps everything', async () => {
    const { user } = await openVendors()

    await user.click(card('Silverfort').getByRole('button', { name: 'Vendor 삭제' }))
    await user.click(within(await screen.findByRole('dialog', { name: 'Vendor 삭제' })).getByRole('button', { name: '삭제' }))

    expect(await screen.findByRole('alert')).toHaveTextContent('사용 중인 Vendor는 삭제할 수 없습니다. (Deal 7건)')
    expect(screen.getByRole('region', { name: 'Silverfort' })).toBeVisible()
    expect(solutionRow('Silverfort', 'ITDR')).toBeTruthy()
    expect((await gateway.vendors.list()).find((v) => v.id === seedVendorId('Silverfort'))?.solutions).toHaveLength(2)
  })

  it('deletes an unused solution after confirmation and asks for it by name', async () => {
    const { user } = await openVendors()

    await user.click(solutionRow('Splunk', 'SOAR').getByRole('button', { name: '삭제' }))
    const dialog = await screen.findByRole('dialog', { name: 'Solution 삭제' })
    expect(dialog).toHaveTextContent("'SOAR' Solution을 삭제할까요?")
    await user.click(within(dialog).getByRole('button', { name: '삭제' }))

    await waitFor(() => expect(card('Splunk').queryByText('SOAR')).not.toBeInTheDocument())
    expect(card('Splunk').getByText('SIEM')).toBeVisible()
  })

  it('shows the 409 message when a deal uses the solution', async () => {
    const { user } = await openVendors()

    await user.click(solutionRow('Silverfort', 'ITDR').getByRole('button', { name: '삭제' }))
    await user.click(within(await screen.findByRole('dialog', { name: 'Solution 삭제' })).getByRole('button', { name: '삭제' }))

    expect(await screen.findByRole('alert')).toHaveTextContent('사용 중인 Solution은 삭제할 수 없습니다. (Deal 4건)')
    expect(card('Silverfort').getByText('ITDR')).toBeVisible()
  })
})
