import { screen, waitFor, within } from '@testing-library/react'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { gateway } from '../../gateway'
import type { LicenseContract } from '../../shared/model/types'
import { allContracts } from '../../test/licenseContracts'
import { renderAt } from '../../test/mockApp'
import { pinClock, unpinClock } from '../../test/partnerMeetings'

/** 계약 종료(AC14)와 admin 삭제(AC15). 자동 종료는 없다. 시계는 2027-03-15 고정. */
const LOAD = { timeout: 8000 }

let contracts: LicenseContract[] = []
beforeEach(async () => {
  pinClock()
  contracts = await allContracts()
})
afterEach(() => {
  unpinClock()
  vi.restoreAllMocks()
})

const table = () => screen.getByRole('table', { name: '계약 목록' })
const rows = () => within(table()).getAllByRole('row').slice(1)
const first = (status: LicenseContract['status']) => {
  const shown = contracts.slice(0, 50)
  const found = shown.find((c) => c.status === status && shown.filter((x) => x.dealCode === c.dealCode).length === 1)
  if (!found) throw new Error(`첫 쪽에 ${status} 계약이 없다`)
  return found
}
const rowOf = (code: string) => rows().find((r) => within(r).getAllByRole('cell')[0]?.textContent === code)

async function openEdit(c: LicenseContract, role: 'admin' | 'sales' | 'user' = 'sales') {
  const view = await renderAt('/contracts', { role })
  await screen.findByRole('table', { name: '계약 목록' }, LOAD)
  await view.user.click(within(rowOf(c.dealCode)!).getAllByRole('cell')[1]!)
  return { ...view, dlg: await screen.findByRole('dialog', { name: '계약 수정' }) }
}
const statusGroup = (dlg: HTMLElement) => within(dlg).getByRole('group', { name: '상태' })

describe('계약 종료 (AC14)', () => {
  it.each(['not_issued', 'issued_new', 'issued_renewal'] as const)('has a 계약 종료 button in the status group of an %s contract', async (status) => {
    const { dlg } = await openEdit(first(status))

    expect(within(statusGroup(dlg)).getByRole('button', { name: '계약 종료' })).toBeVisible()
  })

  it('has no 계약 종료 button for an ended contract', async () => {
    const { dlg } = await openEdit(first('ended'))

    expect(within(statusGroup(dlg)).queryByRole('button', { name: '계약 종료' })).not.toBeInTheDocument()
  })

  it('has no 계약 종료 button for a read-only user', async () => {
    const { dlg } = await openEdit(first('issued_new'), 'user')

    expect(within(statusGroup(dlg)).queryByRole('button', { name: '계약 종료' })).not.toBeInTheDocument()
  })

  it('asks for confirmation and ends nothing when cancelled', async () => {
    const c = first('issued_new')
    const end = vi.spyOn(gateway.licenseContracts, 'end')
    const { user, dlg } = await openEdit(c)

    await user.click(within(statusGroup(dlg)).getByRole('button', { name: '계약 종료' }))
    const confirm = await screen.findByRole('dialog', { name: '계약 종료 확인' })
    await user.click(within(confirm).getByRole('button', { name: '취소' }))

    await waitFor(() => expect(screen.queryByRole('dialog', { name: '계약 종료 확인' })).not.toBeInTheDocument())
    expect(end).not.toHaveBeenCalled()
    expect(screen.getByRole('dialog', { name: '계약 수정' })).toBeVisible()
  })

  it('ends the contract through the gateway after confirmation and shows 종료 with the notice', async () => {
    const c = first('issued_new')
    const end = vi.spyOn(gateway.licenseContracts, 'end')
    const { user, dlg } = await openEdit(c)

    await user.click(within(statusGroup(dlg)).getByRole('button', { name: '계약 종료' }))
    await user.click(within(await screen.findByRole('dialog', { name: '계약 종료 확인' })).getByRole('button', { name: '종료' }))

    expect(await screen.findByText('계약을 종료했습니다.')).toBeVisible()
    expect(end).toHaveBeenCalledWith(c.id)
    await waitFor(() => expect(within(rowOf(c.dealCode)!).getAllByRole('cell')[7]?.textContent).toBe('종료'))
  })

  it('shows the server message when ending fails (409)', async () => {
    const c = first('not_issued')
    vi.spyOn(gateway.licenseContracts, 'end').mockRejectedValue(Object.assign(new Error('이미 종료된 계약입니다.'), { status: 409 }))
    const { user, dlg } = await openEdit(c)

    await user.click(within(statusGroup(dlg)).getByRole('button', { name: '계약 종료' }))
    await user.click(within(await screen.findByRole('dialog', { name: '계약 종료 확인' })).getByRole('button', { name: '종료' }))

    expect(await screen.findByText('이미 종료된 계약입니다.')).toBeVisible()
  })
})

describe('계약 삭제 (AC15)', () => {
  it.each(['not_issued', 'issued_new', 'ended'] as const)('shows 삭제 to an admin for an %s contract and deletes it after confirmation', async (status) => {
    const c = first(status)
    const remove = vi.spyOn(gateway.licenseContracts, 'remove')
    const { user, dlg } = await openEdit(c, 'admin')

    await user.click(within(dlg).getByRole('button', { name: '삭제' }))
    const confirm = await screen.findByRole('dialog', { name: '계약 삭제' })
    expect(confirm).toHaveTextContent(c.dealCode)
    await user.click(within(confirm).getByRole('button', { name: '삭제' }))

    expect(await screen.findByText('계약을 삭제했습니다.')).toBeVisible()
    expect(remove).toHaveBeenCalledWith(c.id)
    await waitFor(() => expect(rowOf(c.dealCode)).toBeUndefined())
  })

  it('keeps the contract when the delete confirmation is cancelled', async () => {
    const c = first('issued_new')
    const remove = vi.spyOn(gateway.licenseContracts, 'remove')
    const { user, dlg } = await openEdit(c, 'admin')

    await user.click(within(dlg).getByRole('button', { name: '삭제' }))
    await user.click(within(await screen.findByRole('dialog', { name: '계약 삭제' })).getByRole('button', { name: '취소' }))

    expect(remove).not.toHaveBeenCalled()
    expect(rowOf(c.dealCode)).toBeDefined()
  })

  it.each(['sales', 'user'] as const)('does not show 삭제 to a %s', async (role) => {
    const { dlg } = await openEdit(first('issued_new'), role)

    expect(within(dlg).queryByRole('button', { name: '삭제' })).not.toBeInTheDocument()
  })
})
