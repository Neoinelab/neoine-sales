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

describe('집계 선택', () => {
  // 테스트 코드: RQ-075
  it('그룹이 있으면 집계를 켜고 텍스트에는 건수 종류만 고르게 한다', async () => {
    // given: Vendor, 금액, Deal code 컬럼
    const { user } = await openDesigner()
    await addColumn(user, 'Vendor')
    await addColumn(user, '금액')
    await addColumn(user, 'Deal code')

    // when: 그룹핑 전에 금액의 집계를 본다
    const before = await open(user, 1, '금액')
    // then: 집계가 꺼져 있고 그룹핑 안내가 보인다
    expect(within(before).getByRole('combobox', { name: '집계' })).toBeDisabled()
    expect(within(before).getByText('(그룹핑이 있을 때)')).toBeVisible()

    // when: Vendor를 그룹핑한다
    await user.click(within(await open(user, 0, 'Vendor')).getByRole('checkbox', { name: '그룹핑' }))

    // then: 금액은 합계 기본에 4종, Deal code는 건수 기본에 건수·고유 건수만 고르게 되고 빈 선택지가 없다
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

  // 테스트 코드: RQ-075
  it('그룹핑 중에 나중에 넣은 텍스트 컬럼은 건수로 채워지고 빈 집계 선택지가 없다', async () => {
    // given: Vendor를 그룹핑한 설계
    const { user } = await openDesigner()
    await addColumn(user, 'Vendor')
    await user.click(within(await open(user, 0, 'Vendor')).getByRole('checkbox', { name: '그룹핑' }))
    // when: Deal 이름 컬럼을 넣는다
    await addColumn(user, 'Deal 이름')

    // then: 집계가 켜지고 건수로 채워져 칩에도 보이며 빈 선택지가 없다
    const name = within(await open(user, 1, 'Deal 이름')).getByRole('combobox', { name: '집계' })

    expect(name).toBeEnabled()
    expect(name).toHaveDisplayValue('건수')
    expect(chipTexts()[1]).toContain('건수')
    expect(screen.queryByText('집계 선택')).not.toBeInTheDocument()
    for (const select of screen.getAllByRole('combobox', { name: '집계' })) {
      expect(within(select).queryByRole('option', { name: '' })).not.toBeInTheDocument()
    }
  })

  // 테스트 코드: RQ-075
  it('그룹 컬럼의 집계는 꺼지고 대시를 보이며 숫자는 합계를 유지한다', async () => {
    // given: Vendor를 그룹핑하고 금액을 넣은 설계
    const { user } = await openDesigner()
    await addColumn(user, 'Vendor')
    await addColumn(user, '금액')
    await user.click(within(await open(user, 0, 'Vendor')).getByRole('checkbox', { name: '그룹핑' }))

    // when: Vendor 설정의 집계를 본다
    const group = within(await open(user, 0, 'Vendor')).getByRole('combobox', { name: '집계' })

    // then: 꺼져 있고 —로 보이며 금액은 합계다
    expect(group).toBeDisabled()
    expect(group).toHaveDisplayValue('—')
    expect(within(await open(user, 1, '금액')).getByRole('combobox', { name: '집계' })).toHaveDisplayValue('합계')
  })

  // 테스트 코드: RQ-075
  it('다른 집계를 고를 수 있고 그룹핑을 끄면 집계가 비워진다', async () => {
    // given: Vendor를 그룹핑하고 금액을 넣은 설계
    const { user } = await openDesigner()
    await addColumn(user, 'Vendor')
    await addColumn(user, '금액')
    await user.click(within(await open(user, 0, 'Vendor')).getByRole('checkbox', { name: '그룹핑' }))

    // when: 금액 집계를 최대로 바꾼다
    await user.selectOptions(within(await open(user, 1, '금액')).getByRole('combobox', { name: '집계' }), 'max')
    // then: 칩에 최대가 보인다
    expect(chipTexts()[1]).toContain('최대')

    // when: Vendor 그룹핑을 끈다
    await user.click(within(await open(user, 0, 'Vendor')).getByRole('checkbox', { name: '그룹핑' }))

    // then: 금액 집계가 꺼지고 칩에서 최대가 사라진다
    expect(within(await open(user, 1, '금액')).getByRole('combobox', { name: '집계' })).toBeDisabled()
    expect(chipTexts()[1]).not.toContain('최대')
  })

  // 테스트 코드: RQ-076
  it('칩에 그룹과 집계 배지를 보인다', async () => {
    // given: Vendor, 금액, 체류 일수 컬럼
    const { user } = await openDesigner()
    await addColumn(user, 'Vendor')
    await addColumn(user, '금액')
    await addColumn(user, 'Status 체류 일수')
    // when: Vendor를 그룹핑한다
    await user.click(within(await open(user, 0, 'Vendor')).getByRole('checkbox', { name: '그룹핑' }))

    // then: Vendor는 그룹, 금액은 합계, 체류 일수는 평균 배지다
    const [vendor, amount, days] = chipTexts()

    expect(vendor).toContain('그룹')
    expect(amount).toContain('합계')
    expect(days).toContain('평균')
  })

  // 테스트 코드: RQ-076
  it('기본이 아닌 날짜 포맷은 배지로 보이고 숫자에는 단위 배지가 없다', async () => {
    // given: 금액과 Expected Close 컬럼
    const { user } = await openDesigner()
    await addColumn(user, '금액')
    await addColumn(user, 'Expected Close')
    expect(chipTexts()[0]).not.toContain('천원')

    // when: Expected Close 포맷을 분기로 바꾼다
    await user.selectOptions(within(await open(user, 1, 'Expected Close')).getByRole('combobox', { name: '포맷' }), 'quarter')

    // then: 칩에 분기 배지가 있고 금액 칩에는 예전 단위 배지가 없다
    expect(chipTexts()[1]).toContain('분기')
    for (const unit of ['천원', '백만원', '천 단위', '소수 1자리', '구성비']) expect(chipTexts()[0]).not.toContain(unit)
  })

  // 테스트 코드: RQ-076
  it('Action 건수는 그룹핑과 집계가 잠기고 그룹핑할 때만 쓴다는 배지가 붙는다', async () => {
    // when: Vendor와 Action 건수 컬럼을 넣는다
    const { user } = await openDesigner()
    await addColumn(user, 'Vendor')
    await addColumn(user, 'Action 건수')
    // then: 그룹핑 전에는 칩에 그룹핑할 때만 배지가 있다
    expect(chipTexts()[1]).toContain('그룹핑할 때만')

    // when: Vendor를 그룹핑한다
    await user.click(within(await open(user, 0, 'Vendor')).getByRole('checkbox', { name: '그룹핑' }))
    // then: Action 건수의 그룹핑·집계가 꺼져 있고 집계는 건수이며 배지가 사라진다
    const panel = await open(user, 1, 'Action 건수')

    expect(within(panel).getByRole('checkbox', { name: '그룹핑' })).toBeDisabled()
    expect(within(panel).getByRole('combobox', { name: '집계' })).toBeDisabled()
    expect(within(panel).getByRole('combobox', { name: '집계' })).toHaveDisplayValue('건수')
    expect(chipTexts()[1]).not.toContain('그룹핑할 때만')
  })
})

describe('포맷·표시 이름', () => {
  // 테스트 코드: RQ-074
  it('필드 형식에 맞는 포맷만 고르게 한다', async () => {
    // given: 텍스트·코드·숫자·날짜·시각 컬럼
    const { user } = await openDesigner()
    await addColumn(user, 'Deal code')
    await addColumn(user, 'Vendor')
    await addColumn(user, '금액')
    await addColumn(user, 'Expected Close')
    await addColumn(user, '등록일')

    // when: 컬럼마다 포맷 선택을 연다
    const formats = async (index: number, name: string) =>
      optionTexts(within(await open(user, index, name)).getByRole('combobox', { name: '포맷' }))
    const hasFormat = async (index: number, name: string) =>
      within(await open(user, index, name)).queryByRole('combobox', { name: '포맷' }) !== null

    // then: 텍스트·코드·숫자에는 포맷 선택이 없고 날짜·시각에는 형식별 목록이 있다
    expect(await hasFormat(0, 'Deal code')).toBe(false)
    expect(await hasFormat(1, 'Vendor')).toBe(false)
    expect(await hasFormat(2, '금액')).toBe(false)
    expect(plain(await formats(3, 'Expected Close'))).toEqual(['연-월-일', '연도', '분기', '월', '요일', '상대 시각'])
    expect(plain(await formats(4, '등록일'))).toEqual(['연-월-일 시:분', '연-월-일', '연도', '분기', '월', '요일', '상대 시각'])
  })

  // 테스트 코드: RQ-074
  it('텍스트·코드·사용자·숫자 필드에는 포맷 선택이 없다', async () => {
    // given: 텍스트·코드·사용자·숫자 컬럼 여섯 개
    const { user } = await openDesigner()
    await addColumn(user, 'Deal 이름')
    await addColumn(user, 'Status')
    await addColumn(user, '담당자')
    await addColumn(user, '금액')
    await addColumn(user, 'Users count')
    await addColumn(user, 'Status 체류 일수')

    // when: 컬럼마다 설정을 연다
    for (const [index, name] of [[0, 'Deal 이름'], [1, 'Status'], [2, '담당자'], [3, '금액'], [4, 'Users count'], [5, 'Status 체류 일수']] as const) {
      // then: 포맷 선택이 없다
      expect(within(await open(user, index, name)).queryByRole('combobox', { name: '포맷' })).not.toBeInTheDocument()
    }
  })

  // 테스트 코드: RQ-074
  it('묶음 단위를 바꾸는 포맷에 (묶음)을 붙인다', async () => {
    // given: Expected Close 컬럼
    const { user } = await openDesigner()
    await addColumn(user, 'Expected Close')

    // when: 포맷 선택지를 연다
    const options = optionTexts(within(await open(user, 0, 'Expected Close')).getByRole('combobox', { name: '포맷' }))

    // then: 연-월-일·연도·분기·월에만 (묶음) 표시가 있다
    expect(options.filter((t) => t.includes('(묶음)')).map((t) => t.replace(/\s*\(묶음\)$/, ''))).toEqual(['연-월-일', '연도', '분기', '월'])
  })

  // 테스트 코드: RQ-077
  it('앞 N자 옵션은 모든 필드에 있고 켜기 전에는 N이 잠겨 있다', async () => {
    // given: 텍스트·숫자·날짜 컬럼
    const { user } = await openDesigner()
    await addColumn(user, 'Deal 이름')
    await addColumn(user, '금액')
    await addColumn(user, 'Expected Close')

    // when: 컬럼마다 설정을 연다
    for (const [index, name] of [[0, 'Deal 이름'], [1, '금액'], [2, 'Expected Close']] as const) {
      // then: 앞 N자 옵션은 꺼져 있고 N 칸은 잠겨 있다
      const panel = await open(user, index, name)
      expect(within(panel).getByRole('checkbox', { name: '앞 N자만 보기' })).not.toBeChecked()
      expect(within(panel).getByLabelText('앞 N자의 N')).toBeDisabled()
    }
  })

  // 테스트 코드: RQ-077
  it('앞 N자를 켜면 N이 20이고 칩 배지가 붙으며 끄면 사라진다', async () => {
    // given: Deal 이름 컬럼
    const { user } = await openDesigner()
    await addColumn(user, 'Deal 이름')
    const panel = await open(user, 0, 'Deal 이름')
    expect(chipTexts()[0]).not.toContain('앞 20자')

    // when: 앞 N자 옵션을 켠다
    await user.click(within(panel).getByRole('checkbox', { name: '앞 N자만 보기' }))
    // then: N 칸이 켜져 값 20, 범위 1~200이고 칩에 앞 20자 배지가 붙는다
    const length = within(settingsOf('Deal 이름')).getByLabelText('앞 N자의 N')

    expect(length).toBeEnabled()
    expect(length).toHaveValue(20)
    expect(length).toHaveAttribute('min', '1')
    expect(length).toHaveAttribute('max', '200')
    expect(chipTexts()[0]).toContain('앞 20자')

    // when: 앞 N자 옵션을 끈다
    await user.click(within(settingsOf('Deal 이름')).getByRole('checkbox', { name: '앞 N자만 보기' }))

    // then: N 칸이 잠기고 배지가 사라진다
    expect(within(settingsOf('Deal 이름')).getByLabelText('앞 N자의 N')).toBeDisabled()
    expect(chipTexts()[0]).not.toContain('앞')
  })

  // 테스트 코드: RQ-076
  it('입력한 N이 배지에 보이고 포맷을 바꿔도 옵션이 유지된다', async () => {
    // given: 앞 N자를 7로 켠 Expected Close 컬럼
    const { user } = await openDesigner()
    await addColumn(user, 'Expected Close')
    const panel = await open(user, 0, 'Expected Close')
    await user.click(within(panel).getByRole('checkbox', { name: '앞 N자만 보기' }))
    const length = within(settingsOf('Expected Close')).getByLabelText('앞 N자의 N')
    await user.clear(length)
    await user.type(length, '7')

    // when: 포맷을 요일로 바꾼다
    await user.selectOptions(within(settingsOf('Expected Close')).getByRole('combobox', { name: '포맷' }), 'weekday')

    // then: 배지가 앞 7자이고 옵션이 켜진 채 남는다
    expect(chipTexts()[0]).toContain('앞 7자')
    expect(within(settingsOf('Expected Close')).getByRole('checkbox', { name: '앞 N자만 보기' })).toBeChecked()
  })

  // 테스트 코드: RQ-076
  it('포맷이 없는 필드는 포맷 배지가 없다', async () => {
    // when: Vendor 컬럼을 넣는다
    const { user } = await openDesigner()
    await addColumn(user, 'Vendor')

    // then: 칩에 이름·코드·그대로 같은 포맷 배지가 없다
    expect(chipTexts()[0]).not.toMatch(/이름|코드|그대로/)
    await open(user, 0, 'Vendor')
  })

  // 테스트 코드: RQ-074
  it('표시 이름을 입력하면 칩에 보이고 지우면 필드 이름으로 돌아간다', async () => {
    // given: 금액 컬럼
    const { user } = await openDesigner()
    await addColumn(user, '금액')
    const input = within(await open(user, 0, '금액')).getByRole('textbox', { name: '표시 이름' })

    expect(input).toHaveAttribute('maxLength', '100')

    // when: 표시 이름에 매출을 입력한다
    await user.type(input, '매출')

    // then: 칩과 빼기 버튼 이름에 매출이 보인다
    expect(chipTexts()[0]).toContain('매출')
    expect(screen.getByRole('button', { name: '매출 빼기' })).toBeVisible()

    // when: 표시 이름을 지운다
    await user.clear(screen.getByRole('textbox', { name: '표시 이름' }))

    // then: 칩이 금액으로 돌아간다
    expect(chipTexts()[0]).toContain('금액')
  })

  // 테스트 코드: RQ-074
  it('어떤 컬럼에도 구성비 안내가 없다', async () => {
    // given: 금액과 Expected Close 컬럼
    const { user } = await openDesigner()
    await addColumn(user, '금액')
    await addColumn(user, 'Expected Close')
    // when: 각 컬럼의 설정을 연다
    await open(user, 0, '금액')
    // then: 구성비 안내가 없다
    expect(screen.queryByText(/구성비/)).not.toBeInTheDocument()

    await open(user, 1, 'Expected Close')

    expect(screen.queryByText(/구성비/)).not.toBeInTheDocument()
  })
})
