import { screen, waitFor, within } from '@testing-library/react'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { gateway } from '../../gateway'
import { ApiError } from '../../shared/api/problem'
import type { LicenseContract } from '../../shared/model/types'
import { allContracts, dotted, nextDay } from '../../test/licenseContracts'
import { renderAt } from '../../test/mockApp'
import { pinClock, unpinClock } from '../../test/partnerMeetings'
import { STATUS_LABELS } from './contractLabels'

/** 계약 수정 대화상자의 상태 묶음과 라이선스 칸, 발급·갱신 버튼(AC12~AC14). 서버가 종료일을 계산한다. 시계는 2027-03-15 고정. */
const LOAD = { timeout: 8000 }
const TODAY_TEXT = '2027.03.15'

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
/** 종료일은 '종료일' 이름과 자동 계산 값이 한 항목으로 보인다. */
function expectEnd(dlg: HTMLElement, date: string) {
  const label = within(dlg).getByText('종료일')
  expect(label).toBeVisible()
  expect(label.parentElement).toHaveTextContent(date)
}

/** 첫 쪽에 보이고 Deal 코드가 유일한 계약. */
const first = (status: LicenseContract['status']) => {
  const shown = contracts.slice(0, 50)
  const found = shown.find((c) => c.status === status && shown.filter((x) => x.dealName === c.dealName).length === 1)
  if (!found) throw new Error(`첫 쪽에 ${status} 계약이 없다`)
  return found
}
const rowOf = (code: string) => rows().find((r) => within(r).getAllByRole('cell')[0]?.textContent === code)!

async function openEdit(c: LicenseContract, role: 'admin' | 'sales' | 'user' = 'sales') {
  const view = await renderAt('/contracts', { role })
  await screen.findByRole('table', { name: '계약 목록' }, LOAD)
  await view.user.click(within(rowOf(c.dealName)).getAllByRole('cell')[1]!)
  return { ...view, dlg: await screen.findByRole('dialog', { name: /^계약 수정 - / }) }
}
const statusGroup = (dlg: HTMLElement) => within(dlg).getByRole('group', { name: '상태' })
const startInput = (dlg: HTMLElement) => within(dlg).getByLabelText('라이선스 시작일')
const amountInput = (dlg: HTMLElement) => within(dlg).getByLabelText('기간')
const unitSelect = (dlg: HTMLElement) => within(dlg).getByLabelText('기간 단위')

describe('상태 묶음과 라이선스 칸 (C3)', () => {
  it.each([
    ['not_issued', '라이센스 발급'],
    ['issued_new', '라이센스 갱신'],
    ['issued_renewal', '라이센스 갱신'],
  ] as const)('shows the %s badge and its license button inside the 상태 group', async (status, button) => {
    const { dlg } = await openEdit(first(status))

    expect(within(statusGroup(dlg)).getByText(STATUS_LABELS[status])).toBeVisible()
    expect(within(statusGroup(dlg)).getByRole('button', { name: button })).toBeVisible()
  })

  it('shows no license or end button for an ended contract and keeps the license fields disabled', async () => {
    const c = first('ended')
    const { dlg } = await openEdit(c)

    expect(within(statusGroup(dlg)).getByText(STATUS_LABELS.ended)).toBeVisible()
    expect(within(statusGroup(dlg)).queryByRole('button')).not.toBeInTheDocument()
    expect(startInput(dlg)).toBeDisabled()
    expect(amountInput(dlg)).toBeDisabled()
    expect(unitSelect(dlg)).toBeDisabled()
    expect(startInput(dlg)).toHaveValue(dotted(c.licenseStart!))
  })

  it('has no 구분 field in the dialog', async () => {
    const { dlg } = await openEdit(first('issued_new'))

    expect(within(dlg).queryByRole('combobox', { name: '구분' })).not.toBeInTheDocument()
  })

  it.each(['issued_new', 'issued_renewal'] as const)('shows the current term of an %s contract in disabled fields', async (status) => {
    const c = first(status)
    const { dlg } = await openEdit(c)

    expect(startInput(dlg)).toBeDisabled()
    expect(amountInput(dlg)).toBeDisabled()
    expect(unitSelect(dlg)).toBeDisabled()
    expect(startInput(dlg)).toHaveValue(dotted(c.licenseStart!))
    expect(amountInput(dlg)).toHaveValue(c.term!.amount)
    expect(unitSelect(dlg)).toHaveDisplayValue(c.term!.unit === 'year' ? '년' : '개월')
    expectEnd(dlg, c.licenseEnd!)
  })

  it('shows empty disabled fields with the 1 year default for a not-issued contract', async () => {
    const { dlg } = await openEdit(first('not_issued'))

    expect(startInput(dlg)).toBeDisabled()
    expect(startInput(dlg)).toHaveValue('')
    expect(amountInput(dlg)).toBeDisabled()
    expect(amountInput(dlg)).toHaveValue(1)
    expect(unitSelect(dlg)).toBeDisabled()
    expect(unitSelect(dlg)).toHaveDisplayValue('년')
  })
})

describe('라이센스 발급 (C4, C6, AC12)', () => {
  const target = () => first('not_issued')

  async function startIssue() {
    const view = await openEdit(target())
    await view.user.click(within(statusGroup(view.dlg)).getByRole('button', { name: '라이센스 발급' }))
    return view
  }

  it('opens no extra dialog, enables the fields, focuses the start date and shows the guide', async () => {
    const { dlg } = await startIssue()

    expect(screen.getAllByRole('dialog')).toHaveLength(1)
    expect(startInput(dlg)).toBeEnabled()
    expect(amountInput(dlg)).toBeEnabled()
    expect(unitSelect(dlg)).toBeEnabled()
    expect(startInput(dlg)).toHaveFocus()
    expect(startInput(dlg)).toHaveValue(TODAY_TEXT)
    expect(amountInput(dlg)).toHaveValue(1)
    expect(unitSelect(dlg)).toHaveDisplayValue('년')
    expectEnd(dlg, '2028-03-14')
    expect(within(statusGroup(dlg)).queryByRole('button', { name: '라이센스 발급' })).not.toBeInTheDocument()
    expect(within(dlg).getByText('저장하면 발급(신규)됩니다')).toBeVisible()
  })

  it('sends the issue request with the contract fields and the period and shows the server-computed row', async () => {
    const issue = vi.spyOn(gateway.licenseContracts, 'issue')
    const { user, dlg } = await startIssue()

    await user.clear(startInput(dlg))
    await user.type(startInput(dlg), '20270101')
    expectEnd(dlg, '2027-12-31')
    await user.clear(within(dlg).getByLabelText('Note'))
    await user.type(within(dlg).getByLabelText('Note'), '발급과 함께 수정')
    await user.click(within(dlg).getByRole('button', { name: '저장' }))

    expect(await screen.findByText('라이센스를 발급했습니다.')).toBeVisible()
    expect(issue).toHaveBeenCalledWith(target().id, { techOwner: target().techOwner, inspection: target().inspection, note: '발급과 함께 수정', start: '2027-01-01', term: { amount: 1, unit: 'year' } })
    await waitFor(() => expect(screen.queryByRole('dialog', { name: /^계약 수정 - / })).not.toBeInTheDocument())
    const cells = within(rowOf(target().dealName)).getAllByRole('cell')
    expect(cells[5]).toHaveTextContent('2027-01-01')
    expect(cells[6]).toHaveTextContent('2027-12-31')
    expect(cells[7]?.textContent).toBe('발급(신규)')
    expect(cells[11]).toHaveTextContent('발급과 함께 수정')
  })

  it('computes 2026-06-30 for 2026-01-01 + 6 months', async () => {
    const { user, dlg } = await startIssue()

    await user.clear(startInput(dlg))
    await user.type(startInput(dlg), '20260101')
    await user.selectOptions(unitSelect(dlg), '개월')
    await user.clear(amountInput(dlg))
    await user.type(amountInput(dlg), '6')
    expectEnd(dlg, '2026-06-30')
    await user.click(within(dlg).getByRole('button', { name: '저장' }))

    await screen.findByText('라이센스를 발급했습니다.')
    expect(within(rowOf(target().dealName)).getAllByRole('cell')[6]).toHaveTextContent('2026-06-30')
  })

  it('does not send the request and shows a message when the start date is cleared (C6)', async () => {
    const issue = vi.spyOn(gateway.licenseContracts, 'issue')
    const { user, dlg } = await startIssue()

    await user.clear(startInput(dlg))
    await user.click(within(dlg).getByRole('button', { name: '저장' }))

    expect(await within(dlg).findByText(/필수|입력하세요/)).toBeVisible()
    expect(issue).not.toHaveBeenCalled()
    expect(screen.getByRole('dialog', { name: /^계약 수정 - / })).toBeVisible()
    expect(within(rowOf(target().dealName)).getAllByRole('cell')[7]?.textContent).toBe('미발급')
  })

  it('does not send the request when the period is empty (C6)', async () => {
    const issue = vi.spyOn(gateway.licenseContracts, 'issue')
    const { user, dlg } = await startIssue()

    await user.clear(amountInput(dlg))
    await user.click(within(dlg).getByRole('button', { name: '저장' }))

    expect(await within(dlg).findByRole('alert')).toHaveTextContent(/기간.*(필수|입력하세요)/)
    expect(issue).not.toHaveBeenCalled()
  })

  it('shows the server message in the dialog and keeps it open when another contract of the deal is already issued (AC3, 409)', async () => {
    vi.spyOn(gateway.licenseContracts, 'issue').mockRejectedValue(
      new ApiError(409, { type: 'https://sales.neoine.test/problems/invalid-state', title: 'Conflict', status: 409, detail: '이 Deal에는 이미 발급 상태인 라이선스 계약이 있습니다.' }),
    )
    const { user, dlg } = await startIssue()

    await user.click(within(dlg).getByRole('button', { name: '저장' }))

    expect(await within(dlg).findByRole('alert')).toHaveTextContent('이 Deal에는 이미 발급 상태인 라이선스 계약이 있습니다.')
    expect(screen.getByRole('dialog', { name: /^계약 수정 - / })).toBeVisible()
    expect(screen.queryByText('라이센스를 발급했습니다.')).not.toBeInTheDocument()
  })

  it('discards the issue on 취소 and restores the button on reopening', async () => {
    const issue = vi.spyOn(gateway.licenseContracts, 'issue')
    const { user, dlg } = await startIssue()

    await user.click(within(dlg).getByRole('button', { name: '취소' }))

    await waitFor(() => expect(screen.queryByRole('dialog')).not.toBeInTheDocument())
    expect(issue).not.toHaveBeenCalled()
    expect(within(rowOf(target().dealName)).getAllByRole('cell')[7]?.textContent).toBe('미발급')
    await user.click(within(rowOf(target().dealName)).getAllByRole('cell')[1]!)
    const again = await screen.findByRole('dialog', { name: /^계약 수정 - / })
    expect(within(statusGroup(again)).getByRole('button', { name: '라이센스 발급' })).toBeVisible()
    expect(startInput(again)).toBeDisabled()
  })
})

describe('라이센스 갱신 (C5, AC13)', () => {
  it.each(['issued_new', 'issued_renewal'] as const)('defaults the start to the day after the end of an %s contract and focuses it', async (status) => {
    const c = first(status)
    const { user, dlg } = await openEdit(c)

    await user.click(within(statusGroup(dlg)).getByRole('button', { name: '라이센스 갱신' }))

    expect(screen.getAllByRole('dialog')).toHaveLength(1)
    expect(startInput(dlg)).toBeEnabled()
    expect(startInput(dlg)).toHaveFocus()
    expect(startInput(dlg)).toHaveValue(dotted(nextDay(c.licenseEnd!)))
    expect(amountInput(dlg)).toHaveValue(c.term!.amount)
    expect(unitSelect(dlg)).toHaveDisplayValue(c.term!.unit === 'year' ? '년' : '개월')
    expect(within(statusGroup(dlg)).queryByRole('button', { name: '라이센스 갱신' })).not.toBeInTheDocument()
    expect(within(dlg).getByText('저장하면 발급(갱신)됩니다')).toBeVisible()
  })

  it.each(['issued_new', 'issued_renewal'] as const)('renews an %s contract through the renew request: a new 발급(갱신) row and the previous one ended', async (status) => {
    const c = first(status)
    const renew = vi.spyOn(gateway.licenseContracts, 'renew')
    const { user, dlg } = await openEdit(c)
    await user.click(within(statusGroup(dlg)).getByRole('button', { name: '라이센스 갱신' }))

    await user.click(within(dlg).getByRole('button', { name: '저장' }))

    expect(await screen.findByText('라이센스를 갱신했습니다.')).toBeVisible()
    expect(renew).toHaveBeenCalledWith(c.id, expect.objectContaining({ start: nextDay(c.licenseEnd!), term: c.term }))
    await waitFor(() => {
      const mine = rows().filter((r) => within(r).getAllByRole('cell')[0]?.textContent === c.dealName)
      const texts = mine.map((r) => within(r).getAllByRole('cell')[7]?.textContent)
      expect(texts).toContain('발급(갱신)')
      expect(texts).toContain('종료')
    })
  })

  it('does not send a renewal whose start date was cleared', async () => {
    const c = first('issued_new')
    const renew = vi.spyOn(gateway.licenseContracts, 'renew')
    const { user, dlg } = await openEdit(c)
    await user.click(within(statusGroup(dlg)).getByRole('button', { name: '라이센스 갱신' }))

    await user.clear(startInput(dlg))
    await user.click(within(dlg).getByRole('button', { name: '저장' }))

    expect(await within(dlg).findByText(/필수|입력하세요/)).toBeVisible()
    expect(renew).not.toHaveBeenCalled()
  })

  it('saves with the update request and the plain notice when no license button was pressed', async () => {
    const c = first('issued_new')
    const issue = vi.spyOn(gateway.licenseContracts, 'issue')
    const renew = vi.spyOn(gateway.licenseContracts, 'renew')
    const { user, dlg } = await openEdit(c)

    await user.click(within(dlg).getByRole('button', { name: '저장' }))

    expect(await screen.findByText('계약을 수정했습니다.')).toBeVisible()
    expect(issue).not.toHaveBeenCalled()
    expect(renew).not.toHaveBeenCalled()
    const cells = within(rowOf(c.dealName)).getAllByRole('cell')
    expect(cells[5]).toHaveTextContent(c.licenseStart!)
    expect(cells[6]).toHaveTextContent(c.licenseEnd!)
  })
})
