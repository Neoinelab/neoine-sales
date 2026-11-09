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
  const found = shown.find((c) => c.status === status && shown.filter((x) => x.dealName === c.dealName).length === 1)
  if (!found) throw new Error(`첫 쪽에 ${status} 계약이 없다`)
  return found
}
const rowOf = (code: string) => rows().find((r) => within(r).getAllByRole('cell')[0]?.textContent === code)

async function openEdit(c: LicenseContract, role: 'admin' | 'sales' | 'user' = 'sales') {
  const view = await renderAt('/contracts', { role })
  await screen.findByRole('table', { name: '계약 목록' }, LOAD)
  await view.user.click(within(rowOf(c.dealName)!).getAllByRole('cell')[1]!)
  return { ...view, dlg: await screen.findByRole('dialog', { name: `계약 수정 - ${c.dealName}` }) }
}
const statusGroup = (dlg: HTMLElement) => within(dlg).getByRole('group', { name: '상태' })

describe('계약 종료 (AC14)', () => {
  // 종료가 아닌 계약의 상태 묶음에 계약 종료 버튼이 있다.
  // 테스트 코드: LC-057
  it.each(['not_issued', 'issued_new', 'issued_renewal'] as const)('has a 계약 종료 button in the status group of an %s contract', async (status) => {
    // given: sales로 연 미발급·발급(신규)·발급(갱신) 계약 대화상자
    // when: 대화상자를 연다
    const { dlg } = await openEdit(first(status))

    // then: 상태 묶음에 계약 종료 버튼이 보인다
    expect(within(statusGroup(dlg)).getByRole('button', { name: '계약 종료' })).toBeVisible()
  })

  // 종료 계약에는 계약 종료 버튼이 없다.
  // 테스트 코드: LC-057
  it('has no 계약 종료 button for an ended contract', async () => {
    // given: 종료 계약 대화상자
    // when: 대화상자를 연다
    const { dlg } = await openEdit(first('ended'))

    // then: 계약 종료 버튼이 없다
    expect(within(statusGroup(dlg)).queryByRole('button', { name: '계약 종료' })).not.toBeInTheDocument()
  })

  // user에게는 계약 종료 버튼이 없다.
  // 테스트 코드: LC-038
  it('has no 계약 종료 button for a read-only user', async () => {
    // given: user로 연 계약 대화상자
    // when: 대화상자를 연다
    const { dlg } = await openEdit(first('issued_new'), 'user')

    // then: 계약 종료 버튼이 없다
    expect(within(statusGroup(dlg)).queryByRole('button', { name: '계약 종료' })).not.toBeInTheDocument()
  })

  // 계약 종료는 확인 창을 띄우고 취소하면 요청하지 않는다.
  // 테스트 코드: LC-057
  it('asks for confirmation and ends nothing when cancelled', async () => {
    // given: 발급(신규) 계약 대화상자
    const c = first('issued_new')
    const end = vi.spyOn(gateway.licenseContracts, 'end')
    const { user, dlg } = await openEdit(c)

    await user.click(within(statusGroup(dlg)).getByRole('button', { name: '계약 종료' }))
    const confirm = await screen.findByRole('dialog', { name: '계약 종료 확인' })
    await user.click(within(confirm).getByRole('button', { name: '취소' }))

    // when: 계약 종료를 누르고 확인 창에서 취소한다
    await waitFor(() => expect(screen.queryByRole('dialog', { name: '계약 종료 확인' })).not.toBeInTheDocument())
    // then: 종료 요청이 없고 대화상자는 그대로다
    expect(end).not.toHaveBeenCalled()
    expect(screen.getByRole('dialog', { name: `계약 수정 - ${c.dealName}` })).toBeVisible()
  })

  // 확인하면 종료 요청이 가고 알림과 표의 종료가 보인다.
  // 테스트 코드: LC-057
  it('ends the contract through the gateway after confirmation and shows 종료 with the notice', async () => {
    // given: 발급(신규) 계약 대화상자
    const c = first('issued_new')
    const end = vi.spyOn(gateway.licenseContracts, 'end')
    const { user, dlg } = await openEdit(c)

    await user.click(within(statusGroup(dlg)).getByRole('button', { name: '계약 종료' }))
    // when: 계약 종료를 누르고 확인 창에서 종료를 누른다
    await user.click(within(await screen.findByRole('dialog', { name: '계약 종료 확인' })).getByRole('button', { name: '종료' }))

    // then: 종료 요청, 계약을 종료했습니다 알림, 표의 종료가 보인다
    expect(await screen.findByText('계약을 종료했습니다.')).toBeVisible()
    expect(end).toHaveBeenCalledWith(c.id)
    await waitFor(() => expect(within(rowOf(c.dealName)!).getAllByRole('cell')[7]?.textContent).toBe('종료'))
  })

  // 종료가 409로 실패하면 서버 문구를 보인다.
  // 테스트 코드: LC-037
  it('shows the server message when ending fails (409)', async () => {
    // given: 서버가 종료에 409를 주도록 준비한 계약
    const c = first('not_issued')
    vi.spyOn(gateway.licenseContracts, 'end').mockRejectedValue(Object.assign(new Error('이미 종료된 계약입니다.'), { status: 409 }))
    const { user, dlg } = await openEdit(c)

    await user.click(within(statusGroup(dlg)).getByRole('button', { name: '계약 종료' }))
    // when: 계약 종료를 확인한다
    await user.click(within(await screen.findByRole('dialog', { name: '계약 종료 확인' })).getByRole('button', { name: '종료' }))

    // then: 서버 문구가 보인다
    expect(await screen.findByText('이미 종료된 계약입니다.')).toBeVisible()
  })
})

describe('계약 삭제 (AC15)', () => {
  // admin은 어떤 상태든 삭제 버튼을 보고 확인 뒤 삭제한다.
  // 테스트 코드: LC-061
  it.each(['not_issued', 'issued_new', 'ended'] as const)('shows 삭제 to an admin for an %s contract and deletes it after confirmation', async (status) => {
    // given: admin으로 연 미발급·발급(신규)·종료 계약 대화상자
    const c = first(status)
    const remove = vi.spyOn(gateway.licenseContracts, 'remove')
    const { user, dlg } = await openEdit(c, 'admin')

    // when: 삭제를 누르고 확인 창에서 삭제를 누른다
    await user.click(within(dlg).getByRole('button', { name: '삭제' }))
    const confirm = await screen.findByRole('dialog', { name: '계약 삭제' })
    // then: 삭제 요청, 계약을 삭제했습니다 알림, 표에서 행이 사라진다
    expect(confirm).toHaveTextContent(c.dealName)
    await user.click(within(confirm).getByRole('button', { name: '삭제' }))

    expect(await screen.findByText('계약을 삭제했습니다.')).toBeVisible()
    expect(remove).toHaveBeenCalledWith(c.id)
    await waitFor(() => expect(rowOf(c.dealName)).toBeUndefined())
  })

  // 삭제 확인에서 취소하면 계약이 남는다.
  // 테스트 코드: LC-061
  it('keeps the contract when the delete confirmation is cancelled', async () => {
    // given: admin으로 연 계약 대화상자
    const c = first('issued_new')
    const remove = vi.spyOn(gateway.licenseContracts, 'remove')
    const { user, dlg } = await openEdit(c, 'admin')

    await user.click(within(dlg).getByRole('button', { name: '삭제' }))
    // when: 삭제를 누르고 확인 창에서 취소한다
    await user.click(within(await screen.findByRole('dialog', { name: '계약 삭제' })).getByRole('button', { name: '취소' }))

    // then: 삭제 요청이 없고 계약이 남는다
    expect(remove).not.toHaveBeenCalled()
    expect(rowOf(c.dealName)).toBeDefined()
  })

  // sales와 user에게는 삭제 버튼이 없다.
  // 테스트 코드: LC-061
  it.each(['sales', 'user'] as const)('does not show 삭제 to a %s', async (role) => {
    // given: sales 또는 user로 연 계약 대화상자
    // when: 대화상자를 연다
    const { dlg } = await openEdit(first('issued_new'), role)

    // then: 삭제 버튼이 없다
    expect(within(dlg).queryByRole('button', { name: '삭제' })).not.toBeInTheDocument()
  })
})
