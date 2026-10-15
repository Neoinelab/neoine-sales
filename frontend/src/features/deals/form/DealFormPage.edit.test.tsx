import { fireEvent, screen, waitFor, within } from '@testing-library/react'
import { describe, expect, it } from 'vitest'
import { renderAt } from '../../../test/mockApp'
import { DETAIL_URL, openEdit, openList, pickPerson, save } from './testHelpers'

describe('Deal 수정 (T-FORM-06)', () => {
  it('loads every value of the deal into the form', async () => {
    await openEdit('누리통신 MFA')
    expect(screen.getByLabelText('Deal Name')).toHaveValue('누리통신 MFA')
    await waitFor(() => expect(screen.getByLabelText('Owner')).toHaveDisplayValue('이영업'))
    expect(screen.getByLabelText('Vendor')).toHaveValue('Silverfort')
    expect(screen.getByLabelText('고객 회사명')).toHaveValue('누리통신')
    expect(screen.getByLabelText('고객 담당자명')).toHaveValue('배성훈')
    expect(screen.getByLabelText('고객 직급')).toHaveValue('과장')
    expect(screen.getByLabelText('파트너 회사명')).toHaveValue('에이원시스템')
    expect(screen.getByLabelText('파트너 담당자명')).toHaveValue('표성호')
    await waitFor(() => expect(screen.getByLabelText('Status')).toHaveDisplayValue('POC준비'))
    expect(screen.getByLabelText('Forecast')).toHaveDisplayValue('Best')
    expect(screen.getByLabelText('매출금액')).toHaveValue('330000000')
  })

  it('saves edits and goes to the detail page', async () => {
    const { user, location, code } = await openEdit('대한제조 NGFW')
    const name = screen.getByLabelText('Deal Name')
    await user.clear(name)
    await user.type(name, '대한제조 NGFW 확장')
    await save(user)
    await waitFor(() => expect(location()).toBe(`/deals/${code}`))
  })

  it('shows a replacement notice for another partner and saves the replacement', async () => {
    const { user, location } = await openEdit('누리통신 MFA')
    expect(screen.queryByText(/이력으로 남고 비활성이 됩니다/)).not.toBeInTheDocument()
    await pickPerson(user, '파트너', '코어테크', /민지훈/)
    expect(
      await screen.findByText('기존 활성 파트너(에이원시스템 표성호)는 이력으로 남고 비활성이 됩니다.'),
    ).toBeVisible()
    await save(user)
    await waitFor(() => expect(location()).toMatch(DETAIL_URL))

    const row = await openList(user, '누리통신 MFA')
    await user.click(within(row).getByRole('button', { name: /빠른 보기/ }))
    const view = await screen.findByRole('region', { name: /빠른 보기/ })
    expect(within(view).getByText(/민지훈/)).toBeVisible()
    expect(within(view).queryByText(/표성호/)).not.toBeInTheDocument()
  })

  it('removes the active partner with the remove button', async () => {
    const { user, location } = await openEdit('누리통신 MFA')
    await user.click(screen.getByRole('button', { name: '파트너 제거' }))
    expect(screen.getByLabelText('파트너 회사명')).toHaveValue('')
    expect(
      await screen.findByText('저장하면 기존 활성 파트너(에이원시스템 표성호)가 제거되고 이력으로 남습니다.'),
    ).toBeVisible()
    await save(user)
    await waitFor(() => expect(location()).toMatch(DETAIL_URL))
    const row = await openList(user, '누리통신 MFA')
    expect(within(row).getByText('—')).toBeVisible()
  })

  it('keeps a resigned owner visible but refuses to save until another owner is picked', async () => {
    const { user, location } = await openEdit('한빛은행 PAM')
    await waitFor(() => expect(screen.getByLabelText('Owner')).toHaveDisplayValue('강퇴사(퇴사)'))
    await save(user)
    expect(
      await screen.findByText('퇴사한 사용자는 Owner로 지정할 수 없습니다. 다른 담당자를 선택하세요.'),
    ).toBeVisible()
    expect(location()).toMatch(/\/edit$/)
    await user.selectOptions(screen.getByLabelText('Owner'), '김영업')
    await save(user)
    await waitFor(() => expect(location()).toMatch(DETAIL_URL))
  })

  it('lets a closed deal be edited as well', async () => {
    const { user, location, code } = await openEdit('청명대학교 SSO/MFA')
    await waitFor(() => expect(screen.getByLabelText('Forecast')).toHaveDisplayValue('Won'))
    await user.type(screen.getByLabelText('구매절차'), ' 추가 메모')
    await save(user)
    await waitFor(() => expect(location()).toBe(`/deals/${code}`))
  })

  it('shows the server message and stays on the form when saving fails', async () => {
    const { user, location } = await openEdit('누리통신 MFA')
    const email = screen.getByLabelText('고객 이메일')
    await user.clear(email)
    await user.type(email, 'bae1@nuri.test')
    await save(user)
    expect(await screen.findByText('이미 등록된 연락처입니다.')).toBeVisible()
    expect(location()).toMatch(/\/edit$/)
    expect(screen.getByRole('button', { name: '저장' })).toBeEnabled()
  })

  it('shows the not-found message and a way back for an unknown code', async () => {
    await renderAt('/deals/20000101-ZZZZ/edit')
    expect(await screen.findByRole('alert')).toHaveTextContent('Deal을 찾을 수 없습니다.')
    expect(screen.getByRole('link', { name: '목록으로' })).toHaveAttribute('href', '/deals')
  })

  it('goes back to the detail page when cancelled', async () => {
    const { user, location, code } = await openEdit('대한제조 NGFW')
    await user.click(screen.getByRole('button', { name: '취소' }))
    expect(location()).toBe(`/deals/${code}`)
  })
})

describe('Status⇄Forecast 동기화 (T-SYNC-UI, 폼)', () => {
  it('asks for revenue on 계약완료, then sets Forecast to Won and tells it is not saved yet', async () => {
    const { user } = await openEdit('대한제조 MFA 확대')
    await waitFor(() => expect(screen.getByLabelText('Status')).toHaveDisplayValue('기술평가'))
    await user.selectOptions(screen.getByLabelText('Status'), '계약완료')
    const dialog = await screen.findByRole('dialog', { name: '매출 확정' })
    await user.click(within(dialog).getByRole('button', { name: '확정' }))
    expect(screen.getByLabelText('Status')).toHaveDisplayValue('계약완료')
    expect(screen.getByLabelText('Forecast')).toHaveDisplayValue('Won')
    expect(await screen.findByText(/함께 변경됩니다\. 저장하면 반영됩니다\./)).toBeVisible()
  })

  it('puts the confirmed revenue into the form fields', async () => {
    const { user } = await openEdit('대한제조 MFA 확대')
    await waitFor(() => expect(screen.getByLabelText('Status')).toHaveDisplayValue('기술평가'))
    await user.selectOptions(screen.getByLabelText('Forecast'), 'Won')
    const dialog = await screen.findByRole('dialog', { name: '매출 확정' })
    const amount = within(dialog).getByLabelText('매출금액(KRW, 실제 값)')
    await user.clear(amount)
    await user.type(amount, '400000000')
    fireEvent.change(within(dialog).getByLabelText('매출일(실제 값)'), { target: { value: '2026-12-01' } })
    await user.click(within(dialog).getByRole('button', { name: '확정' }))
    expect(screen.getByLabelText('매출금액')).toHaveValue('400000000')
    expect(screen.getByLabelText('Expected Close')).toHaveValue('2026-12-01')
    expect(screen.getByLabelText('Status')).toHaveDisplayValue('계약완료')
  })

  it('keeps the old Status when the revenue dialog is cancelled', async () => {
    const { user } = await openEdit('대한제조 MFA 확대')
    await waitFor(() => expect(screen.getByLabelText('Status')).toHaveDisplayValue('기술평가'))
    await user.selectOptions(screen.getByLabelText('Status'), '계약완료')
    const dialog = await screen.findByRole('dialog', { name: '매출 확정' })
    await user.click(within(dialog).getByRole('button', { name: '취소' }))
    expect(screen.getByLabelText('Status')).toHaveDisplayValue('기술평가')
    expect(screen.getByLabelText('Forecast')).toHaveDisplayValue('Most Likely')
    expect(screen.queryByText(/저장하면 반영됩니다/)).not.toBeInTheDocument()
  })

  it('makes the user choose a Status when a Won deal gets another Forecast', async () => {
    const { user } = await openEdit('청명대학교 SSO/MFA')
    await waitFor(() => expect(screen.getByLabelText('Forecast')).toHaveDisplayValue('Won'))
    await user.selectOptions(screen.getByLabelText('Forecast'), 'Commit')
    const dialog = await screen.findByRole('dialog', { name: '함께 바꿀 값 선택' })
    expect(within(dialog).getByRole('button', { name: '확인' })).toBeDisabled()
    await user.click(within(dialog).getByRole('radio', { name: '기술평가' }))
    await user.click(within(dialog).getByRole('button', { name: '확인' }))
    expect(screen.getByLabelText('Status')).toHaveDisplayValue('기술평가')
    expect(screen.getByLabelText('Forecast')).toHaveDisplayValue('Commit')
  })

  it('saves the synchronized values and the list shows them', async () => {
    const { user, location } = await openEdit('대한제조 MFA 확대')
    await waitFor(() => expect(screen.getByLabelText('Status')).toHaveDisplayValue('기술평가'))
    await user.selectOptions(screen.getByLabelText('Status'), '계약완료')
    await user.click(within(await screen.findByRole('dialog', { name: '매출 확정' })).getByRole('button', { name: '확정' }))
    await save(user)
    await waitFor(() => expect(location()).toMatch(DETAIL_URL))
    const row = await openList(user, '대한제조 MFA')
    expect(within(row).getByRole('button', { name: /Forecast 편집/ })).toHaveTextContent('Won')
    expect(within(row).getByRole('button', { name: /Status 편집/ })).toHaveTextContent('계약완료')
  })

  it('asks for revenue on a new deal chosen as Won', async () => {
    const { user } = await renderAt('/deals/new')
    await screen.findByRole('heading', { name: 'Deal 등록' })
    const forecast = screen.getByLabelText('Forecast')
    await within(forecast).findByRole('option', { name: 'Won' })
    await user.selectOptions(forecast, 'Won')
    const dialog = await screen.findByRole('dialog', { name: '매출 확정' })
    expect(within(dialog).getByRole('button', { name: '확정' })).toBeDisabled()
  })
})
