import { screen, within } from '@testing-library/react'
import { describe, expect, it } from 'vitest'
import { addColumn, chipButton, chipTexts, openDesigner, settingsOf, setupReportClock } from '../../../test/reportScreen'

setupReportClock()

const optionTexts = (select: HTMLElement): string[] => within(select).getAllByRole('option').map((o) => o.textContent ?? '')
const plain = (texts: string[]): string[] => texts.map((t) => t.replace(/\s*\(묶음\)$/, ''))

/** i번째 칩을 눌러(이미 선택돼 있으면 누르지 않고) 설정을 열고 그 패널을 돌려준다. */
async function open(user: Awaited<ReturnType<typeof openDesigner>>['user'], index: number, name: string): Promise<HTMLElement> {
  if (chipButton(index).getAttribute('aria-pressed') !== 'true') await user.click(chipButton(index))
  return settingsOf(name)
}

describe('집계 선택 (AC6)', () => {
  it('enables aggregates when a group exists and offers only count kinds for text', async () => {
    const { user } = await openDesigner()
    await addColumn(user, 'Vendor')
    await addColumn(user, '금액')
    await addColumn(user, 'Deal code')

    const before = await open(user, 1, '금액')
    expect(within(before).getByRole('combobox', { name: '집계' })).toBeDisabled()
    expect(within(before).getByText('(그룹핑이 있을 때)')).toBeVisible()

    await user.click(within(await open(user, 0, 'Vendor')).getByRole('checkbox', { name: '그룹핑' }))

    const amount = within(await open(user, 1, '금액')).getByRole('combobox', { name: '집계' })
    expect(amount).toBeEnabled()
    expect(amount).toHaveDisplayValue('합계')
    expect(optionTexts(amount)).toEqual(['합계', '평균', '최소', '최대'])

    const code = within(await open(user, 2, 'Deal code')).getByRole('combobox', { name: '집계' })
    expect(code).toBeEnabled()
    expect(code).toHaveDisplayValue('건수')
    expect(optionTexts(code)).toEqual(['건수', '고유 건수'])
    expect(within(code).queryByRole('option', { name: '' })).not.toBeInTheDocument()
    expect(screen.queryByText('집계 선택')).not.toBeInTheDocument()
  })

  it('counts a text column picked later while grouped and never shows an empty aggregate option', async () => {
    const { user } = await openDesigner()
    await addColumn(user, 'Vendor')
    await user.click(within(await open(user, 0, 'Vendor')).getByRole('checkbox', { name: '그룹핑' }))
    await addColumn(user, 'Deal 이름')

    const name = within(await open(user, 1, 'Deal 이름')).getByRole('combobox', { name: '집계' })

    expect(name).toBeEnabled()
    expect(name).toHaveDisplayValue('건수')
    expect(chipTexts()[1]).toContain('건수')
    expect(screen.queryByText('집계 선택')).not.toBeInTheDocument()
    for (const select of screen.getAllByRole('combobox', { name: '집계' })) {
      expect(within(select).queryByRole('option', { name: '' })).not.toBeInTheDocument()
    }
  })

  it('shows a dash in the disabled aggregate of a group column and keeps numbers on sum', async () => {
    const { user } = await openDesigner()
    await addColumn(user, 'Vendor')
    await addColumn(user, '금액')
    await user.click(within(await open(user, 0, 'Vendor')).getByRole('checkbox', { name: '그룹핑' }))

    const group = within(await open(user, 0, 'Vendor')).getByRole('combobox', { name: '집계' })

    expect(group).toBeDisabled()
    expect(group).toHaveDisplayValue('—')
    expect(within(await open(user, 1, '금액')).getByRole('combobox', { name: '집계' })).toHaveDisplayValue('합계')
  })

  it('lets the user pick another aggregate and clears it when the group is turned off', async () => {
    const { user } = await openDesigner()
    await addColumn(user, 'Vendor')
    await addColumn(user, '금액')
    await user.click(within(await open(user, 0, 'Vendor')).getByRole('checkbox', { name: '그룹핑' }))

    await user.selectOptions(within(await open(user, 1, '금액')).getByRole('combobox', { name: '집계' }), 'max')
    expect(chipTexts()[1]).toContain('최대')

    await user.click(within(await open(user, 0, 'Vendor')).getByRole('checkbox', { name: '그룹핑' }))

    expect(within(await open(user, 1, '금액')).getByRole('combobox', { name: '집계' })).toBeDisabled()
    expect(chipTexts()[1]).not.toContain('최대')
  })

  it('shows group and aggregate badges on chips', async () => {
    const { user } = await openDesigner()
    await addColumn(user, 'Vendor')
    await addColumn(user, '금액')
    await addColumn(user, 'Status 체류 일수')
    await user.click(within(await open(user, 0, 'Vendor')).getByRole('checkbox', { name: '그룹핑' }))

    const [vendor, amount, days] = chipTexts()

    expect(vendor).toContain('그룹')
    expect(amount).toContain('합계')
    expect(days).toContain('평균')
  })

  it('shows the name of a date format that is not the default as a badge and none for numbers (AC-8)', async () => {
    const { user } = await openDesigner()
    await addColumn(user, '금액')
    await addColumn(user, 'Expected Close')
    expect(chipTexts()[0]).not.toContain('천원')

    await user.selectOptions(within(await open(user, 1, 'Expected Close')).getByRole('combobox', { name: '포맷' }), 'quarter')

    expect(chipTexts()[1]).toContain('분기')
    for (const unit of ['천원', '백만원', '천 단위', '소수 1자리', '구성비']) expect(chipTexts()[0]).not.toContain(unit)
  })

  it('locks grouping and the aggregate of action count', async () => {
    const { user } = await openDesigner()
    await addColumn(user, 'Vendor')
    await addColumn(user, 'Action 건수')
    expect(chipTexts()[1]).toContain('그룹핑할 때만')

    await user.click(within(await open(user, 0, 'Vendor')).getByRole('checkbox', { name: '그룹핑' }))
    const panel = await open(user, 1, 'Action 건수')

    expect(within(panel).getByRole('checkbox', { name: '그룹핑' })).toBeDisabled()
    expect(within(panel).getByRole('combobox', { name: '집계' })).toBeDisabled()
    expect(within(panel).getByRole('combobox', { name: '집계' })).toHaveDisplayValue('건수')
    expect(chipTexts()[1]).not.toContain('그룹핑할 때만')
  })
})

describe('포맷·표시 이름 (AC6)', () => {
  it('offers only the formats of the field type', async () => {
    const { user } = await openDesigner()
    await addColumn(user, 'Deal code')
    await addColumn(user, 'Vendor')
    await addColumn(user, '금액')
    await addColumn(user, 'Expected Close')
    await addColumn(user, '등록일')

    const formats = async (index: number, name: string) =>
      optionTexts(within(await open(user, index, name)).getByRole('combobox', { name: '포맷' }))
    const hasFormat = async (index: number, name: string) =>
      within(await open(user, index, name)).queryByRole('combobox', { name: '포맷' }) !== null

    expect(await hasFormat(0, 'Deal code')).toBe(false)
    expect(await hasFormat(1, 'Vendor')).toBe(false)
    expect(await hasFormat(2, '금액')).toBe(false)
    expect(plain(await formats(3, 'Expected Close'))).toEqual(['연-월-일', '연도', '분기', '월', '요일', '상대 시각'])
    expect(plain(await formats(4, '등록일'))).toEqual(['연-월-일 시:분', '연-월-일', '연도', '분기', '월', '요일', '상대 시각'])
  })

  it('shows no format choice for text, code, user and number fields (AC-8)', async () => {
    const { user } = await openDesigner()
    await addColumn(user, 'Deal 이름')
    await addColumn(user, 'Status')
    await addColumn(user, '담당자')
    await addColumn(user, '금액')
    await addColumn(user, 'Users count')
    await addColumn(user, 'Status 체류 일수')

    for (const [index, name] of [[0, 'Deal 이름'], [1, 'Status'], [2, '담당자'], [3, '금액'], [4, 'Users count'], [5, 'Status 체류 일수']] as const) {
      expect(within(await open(user, index, name)).queryByRole('combobox', { name: '포맷' })).not.toBeInTheDocument()
    }
  })

  it('marks the formats that change the grouping with (묶음)', async () => {
    const { user } = await openDesigner()
    await addColumn(user, 'Expected Close')

    const options = optionTexts(within(await open(user, 0, 'Expected Close')).getByRole('combobox', { name: '포맷' }))

    expect(options.filter((t) => t.includes('(묶음)')).map((t) => t.replace(/\s*\(묶음\)$/, ''))).toEqual(['연-월-일', '연도', '분기', '월'])
  })

  it('offers the prefix option on every field with N locked until it is turned on', async () => {
    const { user } = await openDesigner()
    await addColumn(user, 'Deal 이름')
    await addColumn(user, '금액')
    await addColumn(user, 'Expected Close')

    for (const [index, name] of [[0, 'Deal 이름'], [1, '금액'], [2, 'Expected Close']] as const) {
      const panel = await open(user, index, name)
      expect(within(panel).getByRole('checkbox', { name: '앞 N자만 보기' })).not.toBeChecked()
      expect(within(panel).getByLabelText('앞 N자의 N')).toBeDisabled()
    }
  })

  it('turns the prefix option on with N 20, a chip badge, and off again', async () => {
    const { user } = await openDesigner()
    await addColumn(user, 'Deal 이름')
    const panel = await open(user, 0, 'Deal 이름')
    expect(chipTexts()[0]).not.toContain('앞 20자')

    await user.click(within(panel).getByRole('checkbox', { name: '앞 N자만 보기' }))
    const length = within(settingsOf('Deal 이름')).getByLabelText('앞 N자의 N')

    expect(length).toBeEnabled()
    expect(length).toHaveValue(20)
    expect(length).toHaveAttribute('min', '1')
    expect(length).toHaveAttribute('max', '200')
    expect(chipTexts()[0]).toContain('앞 20자')

    await user.click(within(settingsOf('Deal 이름')).getByRole('checkbox', { name: '앞 N자만 보기' }))

    expect(within(settingsOf('Deal 이름')).getByLabelText('앞 N자의 N')).toBeDisabled()
    expect(chipTexts()[0]).not.toContain('앞')
  })

  it('shows the typed N on the badge and keeps the option when the format changes', async () => {
    const { user } = await openDesigner()
    await addColumn(user, 'Expected Close')
    const panel = await open(user, 0, 'Expected Close')
    await user.click(within(panel).getByRole('checkbox', { name: '앞 N자만 보기' }))
    const length = within(settingsOf('Expected Close')).getByLabelText('앞 N자의 N')
    await user.clear(length)
    await user.type(length, '7')

    await user.selectOptions(within(settingsOf('Expected Close')).getByRole('combobox', { name: '포맷' }), 'weekday')

    expect(chipTexts()[0]).toContain('앞 7자')
    expect(within(settingsOf('Expected Close')).getByRole('checkbox', { name: '앞 N자만 보기' })).toBeChecked()
  })

  it('shows no format badge for a field without formats', async () => {
    const { user } = await openDesigner()
    await addColumn(user, 'Vendor')

    expect(chipTexts()[0]).not.toMatch(/이름|코드|그대로/)
    await open(user, 0, 'Vendor')
  })

  it('shows the typed display name on the chip and falls back to the field name when cleared', async () => {
    const { user } = await openDesigner()
    await addColumn(user, '금액')
    const input = within(await open(user, 0, '금액')).getByRole('textbox', { name: '표시 이름' })

    expect(input).toHaveAttribute('maxLength', '100')

    await user.type(input, '매출')

    expect(chipTexts()[0]).toContain('매출')
    expect(screen.getByRole('button', { name: '매출 빼기' })).toBeVisible()

    await user.clear(screen.getByRole('textbox', { name: '표시 이름' }))

    expect(chipTexts()[0]).toContain('금액')
  })

  it('has no share hint on any column (AC-8)', async () => {
    const { user } = await openDesigner()
    await addColumn(user, '금액')
    await addColumn(user, 'Expected Close')
    await open(user, 0, '금액')
    expect(screen.queryByText(/구성비/)).not.toBeInTheDocument()

    await open(user, 1, 'Expected Close')

    expect(screen.queryByText(/구성비/)).not.toBeInTheDocument()
  })
})
