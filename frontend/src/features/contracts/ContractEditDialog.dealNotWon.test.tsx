import { screen, within } from '@testing-library/react'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { gateway } from '../../gateway'
import { dealCodeOf } from '../../test/detailTestUtils'
import { defaultMock } from '../../test/fake/default'
import { USER_ID } from '../../test/fake/seed/ids'
import { renderAt } from '../../test/mockApp'
import { pinClock, unpinClock } from '../../test/partnerMeetings'

/**
 * Won이 아닌 Deal의 계약(AC31): 계약 응답의 dealIsWon이 false면 '라이센스 발급' 버튼이 비활성화되고 힌트가 보인다.
 * 계약 종료·삭제(admin)·저장은 그대로다. 시드 12번 Deal('바른제약 PAM')은 Won이고 미발급 계약 1건뿐이다.
 */
const LOAD = { timeout: 8000 }
const DEAL_NOT_WON = 'Won인 Deal의 계약만 발급하거나 갱신할 수 있습니다.'
const ISSUE = /라이.스 발급/

beforeEach(() => pinClock())
afterEach(() => {
  unpinClock()
  vi.restoreAllMocks()
})

async function openContractOfDeal12(leaveWon: boolean, role: 'admin' | 'sales' = 'sales') {
  const code = await dealCodeOf(12)
  const view = await renderAt('/contracts', { role }) // renderAt이 데이터를 시드로 되돌리므로 Won 이탈은 그 뒤에 한다
  if (leaveWon) {
    await defaultMock.signInAs(USER_ID.root)
    await gateway.deals.applyChange(code, {
      change: { field: 'forecastKey', value: 'commit' },
      resolution: { statusKey: 'technical_evaluation' },
      deleteLicenseContracts: false,
    })
    await defaultMock.signInAs(role === 'admin' ? USER_ID.root : USER_ID.kim)
  }
  await screen.findByRole('table', { name: '계약 목록' }, LOAD)
  const bar = within(screen.getByRole('search', { name: '계약 검색' }))
  await view.user.type(bar.getByRole('textbox', { name: '고객사명' }), '바른제약')
  await view.user.click(bar.getByRole('button', { name: '검색' }))
  const cell = await within(screen.getByRole('table', { name: '계약 목록' })).findByText(code, undefined, LOAD)
  await view.user.click(cell.closest('tr')!.querySelectorAll('td')[1]!)
  return { ...view, dlg: await screen.findByRole('dialog', { name: '계약 수정' }) }
}

describe('Won이 아닌 Deal의 계약 대화상자 (AC31)', () => {
  it('keeps the issue button enabled and shows no hint while the deal is Won', async () => {
    const { dlg } = await openContractOfDeal12(false)

    expect(within(dlg).getByRole('button', { name: ISSUE })).toBeEnabled()
    expect(within(dlg).queryByText(DEAL_NOT_WON)).not.toBeInTheDocument()
  })

  it('disables the issue button and shows the hint when the deal left Won', async () => {
    const { dlg } = await openContractOfDeal12(true)

    expect(within(dlg).getByRole('button', { name: ISSUE })).toBeDisabled()
    expect(within(dlg).getByText(DEAL_NOT_WON)).toBeVisible()
  })

  it('does not call the server when the disabled issue button is clicked', async () => {
    const issue = vi.spyOn(gateway.licenseContracts, 'issue')
    const { user, dlg } = await openContractOfDeal12(true)

    expect(within(dlg).getByRole('button', { name: ISSUE })).toBeDisabled()
    await user.click(within(dlg).getByRole('button', { name: ISSUE }))

    expect(issue).not.toHaveBeenCalled()
    expect(within(dlg).queryByRole('alert')).not.toBeInTheDocument()
  })

  it('still lets the user end the contract and save the fields', async () => {
    const { dlg } = await openContractOfDeal12(true)

    expect(within(dlg).getByRole('button', { name: '계약 종료' })).toBeEnabled()
    expect(within(dlg).getByRole('button', { name: '저장' })).toBeEnabled()
  })

  it('still shows 삭제 to an admin', async () => {
    const { dlg } = await openContractOfDeal12(true, 'admin')

    expect(within(dlg).getByRole('button', { name: '삭제' })).toBeEnabled()
  })
})
