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
    await addColumn(user, '금액(원)')
    await addColumn(user, 'Deal code')

    const before = await open(user, 1, '금액(원)')
    expect(within(before).getByRole('combobox', { name: '집계' })).toBeDisabled()
    expect(within(before).getByText('(그룹핑이 있을 때)')).toBeVisible()

    await user.click(within(await open(user, 0, 'Vendor')).getByRole('checkbox', { name: '그룹핑' }))

    const amount = within(await open(user, 1, '금액(원)')).getByRole('combobox', { name: '집계' })
    expect(amount).toBeEnabled()
    expect(amount).toHaveDisplayValue('합계')
    expect(optionTexts(amount)).toEqual(['합계', '평균', '최소', '최대'])

    const code = within(await open(user, 2, 'Deal code')).getByRole('combobox', { name: '집계' })
    expect(code).toBeEnabled()
    expect(code).toHaveDisplayValue('집계 선택')
    expect(optionTexts(code)).toEqual(['집계 선택', '건수', '고유 건수'])
  })

  it('lets the user pick another aggregate and clears it when the group is turned off', async () => {
    const { user } = await openDesigner()
    await addColumn(user, 'Vendor')
    await addColumn(user, '금액(원)')
    await user.click(within(await open(user, 0, 'Vendor')).getByRole('checkbox', { name: '그룹핑' }))

    await user.selectOptions(within(await open(user, 1, '금액(원)')).getByRole('combobox', { name: '집계' }), 'max')
    expect(chipTexts()[1]).toContain('최대')

    await user.click(within(await open(user, 0, 'Vendor')).getByRole('checkbox', { name: '그룹핑' }))

    expect(within(await open(user, 1, '금액(원)')).getByRole('combobox', { name: '집계' })).toBeDisabled()
    expect(chipTexts()[1]).not.toContain('최대')
  })

  it('shows group and aggregate badges on chips', async () => {
    const { user } = await openDesigner()
    await addColumn(user, 'Vendor')
    await addColumn(user, '금액(원)')
    await addColumn(user, 'Status 체류 일수')
    await user.click(within(await open(user, 0, 'Vendor')).getByRole('checkbox', { name: '그룹핑' }))

    const [vendor, amount, days] = chipTexts()

    expect(vendor).toContain('그룹')
    expect(amount).toContain('합계')
    expect(days).toContain('평균')
  })

  it('shows the name of a format that is not the default as a badge', async () => {
    const { user } = await openDesigner()
    await addColumn(user, '금액(원)')
    await addColumn(user, 'Expected Close')
    expect(chipTexts()[0]).not.toContain('천원')

    await user.selectOptions(within(await open(user, 0, '금액(원)')).getByRole('combobox', { name: '포맷' }), 'krw_million')
    await user.selectOptions(within(await open(user, 1, 'Expected Close')).getByRole('combobox', { name: '포맷' }), 'quarter')

    expect(chipTexts()[0]).toContain('백만원')
    expect(chipTexts()[1]).toContain('분기')
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
    await addColumn(user, '금액(원)')
    await addColumn(user, 'Expected Close')
    await addColumn(user, '등록일')

    const formats = async (index: number, name: string) =>
      optionTexts(within(await open(user, index, name)).getByRole('combobox', { name: '포맷' }))

    expect(plain(await formats(0, 'Deal code'))).toEqual(['그대로', '앞 N자'])
    expect(plain(await formats(1, 'Vendor'))).toEqual(['이름', '코드'])
    expect(plain(await formats(2, '금액(원)'))).toEqual(['천 단위 구분', '천원', '백만원', '소수 1자리', '구성비(%)'])
    expect(plain(await formats(3, 'Expected Close'))).toEqual(['연-월-일', '연도', '분기', '월', '요일', '상대 시각'])
    expect(plain(await formats(4, '등록일'))).toEqual(['연-월-일 시:분', '연-월-일', '연도', '분기', '월', '요일', '상대 시각'])
  })

  it('marks the formats that change the grouping with (묶음)', async () => {
    const { user } = await openDesigner()
    await addColumn(user, 'Expected Close')

    const options = optionTexts(within(await open(user, 0, 'Expected Close')).getByRole('combobox', { name: '포맷' }))

    expect(options.filter((t) => t.includes('(묶음)')).map((t) => t.replace(/\s*\(묶음\)$/, ''))).toEqual(['연-월-일', '연도', '분기', '월'])
  })

  it('shows the length input only for the prefix format with the default 20', async () => {
    const { user } = await openDesigner()
    await addColumn(user, 'Deal 이름')
    const panel = await open(user, 0, 'Deal 이름')
    expect(within(panel).queryByLabelText('앞 N자의 N')).not.toBeInTheDocument()

    await user.selectOptions(within(panel).getByRole('combobox', { name: '포맷' }), 'prefix')
    const length = within(settingsOf('Deal 이름')).getByLabelText('앞 N자의 N')

    expect(length).toHaveValue(20)
    expect(length).toHaveAttribute('min', '1')
    expect(length).toHaveAttribute('max', '200')

    await user.selectOptions(within(settingsOf('Deal 이름')).getByRole('combobox', { name: '포맷' }), 'as_is')

    expect(within(settingsOf('Deal 이름')).queryByLabelText('앞 N자의 N')).not.toBeInTheDocument()
  })

  it('shows the typed display name on the chip and falls back to the field name when cleared', async () => {
    const { user } = await openDesigner()
    await addColumn(user, '금액(원)')
    const input = within(await open(user, 0, '금액(원)')).getByRole('textbox', { name: '표시 이름' })

    expect(input).toHaveAttribute('maxLength', '100')

    await user.type(input, '매출')

    expect(chipTexts()[0]).toContain('매출')
    expect(screen.getByRole('button', { name: '매출 빼기' })).toBeVisible()

    await user.clear(screen.getByRole('textbox', { name: '표시 이름' }))

    expect(chipTexts()[0]).toContain('금액(원)')
  })

  it('explains that the share is calculated only for grouped sums and counts', async () => {
    const { user } = await openDesigner()
    await addColumn(user, '금액(원)')
    const panel = await open(user, 0, '금액(원)')
    expect(screen.queryByText(/구성비는 그룹핑한 결과의 합계·건수에서만 계산됩니다/)).not.toBeInTheDocument()

    await user.selectOptions(within(panel).getByRole('combobox', { name: '포맷' }), 'percent_share')

    expect(screen.getByText(/구성비는 그룹핑한 결과의 합계·건수에서만 계산됩니다/)).toBeVisible()
  })
})
