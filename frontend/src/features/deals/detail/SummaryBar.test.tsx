import { screen, waitFor, within } from '@testing-library/react'
import type { UserEvent } from '@testing-library/user-event'
import { describe, expect, it } from 'vitest'
import { renderAt } from '../../../test/mockApp'
import { detailPath } from './detailTestUtils'

async function openBar(no: number, title: string, role: 'sales' | 'admin' = 'sales') {
  const view = await renderAt(await detailPath(no), { role })
  await screen.findByRole('heading', { level: 1, name: title })
  return { ...view, bar: screen.getByRole('region', { name: '현재 값' }) }
}

/** Status/Forecast 값을 클릭 → 선택(고르는 순간 반영). 동기화 팝업은 호출한 테스트가 이어서 다룬다. */
async function pick(user: UserEvent, bar: HTMLElement, field: 'Status' | 'Forecast', option: string) {
  await user.click(within(bar).getByRole('button', { name: `${field} 수정` }))
  await user.selectOptions(within(bar).getByLabelText(field), option)
}

const shown = (bar: HTMLElement, field: 'Status' | 'Forecast') => within(bar).getByRole('button', { name: `${field} 수정` })

describe('상세 현재값 바 인라인 변경 (T-SYNC-UI 상세)', () => {
  it('changes the forecast right away when no sync is needed and tells the user', async () => {
    const { user, bar } = await openBar(2, '대한제조 MFA 확대')
    await pick(user, bar, 'Forecast', 'Commit')
    await waitFor(() => expect(shown(bar, 'Forecast')).toHaveTextContent('Commit'))
    expect(await screen.findByText("Forecast가 'Commit'(으)로 변경되었습니다.")).toBeVisible()
  })

  it('asks for the revenue before moving to 계약완료 and then changes forecast to Won too', async () => {
    const { user, bar } = await openBar(1, '한빛은행 ITDR 도입')
    await pick(user, bar, 'Status', '계약완료')
    const dialog = await screen.findByRole('dialog', { name: '매출 확정' })
    const confirm = within(dialog).getByRole('button', { name: '확정' })
    await user.clear(within(dialog).getByLabelText('매출금액(KRW, 실제 값)'))
    expect(confirm).toBeDisabled()
    await user.type(within(dialog).getByLabelText('매출금액(KRW, 실제 값)'), '1800000000')
    await user.clear(within(dialog).getByLabelText('매출일(실제 값)'))
    await user.type(within(dialog).getByLabelText('매출일(실제 값)'), '2026-11-30')
    await user.click(confirm)
    await waitFor(() => expect(shown(bar, 'Status')).toHaveTextContent('계약완료'))
    expect(shown(bar, 'Forecast')).toHaveTextContent('Won')
    expect(await screen.findByText(/함께 변경되었습니다/)).toBeVisible()
    expect(within(bar).getByTitle('1,800,000,000원')).toBeVisible()
  })

  it('keeps the old values when the revenue dialog is cancelled', async () => {
    const { user, bar } = await openBar(1, '한빛은행 ITDR 도입')
    await pick(user, bar, 'Status', '계약완료')
    const dialog = await screen.findByRole('dialog', { name: '매출 확정' })
    await user.click(within(dialog).getByRole('button', { name: '취소' }))
    await waitFor(() => expect(screen.queryByRole('dialog')).not.toBeInTheDocument())
    expect(shown(bar, 'Status')).toHaveTextContent('가격협상')
    expect(shown(bar, 'Forecast')).toHaveTextContent('Commit')
  })

  it('asks which status to use when a won deal leaves Won, with no default and 계약완료 excluded', async () => {
    const { user, bar } = await openBar(11, '청명대학교 SSO/MFA')
    await pick(user, bar, 'Forecast', 'Commit')
    const dialog = await screen.findByRole('dialog', { name: '함께 바꿀 값 선택' })
    const confirm = within(dialog).getByRole('button', { name: '확인' })
    expect(confirm).toBeDisabled()
    expect(within(dialog).queryByRole('radio', { name: '계약완료' })).not.toBeInTheDocument()
    await user.click(within(dialog).getByRole('radio', { name: '기술평가' }))
    await user.click(confirm)
    await waitFor(() => expect(shown(bar, 'Forecast')).toHaveTextContent('Commit'))
    expect(shown(bar, 'Status')).toHaveTextContent('기술평가')
  })

  it('asks which forecast to use when a contract-completed deal goes back to an earlier status', async () => {
    const { user, bar } = await openBar(11, '청명대학교 SSO/MFA')
    await pick(user, bar, 'Status', '기술평가')
    const dialog = await screen.findByRole('dialog', { name: '함께 바꿀 값 선택' })
    expect(within(dialog).getByRole('button', { name: '확인' })).toBeDisabled()
    await user.click(within(dialog).getByRole('radio', { name: 'Best' }))
    await user.click(within(dialog).getByRole('button', { name: '확인' }))
    await waitFor(() => expect(shown(bar, 'Status')).toHaveTextContent('기술평가'))
    expect(shown(bar, 'Forecast')).toHaveTextContent('Best')
  })

  it('asks for a status when reviving a lost deal, defaulting to the current status', async () => {
    const { user, bar } = await openBar(16, '새론병원 SSO')
    await pick(user, bar, 'Forecast', 'Best')
    const dialog = await screen.findByRole('dialog', { name: '함께 바꿀 값 선택' })
    expect(within(dialog).getByRole('radio', { name: '가격협상' })).toBeChecked()
    await user.click(within(dialog).getByRole('button', { name: '확인' }))
    await waitFor(() => expect(shown(bar, 'Forecast')).toHaveTextContent('Best'))
  })

  it('closes the status editor with Escape or by leaving it, without changing anything or asking', async () => {
    const { user, bar } = await openBar(1, '한빛은행 ITDR 도입')
    await user.click(within(bar).getByRole('button', { name: 'Status 수정' }))
    await user.keyboard('{Escape}')
    expect(within(bar).queryByLabelText('Status')).not.toBeInTheDocument()
    await user.click(within(bar).getByRole('button', { name: 'Status 수정' }))
    await user.tab()
    expect(within(bar).queryByLabelText('Status')).not.toBeInTheDocument()
    expect(screen.queryByRole('dialog')).not.toBeInTheDocument()
    expect(shown(bar, 'Status')).toHaveTextContent('가격협상')
  })
})

describe('금액·Expected Close 인라인 편집', () => {
  it('saves a new amount and shows it', async () => {
    const { user, bar } = await openBar(2, '대한제조 MFA 확대')
    await user.click(within(bar).getByRole('button', { name: '금액 수정' }))
    const input = within(bar).getByLabelText('금액(KRW)')
    await user.clear(input)
    await user.type(input, '500000000')
    await user.tab()
    await waitFor(() => expect(within(bar).getByTitle('500,000,000원')).toBeVisible())
  })

  it('rejects an empty amount with the server message and keeps the editor open', async () => {
    const { user, bar } = await openBar(2, '대한제조 MFA 확대')
    await user.click(within(bar).getByRole('button', { name: '금액 수정' }))
    await user.clear(within(bar).getByLabelText('금액(KRW)'))
    await user.keyboard('{Enter}')
    expect(await within(bar).findByRole('alert')).toHaveTextContent('매출금액은 1원 이상의 정수로 입력하세요.')
    expect(within(bar).getByLabelText('금액(KRW)')).toBeVisible()
  })

  it('cancels the amount edit with Escape without saving', async () => {
    const { user, bar } = await openBar(2, '대한제조 MFA 확대')
    await user.click(within(bar).getByRole('button', { name: '금액 수정' }))
    await user.type(within(bar).getByLabelText('금액(KRW)'), '9{Escape}')
    expect(within(bar).queryByLabelText('금액(KRW)')).not.toBeInTheDocument()
    expect(within(bar).getByTitle('420,000,000원')).toBeVisible()
  })

  it('saves the amount with Enter from the keyboard', async () => {
    const { user, bar } = await openBar(2, '대한제조 MFA 확대')
    await user.click(within(bar).getByRole('button', { name: '금액 수정' }))
    const input = within(bar).getByLabelText('금액(KRW)')
    expect(input).toHaveFocus()
    await user.clear(input)
    await user.type(input, '777000000{Enter}')
    await waitFor(() => expect(within(bar).getByTitle('777,000,000원')).toBeVisible())
  })

  it('saves a new Expected Close', async () => {
    const { user, bar } = await openBar(2, '대한제조 MFA 확대')
    await user.click(within(bar).getByRole('button', { name: 'Expected Close 수정' }))
    const input = within(bar).getByLabelText('Expected Close')
    await user.clear(input)
    await user.type(input, '2027-03-31')
    await user.keyboard('{Enter}')
    await waitFor(() => expect(within(bar).getByText('2027-03-31')).toBeVisible())
  })

  it('records the change in the deal history', async () => {
    const { user, bar } = await openBar(2, '대한제조 MFA 확대')
    await pick(user, bar, 'Forecast', 'Commit')
    await waitFor(() => expect(shown(bar, 'Forecast')).toHaveTextContent('Commit'))
    await user.click(screen.getByRole('tab', { name: 'Deal History' }))
    const row = (await screen.findAllByRole('row')).find((r) => within(r).queryByRole('cell', { name: 'Forecast' }))
    expect(row).toBeDefined()
    expect(row).toHaveTextContent('Most Likely')
    expect(row).toHaveTextContent('Commit')
  })
})
