import { screen, within } from '@testing-library/react'
import { describe, expect, it } from 'vitest'
import { addColumn, addCondition, lastQuery, openDesigner, runQuery, setupReportClock } from '../../../test/reportScreen'

setupReportClock()

const optionTexts = (select: HTMLElement): string[] => within(select).getAllByRole('option').map((o) => o.textContent ?? '')

/** n번째 조건의 값 선택 목록을 열고 보이는 선택지를 돌려준다. */
async function choicesOf(user: Awaited<ReturnType<typeof openDesigner>>['user'], n: number): Promise<string[]> {
  await user.click(screen.getByRole('button', { name: new RegExp(`^조건 ${n} 값`) }))
  return within(screen.getByRole('group', { name: `조건 ${n} 값` }))
    .getAllByRole('checkbox')
    .map((c) => (c.closest('label')?.textContent ?? '').trim())
}

describe('조건 행 (AC7)', () => {
  it('adds a condition from the field list and resets operator on field change', async () => {
    const { user } = await openDesigner()

    await addCondition(user, 'Vendor')

    expect(screen.getByRole('combobox', { name: '조건 1 필드' })).toHaveDisplayValue('Vendor')
    expect(screen.getByRole('combobox', { name: '조건 1 연산자' })).toHaveDisplayValue('다음 중 하나')
    expect(screen.getByRole('button', { name: /^조건 1 값/ })).toBeVisible()

    await user.selectOptions(screen.getByRole('combobox', { name: '조건 1 필드' }), 'deal.amount')

    expect(screen.getByRole('combobox', { name: '조건 1 연산자' })).toHaveDisplayValue('=')
    expect(optionTexts(screen.getByRole('combobox', { name: '조건 1 연산자' }))).toEqual(['=', '≠', '>', '≥', '<', '≤', '범위'])
    expect(screen.getByRole('textbox', { name: '조건 1 값' })).toHaveValue('')
  })

  it('adds a row with the first filterable field from the add button', async () => {
    const { user } = await openDesigner()

    await user.click(screen.getByRole('button', { name: '+ 조건 추가' }))

    expect(screen.getByRole('combobox', { name: '조건 1 필드' })).toHaveDisplayValue('Deal code')
    expect(screen.getByRole('combobox', { name: '조건 1 연산자' })).toHaveDisplayValue('포함')
  })

  it('lists only the filterable fields in the field select', async () => {
    const { user } = await openDesigner()
    await addCondition(user, 'Vendor')

    const names = optionTexts(screen.getByRole('combobox', { name: '조건 1 필드' }))

    expect(names).toHaveLength(39)
    expect(names).not.toContain('Action 건수')
  })

  it('removes a condition and renumbers the rest', async () => {
    const { user } = await openDesigner()
    await addCondition(user, 'Vendor')
    await addCondition(user, 'Status')

    await user.click(screen.getByRole('button', { name: '조건 1 삭제' }))

    expect(screen.getByRole('combobox', { name: '조건 1 필드' })).toHaveDisplayValue('Status')
    expect(screen.queryByRole('combobox', { name: '조건 2 필드' })).not.toBeInTheDocument()
  })

  it('disables adding at the condition limit', async () => {
    const { user } = await openDesigner()
    for (let i = 0; i < 20; i += 1) await user.click(screen.getByRole('button', { name: '+ 조건 추가' }))

    expect(screen.getByRole('button', { name: '+ 조건 추가' })).toBeDisabled()
    expect(screen.getByRole('button', { name: 'Vendor 조건 추가' })).toBeDisabled()
  }, 30_000)

  it('explains what no condition means for Deal rows and for Action rows', async () => {
    const { user } = await openDesigner()
    expect(screen.getByText(/조건이 없으면 모든 Deal이 대상입니다/)).toBeVisible()

    await addColumn(user, '진행사항')

    expect(screen.getByText(/조건이 없으면 모든 Action이 대상입니다/)).toBeVisible()

    await addCondition(user, 'Vendor')

    expect(screen.queryByText(/조건이 없으면/)).not.toBeInTheDocument()
  })

  it('shows no value input for an operator without a value', async () => {
    const { user } = await openDesigner()
    await addCondition(user, 'Deal 이름')

    await user.selectOptions(screen.getByRole('combobox', { name: '조건 1 연산자' }), 'is_empty')

    expect(screen.queryByLabelText('조건 1 값')).not.toBeInTheDocument()
  })
})

describe('조건 값 선택지 (AC7)', () => {
  it.each([
    ['Vendor', ['CrowdStrike', 'Okta', 'Silverfort', 'Zscaler']],
    ['담당자', ['김영업', '박영업', '강퇴사(퇴사)']],
    ['Status', ['기회발굴', '제품소개', 'POC준비', 'POC완료', '기술평가', '가격협상', '계약완료']],
    ['Forecast', ['Pipeline', 'Best', 'Most Likely', 'Commit', 'Won', 'Lost']],
    ['당시 Status', ['기회발굴', '계약완료']],
    ['BANT Budget', ['단독 예산 확보', '예산 없음', '미확인']],
    ['Action 유형', ['통화', '미팅', '이메일', '데모', '제안', '협상', '계약', '기타']],
    ['수행자', ['김영업', '강퇴사(퇴사)']],
    ['경고', ['기한초과', '미업데이트']],
    ['Forecast 구분', ['Open', 'Won', 'Lost']],
    ['견적 제출', ['YES', 'NO']],
    ['POC 상태', ['YES', 'ING', 'NO']],
  ])('uses the list choices of the options source of %s', async (label, expected) => {
    const { user } = await openDesigner()
    await addCondition(user, label)

    const choices = await choicesOf(user, 1)

    expect(choices).toEqual(expect.arrayContaining(expected))
  })

  it('keeps the choices of the static and the code sets in their own order', async () => {
    const { user } = await openDesigner()
    await addCondition(user, 'Status')

    expect(await choicesOf(user, 1)).toEqual(['기회발굴', '제품소개', 'POC준비', 'POC완료', '기술평가', '가격협상', '계약완료'])
  })

  it('shows only the Label category of the BANT field', async () => {
    const { user } = await openDesigner()
    await addCondition(user, 'BANT Budget')

    const choices = await choicesOf(user, 1)

    expect(choices).toContain('단독 예산 확보')
    expect(choices).not.toContain('CEO 보고 완료')
    expect(choices).not.toContain('보안 사고 발생')
  })

  it('summarizes the selection and offers a clear button', async () => {
    const { user } = await openDesigner()
    await addCondition(user, 'Action 유형')
    await choicesOf(user, 1)
    const panel = within(screen.getByRole('group', { name: '조건 1 값' }))

    await user.click(panel.getByRole('checkbox', { name: '통화' }))
    expect(screen.getByRole('button', { name: '조건 1 값 통화' })).toBeVisible()

    await user.click(panel.getByRole('checkbox', { name: '미팅' }))
    expect(screen.getByRole('button', { name: '조건 1 값 통화, 미팅' })).toBeVisible()

    await user.click(panel.getByRole('checkbox', { name: '이메일' }))
    expect(screen.getByRole('button', { name: '조건 1 값 통화, 미팅 외 1' })).toBeVisible()

    await user.click(panel.getByRole('button', { name: '선택 해제' }))
    expect(screen.getByRole('button', { name: '조건 1 값 선택' })).toBeVisible()
  })
})

describe('조건 값 입력 (AC7)', () => {
  it('shows date range, relative period with days, and money input in thousands', async () => {
    const { user } = await openDesigner()
    await addCondition(user, 'Expected Close')

    expect(optionTexts(screen.getByRole('combobox', { name: '조건 1 연산자' }))).toEqual(['범위', '이전', '이후', '상대 기간'])
    expect(screen.getByLabelText('조건 1 시작')).toHaveAttribute('type', 'date')
    expect(screen.getByLabelText('조건 1 끝')).toHaveAttribute('type', 'date')

    await user.selectOptions(screen.getByRole('combobox', { name: '조건 1 연산자' }), 'before')
    expect(screen.getByLabelText('조건 1 값')).toHaveAttribute('type', 'date')

    await user.selectOptions(screen.getByRole('combobox', { name: '조건 1 연산자' }), 'relative')
    const period = screen.getByRole('combobox', { name: '조건 1 기간' })
    expect(optionTexts(period)).toEqual(['올해', '이번 분기', '이번 달', '최근 N일', '오늘 이전'])
    expect(screen.queryByLabelText('조건 1 일수')).not.toBeInTheDocument()

    await user.selectOptions(period, 'last_n_days')
    expect(screen.getByLabelText('조건 1 일수')).toBeVisible()

    await user.selectOptions(period, 'this_month')
    expect(screen.queryByLabelText('조건 1 일수')).not.toBeInTheDocument()
  })

  it('asks for the amount in thousand won', async () => {
    const { user } = await openDesigner()
    await addCondition(user, '금액(원)')

    expect(screen.getAllByText(/\(천원\)/).length).toBeGreaterThan(0)

    await user.selectOptions(screen.getByRole('combobox', { name: '조건 1 연산자' }), 'between')

    expect(screen.getByRole('textbox', { name: '조건 1 시작' })).toBeVisible()
    expect(screen.getByRole('textbox', { name: '조건 1 끝' })).toBeVisible()
    expect(screen.getAllByText(/\(천원\)/).length).toBeGreaterThan(0)
  })

  it('does not keep an old value when the field changes to another kind', async () => {
    const { user } = await openDesigner()
    await addCondition(user, 'Deal 이름')
    await user.type(screen.getByRole('textbox', { name: '조건 1 값' }), '은행')

    await user.selectOptions(screen.getByRole('combobox', { name: '조건 1 필드' }), 'deal.users')

    expect(screen.getByRole('textbox', { name: '조건 1 값' })).toHaveValue('')
  })
})

describe('조건 결합 (AC8)', () => {
  it('switches the combine and the joining words', async () => {
    const { user } = await openDesigner()
    await addColumn(user, 'Deal code')
    await addCondition(user, 'Vendor')
    await addCondition(user, 'Status')

    expect(screen.getByRole('radio', { name: /AND/ })).toBeChecked()
    expect(screen.getByRole('radio', { name: /OR/ })).not.toBeChecked()
    expect(screen.getByText('AND')).toBeVisible()
    expect(screen.queryByText('OR')).not.toBeInTheDocument()

    await user.click(screen.getByRole('radio', { name: /OR/ }))

    expect(screen.getByText('OR')).toBeVisible()
    expect(screen.queryByText('AND')).not.toBeInTheDocument()
  })

  it('sends the chosen combine in the request', async () => {
    const { user } = await openDesigner()
    await addColumn(user, 'Deal code')
    await addCondition(user, 'Deal 이름')
    await user.type(screen.getByRole('textbox', { name: '조건 1 값' }), '은행')

    await user.click(screen.getByRole('radio', { name: /OR/ }))
    await runQuery(user)

    await screen.findByRole('table', { name: '조회 결과' })
    expect(lastQuery().combine).toBe('or')
  })

  it('groups the radios under the legend 조건 결합', async () => {
    await openDesigner()

    expect(screen.getByRole('group', { name: '조건 결합' })).toBeVisible()
  })
})
