import { fireEvent, screen, within } from '@testing-library/react'
import { describe, expect, it } from 'vitest'
import { renderAt } from '../../../test/mockApp'
import { rowOf } from './testHelpers'

const SEARCH = '/deals?q=대한제조 MFA'

describe('Inline Update 즉시 저장 (T-LIST-12~14)', () => {
  it('has no save or cancel button while editing', async () => {
    const { user } = await renderAt(SEARCH)
    const row = await rowOf(/대한제조 MFA 확대/)
    for (const label of ['Status', 'Forecast', '금액', 'Expected Close']) {
      await user.click(within(row).getByRole('button', { name: new RegExp(`${label} 편집`) }))
      expect(within(row).queryByRole('button', { name: '저장' })).not.toBeInTheDocument()
      expect(within(row).queryByRole('button', { name: '취소' })).not.toBeInTheDocument()
      await user.keyboard('{Escape}')
    }
  })

  it('saves a Forecast change as soon as it is picked and tells it in a status message', async () => {
    const { user } = await renderAt(SEARCH)
    const row = await rowOf(/대한제조 MFA 확대/)
    await user.click(within(row).getByRole('button', { name: /Forecast 편집/ }))
    await user.selectOptions(within(row).getByLabelText('Forecast 값'), 'Commit')
    expect(await within(row).findByRole('button', { name: /Forecast 편집/ })).toHaveTextContent('Commit')
    expect(within(row).queryByLabelText('Forecast 값')).not.toBeInTheDocument()
    expect(await screen.findByText(/대한제조 MFA 확대: Forecast.*'Commit'.*변경되었습니다/)).toBeVisible()
  })

  it('leaves the old value when a select loses focus without a change', async () => {
    const { user } = await renderAt(SEARCH)
    const row = await rowOf(/대한제조 MFA 확대/)
    await user.click(within(row).getByRole('button', { name: /Forecast 편집/ }))
    await user.tab()
    expect(within(row).queryByLabelText('Forecast 값')).not.toBeInTheDocument()
    expect(within(row).getByRole('button', { name: /Forecast 편집/ })).toHaveTextContent('Most Likely')
  })

  it('saves Status as soon as it is picked', async () => {
    const { user } = await renderAt(SEARCH)
    const row = await rowOf(/대한제조 MFA 확대/)
    await user.click(within(row).getByRole('button', { name: /Status 편집/ }))
    await user.selectOptions(within(row).getByLabelText('Status 값'), 'POC완료')
    expect(await within(row).findByRole('button', { name: /Status 편집/ })).toHaveTextContent('POC완료')
  })

  it('saves the amount with Enter and shows it in the short form', async () => {
    const { user } = await renderAt(SEARCH)
    const row = await rowOf(/대한제조 MFA 확대/)
    await user.click(within(row).getByRole('button', { name: /금액 편집/ }))
    const input = within(row).getByLabelText('금액 값')
    await user.clear(input)
    await user.type(input, '500000000{Enter}')
    expect(await within(row).findByRole('button', { name: /금액 편집/ })).toHaveTextContent('500M')
  })

  it('saves the amount when the input loses focus, not on every keystroke', async () => {
    const { user } = await renderAt(SEARCH)
    const row = await rowOf(/대한제조 MFA 확대/)
    await user.click(within(row).getByRole('button', { name: /금액 편집/ }))
    const input = within(row).getByLabelText('금액 값')
    await user.clear(input)
    await user.type(input, '700000000')
    expect(within(row).getByLabelText('금액 값')).toBeVisible()
    expect(screen.queryByText(/금액.*변경되었습니다/)).not.toBeInTheDocument()
    await user.tab()
    expect(await within(row).findByRole('button', { name: /금액 편집/ })).toHaveTextContent('700M')
  })

  it('discards the typed amount with Esc', async () => {
    const { user } = await renderAt(SEARCH)
    const row = await rowOf(/대한제조 MFA 확대/)
    const before = within(row).getByRole('button', { name: /금액 편집/ }).textContent
    await user.click(within(row).getByRole('button', { name: /금액 편집/ }))
    const input = within(row).getByLabelText('금액 값')
    await user.clear(input)
    await user.type(input, '900000000{Escape}')
    expect(within(row).queryByLabelText('금액 값')).not.toBeInTheDocument()
    expect(within(row).getByRole('button', { name: /금액 편집/ })).toHaveTextContent(before ?? '')
    expect(screen.queryByText(/금액.*변경되었습니다/)).not.toBeInTheDocument()
  })

  it('rejects an invalid amount, keeps editing and does not save', async () => {
    const { user } = await renderAt(SEARCH)
    const row = await rowOf(/대한제조 MFA 확대/)
    await user.click(within(row).getByRole('button', { name: /금액 편집/ }))
    const input = within(row).getByLabelText('금액 값')
    await user.clear(input)
    await user.type(input, '0{Enter}')
    expect(await within(row).findByRole('alert')).toHaveTextContent('매출금액은 1원 이상의 정수로 입력하세요.')
    expect(within(row).getByLabelText('금액 값')).toBeVisible()
    expect(screen.queryByText(/금액.*변경되었습니다/)).not.toBeInTheDocument()
  })

  it('saves Expected Close as soon as a date is picked', async () => {
    const { user } = await renderAt(SEARCH)
    const row = await rowOf(/대한제조 MFA 확대/)
    await user.click(within(row).getByRole('button', { name: /Expected Close 편집/ }))
    fireEvent.change(within(row).getByLabelText('Expected Close 값'), { target: { value: '2027-02-03' } })
    expect(await within(row).findByRole('button', { name: /Expected Close 편집/ })).toHaveTextContent('2027-02-03')
  })

  it('rejects an empty Expected Close and keeps editing', async () => {
    const { user } = await renderAt(SEARCH)
    const row = await rowOf(/대한제조 MFA 확대/)
    await user.click(within(row).getByRole('button', { name: /Expected Close 편집/ }))
    fireEvent.change(within(row).getByLabelText('Expected Close 값'), { target: { value: '' } })
    expect(await within(row).findByRole('alert')).toHaveTextContent('Expected Close를 입력하세요.')
    expect(within(row).getByLabelText('Expected Close 값')).toBeVisible()
  })

  it('offers exactly four editable columns and none for Vendor, owner or the deal name', async () => {
    await renderAt(SEARCH)
    const row = await rowOf(/대한제조 MFA 확대/)
    const labels = within(row)
      .getAllByRole('button', { name: /편집/ })
      .map((b) => b.getAttribute('aria-label') ?? '')
    expect(labels).toHaveLength(4)
  })

  it('gives a user role no edit buttons', async () => {
    await renderAt(SEARCH, { role: 'user' })
    const row = await rowOf(/대한제조 MFA 확대/)
    expect(within(row).queryByRole('button', { name: /편집/ })).not.toBeInTheDocument()
  })
})

describe('Status⇄Forecast 동기화 (T-SYNC-UI-01~06, 목록)', () => {
  it('asks for the actual revenue before closing a deal as 계약완료 and tells the co-changed value', async () => {
    const { user } = await renderAt('/deals?q=한빛은행 ITDR')
    const row = await rowOf(/한빛은행 ITDR 도입/)
    await user.click(within(row).getByRole('button', { name: /Status 편집/ }))
    await user.selectOptions(within(row).getByLabelText('Status 값'), '계약완료')
    const dialog = await screen.findByRole('dialog', { name: '매출 확정' })
    const amount = within(dialog).getByLabelText('매출금액(KRW, 실제 값)')
    await user.clear(amount)
    expect(within(dialog).getByRole('button', { name: '확정' })).toBeDisabled()
    await user.type(amount, '1800000000')
    expect(within(dialog).getByRole('button', { name: '확정' })).toBeEnabled()
    await user.click(within(dialog).getByRole('button', { name: '확정' }))
    expect(await within(row).findByRole('button', { name: /Forecast 편집/ })).toHaveTextContent('Won')
    expect(within(row).getByRole('button', { name: /Status 편집/ })).toHaveTextContent('계약완료')
    expect(within(row).getByRole('button', { name: /금액 편집/ })).toHaveTextContent('1.8B')
    expect(await screen.findByText(/함께 변경되었습니다/)).toBeVisible()
  })

  it('leaves everything unchanged when the revenue dialog is cancelled', async () => {
    const { user } = await renderAt('/deals?q=한빛은행 ITDR')
    const row = await rowOf(/한빛은행 ITDR 도입/)
    await user.click(within(row).getByRole('button', { name: /Forecast 편집/ }))
    await user.selectOptions(within(row).getByLabelText('Forecast 값'), 'Won')
    const dialog = await screen.findByRole('dialog', { name: '매출 확정' })
    await user.click(within(dialog).getByRole('button', { name: '취소' }))
    expect(screen.queryByRole('dialog')).not.toBeInTheDocument()
    expect(within(row).getByRole('button', { name: /Forecast 편집/ })).toHaveTextContent('Commit')
    expect(within(row).getByRole('button', { name: /Status 편집/ })).toHaveTextContent('가격협상')
  })

  it('makes the user pick the new Status when a Won deal is reopened', async () => {
    const { user } = await renderAt('/deals?q=청명대학교 SSO')
    const row = await rowOf(/청명대학교 SSO\/MFA/)
    await user.click(within(row).getByRole('button', { name: /Forecast 편집/ }))
    await user.selectOptions(within(row).getByLabelText('Forecast 값'), 'Commit')
    const dialog = await screen.findByRole('dialog', { name: '함께 바꿀 값 선택' })
    expect(within(dialog).getByRole('button', { name: '확인' })).toBeDisabled()
    expect(within(dialog).queryByRole('radio', { name: '계약완료' })).not.toBeInTheDocument()
    await user.click(within(dialog).getByRole('radio', { name: '기술평가' }))
    await user.click(within(dialog).getByRole('button', { name: '확인' }))
    expect(await within(row).findByRole('button', { name: /Status 편집/ })).toHaveTextContent('기술평가')
    expect(within(row).getByRole('button', { name: /Forecast 편집/ })).toHaveTextContent('Commit')
  })

  it('makes the user pick the Forecast when 계약완료 is moved back', async () => {
    const { user } = await renderAt('/deals?q=청명대학교 SSO')
    const row = await rowOf(/청명대학교 SSO\/MFA/)
    await user.click(within(row).getByRole('button', { name: /Status 편집/ }))
    await user.selectOptions(within(row).getByLabelText('Status 값'), '가격협상')
    const dialog = await screen.findByRole('dialog', { name: '함께 바꿀 값 선택' })
    await user.click(within(dialog).getByRole('radio', { name: 'Best' }))
    await user.click(within(dialog).getByRole('button', { name: '확인' }))
    expect(await within(row).findByRole('button', { name: /Forecast 편집/ })).toHaveTextContent('Best')
    expect(within(row).getByRole('button', { name: /Status 편집/ })).toHaveTextContent('가격협상')
  })

  it('keeps the old values when the choice dialog is cancelled', async () => {
    const { user } = await renderAt('/deals?q=청명대학교 SSO')
    const row = await rowOf(/청명대학교 SSO\/MFA/)
    await user.click(within(row).getByRole('button', { name: /Forecast 편집/ }))
    await user.selectOptions(within(row).getByLabelText('Forecast 값'), 'Commit')
    const dialog = await screen.findByRole('dialog', { name: '함께 바꿀 값 선택' })
    await user.click(within(dialog).getByRole('button', { name: '취소' }))
    expect(within(row).getByRole('button', { name: /Forecast 편집/ })).toHaveTextContent('Won')
    expect(within(row).getByRole('button', { name: /Status 편집/ })).toHaveTextContent('계약완료')
  })
})
