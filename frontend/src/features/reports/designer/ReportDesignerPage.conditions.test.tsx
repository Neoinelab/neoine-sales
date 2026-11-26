import { screen, within } from '@testing-library/react'
import { describe, expect, it } from 'vitest'
import { mockControl } from '../../../test/fake/default'
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

describe('조건 행', () => {
  // 테스트 코드: RQ-078
  it('필드 목록에서 조건을 추가하고 필드를 바꾸면 연산자가 그 필드 기본으로 돌아간다', async () => {
    // given: 빈 설계
    const { user } = await openDesigner()

    // when: Vendor 조건을 추가한다
    await addCondition(user, 'Vendor')

    // then: 필드 Vendor, 연산자 다음 중 하나, 값 선택 버튼이 보인다
    expect(screen.getByRole('combobox', { name: '조건 1 필드' })).toHaveDisplayValue('Vendor')
    expect(screen.getByRole('combobox', { name: '조건 1 연산자' })).toHaveDisplayValue('다음 중 하나')
    expect(screen.getByRole('button', { name: /^조건 1 값/ })).toBeVisible()

    // when: 조건 필드를 금액으로 바꾼다
    await user.selectOptions(screen.getByRole('combobox', { name: '조건 1 필드' }), 'deal.amount')

    // then: 연산자가 =로 돌아가고 숫자 연산자 7개만 고르며 값이 비어 있다
    expect(screen.getByRole('combobox', { name: '조건 1 연산자' })).toHaveDisplayValue('=')
    expect(optionTexts(screen.getByRole('combobox', { name: '조건 1 연산자' }))).toEqual(['=', '≠', '>', '≥', '<', '≤', '범위'])
    expect(screen.getByRole('textbox', { name: '조건 1 값' })).toHaveValue('')
  })

  // 테스트 코드: RQ-078
  it('+ 조건 추가 버튼은 조건에 쓸 수 있는 첫 필드로 행을 만든다', async () => {
    // given: 빈 설계
    const { user } = await openDesigner()

    // when: + 조건 추가를 누른다
    await user.click(screen.getByRole('button', { name: '+ 조건 추가' }))

    // then: 필드 Deal code, 연산자 포함인 행이 생긴다
    expect(screen.getByRole('combobox', { name: '조건 1 필드' })).toHaveDisplayValue('Deal code')
    expect(screen.getByRole('combobox', { name: '조건 1 연산자' })).toHaveDisplayValue('포함')
  })

  // 테스트 코드: RQ-078
  it('조건 필드 선택에는 조건에 쓸 수 있는 필드만 나온다', async () => {
    // given: Vendor 조건 하나
    const { user } = await openDesigner()
    // when: 조건 추가 뒤 필드 선택지를 읽는다
    await addCondition(user, 'Vendor')

    const names = optionTexts(screen.getByRole('combobox', { name: '조건 1 필드' }))

    expect(names).toHaveLength(42)
    expect(names).toEqual(expect.arrayContaining(['작성일자', '수정일자', '작성자']))
    expect(names).not.toContain('Action 건수')
  })

  // 테스트 코드: RQ-078
  it('조건을 지우면 나머지 번호가 다시 매겨진다', async () => {
    // given: Vendor와 Status 조건
    const { user } = await openDesigner()
    await addCondition(user, 'Vendor')
    await addCondition(user, 'Status')

    // when: 조건 1을 지운다
    await user.click(screen.getByRole('button', { name: '조건 1 삭제' }))

    // then: Status가 조건 1이 되고 조건 2는 없다
    expect(screen.getByRole('combobox', { name: '조건 1 필드' })).toHaveDisplayValue('Status')
    expect(screen.queryByRole('combobox', { name: '조건 2 필드' })).not.toBeInTheDocument()
  })

  // 테스트 코드: RQ-078
  it('조건이 20개이면 더 추가할 수 없다', async () => {
    // given: 빈 설계
    const { user } = await openDesigner()
    // when: 조건을 20개 추가한다
    for (let i = 0; i < 20; i += 1) await user.click(screen.getByRole('button', { name: '+ 조건 추가' }))

    // then: + 조건 추가와 필드별 조건 추가 버튼이 꺼진다
    expect(screen.getByRole('button', { name: '+ 조건 추가' })).toBeDisabled()
    expect(screen.getByRole('button', { name: 'Vendor 조건 추가' })).toBeDisabled()
  }, 30_000)

  // 테스트 코드: RQ-078
  it('조건이 없으면 Deal 행과 Action 행 각각 무엇이 대상인지 안내한다', async () => {
    // when: 빈 설계를 연다
    const { user } = await openDesigner()
    // then: 모든 Deal이 대상이라는 안내가 보인다
    expect(screen.getByText(/조건이 없으면 모든 Deal이 대상입니다/)).toBeVisible()

    // when: Action 컬럼을 넣는다
    await addColumn(user, '진행사항')

    // then: 모든 Action이 대상이라는 안내로 바뀐다
    expect(screen.getByText(/조건이 없으면 모든 Action이 대상입니다/)).toBeVisible()

    // when: 조건을 추가한다
    await addCondition(user, 'Vendor')

    // then: 안내가 사라진다
    expect(screen.queryByText(/조건이 없으면/)).not.toBeInTheDocument()
  })

  // 테스트 코드: RQ-081
  it('값이 필요 없는 연산자는 값 입력칸이 없다', async () => {
    // given: Deal 이름 조건
    const { user } = await openDesigner()
    await addCondition(user, 'Deal 이름')

    // when: 연산자를 비어 있음으로 바꾼다
    await user.selectOptions(screen.getByRole('combobox', { name: '조건 1 연산자' }), 'is_empty')

    // then: 값 입력칸이 없다
    expect(screen.queryByLabelText('조건 1 값')).not.toBeInTheDocument()
  })
})

describe('조건 값 선택지', () => {
  // 테스트 코드: RQ-080
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
  ])('%s 조건의 목록 선택지는 출처의 선택지를 쓴다', async (label, expected) => {
    // given: 빈 설계
    const { user } = await openDesigner()
    // when: 그 필드의 조건을 추가하고 값 선택을 연다 (전제: 필드와 선택지 매개변수)
    await addCondition(user, label)

    const choices = await choicesOf(user, 1)

    // then: 출처의 선택지가 모두 보인다
    expect(choices).toEqual(expect.arrayContaining(expected))
  })

  // 테스트 코드: RQ-080
  it('정적 선택지와 코드 집합 선택지는 각자의 순서를 따른다', async () => {
    // given: 빈 설계
    const { user } = await openDesigner()
    // when: Status 조건을 추가하고 값 선택을 연다
    await addCondition(user, 'Status')

    // then: 선택지가 코드 순서다
    expect(await choicesOf(user, 1)).toEqual(['기회발굴', '제품소개', 'POC준비', 'POC완료', '기술평가', '가격협상', '계약완료'])
  })

  // 테스트 코드: RQ-080
  it('BANT 필드는 그 구분의 Label만 보인다', async () => {
    // given: 빈 설계
    const { user } = await openDesigner()
    // when: BANT Budget 조건을 추가하고 값 선택을 연다
    await addCondition(user, 'BANT Budget')

    const choices = await choicesOf(user, 1)

    // then: Budget Label만 있고 다른 구분의 Label은 없다
    expect(choices).toContain('단독 예산 확보')
    expect(choices).not.toContain('CEO 보고 완료')
    expect(choices).not.toContain('보안 사고 발생')
  })

  // 테스트 코드: RQ-080
  it('선택 개수와 모든 값의 이름을 표시하고 선택 해제를 반영한다', async () => {
    // given: Action 유형 조건의 값 선택이 열려 있다
    const { user } = await openDesigner()
    await addCondition(user, 'Action 유형')
    await choicesOf(user, 1)
    const panel = within(screen.getByRole('group', { name: '조건 1 값' }))

    // when: 통화를 고른다
    await user.click(panel.getByRole('checkbox', { name: '통화' }))
    expect(screen.getByRole('button', { name: '조건 1 값 1개 선택 · 통화' })).toHaveTextContent(/^1개 선택 · 통화$/)

    // when: 미팅을 고른다
    await user.click(panel.getByRole('checkbox', { name: '미팅' }))
    expect(screen.getByRole('button', { name: '조건 1 값 2개 선택 · 통화, 미팅' })).toBeVisible()

    // when: 이메일을 고른다
    await user.click(panel.getByRole('checkbox', { name: '이메일' }))
    expect(screen.getByRole('button', { name: '조건 1 값 3개 선택 · 통화, 미팅, 이메일' })).toBeVisible()

    await user.click(panel.getByRole('checkbox', { name: '미팅' }))
    expect(screen.getByRole('button', { name: '조건 1 값 2개 선택 · 통화, 이메일' })).toBeVisible()

    // when: 선택 해제를 누른다
    await user.click(panel.getByRole('button', { name: '선택 해제' }))
    // then: 요약이 선택으로 돌아간다
    expect(screen.getByRole('button', { name: '조건 1 값 선택' })).toBeVisible()
  })
})

describe('조건 값 입력', () => {
  // 테스트 코드: RQ-081
  it('날짜는 범위·이전·이후·상대 기간 입력을, 상대 기간은 최근 N일일 때만 일수 칸을 보인다', async () => {
    // given: Expected Close 조건
    const { user } = await openDesigner()
    // when: 조건을 추가한다
    await addCondition(user, 'Expected Close')

    // then: 연산자 4개와 시작·끝 칸의 yyyymmdd 자리표시가 보인다
    expect(optionTexts(screen.getByRole('combobox', { name: '조건 1 연산자' }))).toEqual(['범위', '이전', '이후', '상대 기간'])
    expect(screen.getByLabelText('조건 1 시작')).toHaveAttribute('placeholder', 'yyyymmdd')
    expect(screen.getByLabelText('조건 1 끝')).toHaveAttribute('placeholder', 'yyyymmdd')

    // when: 연산자를 이전으로 바꾼다
    await user.selectOptions(screen.getByRole('combobox', { name: '조건 1 연산자' }), 'before')
    // then: 한 칸 날짜 입력이 보인다
    expect(screen.getByLabelText('조건 1 값')).toHaveAttribute('placeholder', 'yyyymmdd')

    // when: 연산자를 상대 기간으로 바꾼다
    await user.selectOptions(screen.getByRole('combobox', { name: '조건 1 연산자' }), 'relative')
    // then: 기간 8개가 보이고 일수 칸은 없다
    const period = screen.getByRole('combobox', { name: '조건 1 기간' })
    expect(optionTexts(period)).toEqual(['최근 1개월', '최근 3개월', '최근 6개월', '올해', '이번 분기', '이번 달', '최근 N일', '오늘 이전'])
    expect(screen.queryByLabelText('조건 1 일수')).not.toBeInTheDocument()

    // when: 기간을 최근 N일로 바꾼다
    await user.selectOptions(period, 'last_n_days')
    // then: 일수 칸이 보인다
    expect(screen.getByLabelText('조건 1 일수')).toBeVisible()

    // when: 기간을 이번 달로 바꾼다
    await user.selectOptions(period, 'this_month')
    // then: 일수 칸이 사라진다
    expect(screen.queryByLabelText('조건 1 일수')).not.toBeInTheDocument()
  })

  // 테스트 코드: RQ-083
  it('최근 3개월은 일수 없이 보내고 일수 칸을 숨긴다', async () => {
    // given: Deal 이름 컬럼과 상대 기간 조건
    const { user } = await openDesigner()
    await addColumn(user, 'Deal 이름')
    await addCondition(user, 'Expected Close')
    await user.selectOptions(screen.getByRole('combobox', { name: '조건 1 연산자' }), 'relative')

    // when: 기간을 최근 3개월로 바꾼다
    await user.selectOptions(screen.getByRole('combobox', { name: '조건 1 기간' }), 'last_3_months')

    // then: 선택이 최근 3개월이고 일수 칸이 없다
    expect(screen.getByRole('combobox', { name: '조건 1 기간' })).toHaveDisplayValue('최근 3개월')
    expect(screen.queryByLabelText('조건 1 일수')).not.toBeInTheDocument()
    // when: 조회한다
    await runQuery(user)
    // then: 요청 조건은 기간만 있고 일수가 없다
    expect(lastQuery().conditions?.[0]).toEqual({ field: 'deal.expected_close', operator: 'relative', value: { period: 'last_3_months' } })
  })

  // 테스트 코드: RQ-084
  it('날짜 범위를 yyyymmdd로 입력하면 ISO 날짜로 보낸다', async () => {
    // given: Deal 이름 컬럼과 Expected Close 조건
    const { user } = await openDesigner()
    await addColumn(user, 'Deal 이름')
    await addCondition(user, 'Expected Close')

    // when: 시작과 끝을 yyyymmdd로 입력한다
    await user.type(screen.getByLabelText('조건 1 시작'), '20261001')
    await user.type(screen.getByLabelText('조건 1 끝'), '20261231')
    // then: 시작 칸이 yyyy.mm.dd로 보인다
    expect(screen.getByLabelText('조건 1 시작')).toHaveValue('2026.10.01')
    // when: 조회한다
    await runQuery(user)

    // then: 요청 값은 ISO 날짜 두 개다
    expect(lastQuery().conditions?.[0]).toMatchObject({ field: 'deal.expected_close', value: ['2026-10-01', '2026-12-31'] })
  })

  // 테스트 코드: RQ-084
  it('틀린 날짜는 요청 없이 그 칸에 안내한다', async () => {
    // given: Deal 이름 컬럼과 Expected Close 조건
    const { user } = await openDesigner()
    await addColumn(user, 'Deal 이름')
    await addCondition(user, 'Expected Close')

    // when: 시작에 없는 날짜, 끝에 올바른 날짜를 입력하고 조회한다
    await user.type(screen.getByLabelText('조건 1 시작'), '20261340')
    await user.type(screen.getByLabelText('조건 1 끝'), '20261231')
    await runQuery(user)

    // then: 요청이 없고 시작 칸만 오류 표시와 안내 문구를 가진다
    expect(mockControl.reportQueries()).toHaveLength(0)
    expect(screen.getByLabelText('조건 1 시작')).toHaveAttribute('aria-invalid', 'true')
    expect(screen.getByLabelText('조건 1 끝')).not.toHaveAttribute('aria-invalid')
    expect(screen.getByText('없는 날짜입니다.')).toBeVisible()
  })

  // 테스트 코드: RQ-084
  it('덜 입력한 한 칸 날짜도 요청 없이 안내한다', async () => {
    // given: 이전 연산자의 날짜 조건
    const { user } = await openDesigner()
    await addColumn(user, 'Deal 이름')
    await addCondition(user, 'Expected Close')
    await user.selectOptions(screen.getByRole('combobox', { name: '조건 1 연산자' }), 'before')

    // when: 날짜를 덜 입력하고 조회한다
    await user.type(screen.getByLabelText('조건 1 값'), '2026.1')
    await runQuery(user)

    // then: 요청이 없고 값 칸에 형식 안내가 보인다
    expect(mockControl.reportQueries()).toHaveLength(0)
    expect(screen.getByLabelText('조건 1 값')).toHaveAttribute('aria-invalid', 'true')
    expect(screen.getByText('날짜를 yyyymmdd 형식으로 입력하세요.')).toBeVisible()
  })

  // 테스트 코드: RQ-084
  it('빈 날짜는 날짜를 고르라는 안내를 보인다', async () => {
    // given: 값이 빈 이전 연산자의 날짜 조건
    const { user } = await openDesigner()
    await addColumn(user, 'Deal 이름')
    await addCondition(user, 'Expected Close')
    await user.selectOptions(screen.getByRole('combobox', { name: '조건 1 연산자' }), 'before')

    // when: 조회한다
    await runQuery(user)

    // then: 요청이 없고 날짜를 고르라는 안내가 보인다
    expect(mockControl.reportQueries()).toHaveLength(0)
    expect(screen.getByText('날짜를 고르세요')).toBeVisible()
  })

  // 테스트 코드: RQ-082
  it('금액 조건은 원 단위로 입력하라고 안내한다', async () => {
    // given: 빈 설계
    const { user } = await openDesigner()
    // when: 금액 조건을 추가한다
    await addCondition(user, '금액')

    // then: (원) 안내가 보인다
    expect(screen.getAllByText(/\(원\)/).length).toBeGreaterThan(0)

    // when: 연산자를 범위로 바꾼다
    await user.selectOptions(screen.getByRole('combobox', { name: '조건 1 연산자' }), 'between')

    // then: 시작·끝 칸이 보이고 (원) 안내가 남는다
    expect(screen.getByRole('textbox', { name: '조건 1 시작' })).toBeVisible()
    expect(screen.getByRole('textbox', { name: '조건 1 끝' })).toBeVisible()
    expect(screen.getAllByText(/\(원\)/).length).toBeGreaterThan(0)
  })

  // 테스트 코드: RQ-082
  it('금액 값은 숫자만 받고 입력하면서 콤마를 붙인다', async () => {
    // given: 금액 조건
    const { user } = await openDesigner()
    await addCondition(user, '금액')
    const value = screen.getByRole('textbox', { name: '조건 1 값' })

    // when: 글자를 입력한다
    await user.type(value, 'abc')
    // then: 값이 비어 있다
    expect(value).toHaveValue('')

    // when: 숫자 1000000을 입력한다
    await user.type(value, '1000000')
    // then: 콤마가 붙어 보인다
    expect(value).toHaveValue('1,000,000')
  })

  // 테스트 코드: RQ-082
  it('입력한 원을 변환 없이 조건 값으로 보낸다', async () => {
    // given: Deal code 컬럼과 금액 조건 1000000
    const { user } = await openDesigner()
    await addColumn(user, 'Deal code')
    await addCondition(user, '금액')
    await user.type(screen.getByRole('textbox', { name: '조건 1 값' }), '1000000')

    // when: 조회한다
    await runQuery(user)

    // then: 요청 값은 1,000,000이다
    expect(lastQuery().conditions).toEqual([{ field: 'deal.amount', operator: 'eq', value: 1_000_000 }])
  })

  // 테스트 코드: RQ-082
  it('금액 범위의 양끝을 입력한 원 그대로 보낸다', async () => {
    // given: 금액 범위 조건의 시작 1000000과 끝 5000000
    const { user } = await openDesigner()
    await addColumn(user, 'Deal code')
    await addCondition(user, '금액')
    await user.selectOptions(screen.getByRole('combobox', { name: '조건 1 연산자' }), 'between')
    await user.type(screen.getByRole('textbox', { name: '조건 1 시작' }), '1000000')
    await user.type(screen.getByRole('textbox', { name: '조건 1 끝' }), '5000000')
    expect(screen.getByRole('textbox', { name: '조건 1 끝' })).toHaveValue('5,000,000')

    // when: 조회한다
    await runQuery(user)

    // then: 요청 값은 [1,000,000, 5,000,000]이다
    expect(lastQuery().conditions).toEqual([{ field: 'deal.amount', operator: 'between', value: [1_000_000, 5_000_000] }])
  })

  // 테스트 코드: RQ-082
  it('Users count와 체류 일수 조건은 원 단위를 묻지 않는다', async () => {
    // given: 빈 설계
    const { user } = await openDesigner()
    // when: Users count와 Status 체류 일수 조건을 추가한다
    await addCondition(user, 'Users count')
    await addCondition(user, 'Status 체류 일수')

    // then: (원) 안내가 없다
    expect(screen.queryByText(/\(원\)/)).not.toBeInTheDocument()
  })

  // 테스트 코드: RQ-078
  it('다른 종류의 필드로 바꾸면 이전 값을 유지하지 않는다', async () => {
    // given: 텍스트 값 은행을 입력한 Deal 이름 조건
    const { user } = await openDesigner()
    await addCondition(user, 'Deal 이름')
    await user.type(screen.getByRole('textbox', { name: '조건 1 값' }), '은행')

    // when: 필드를 Users count로 바꾼다
    await user.selectOptions(screen.getByRole('combobox', { name: '조건 1 필드' }), 'deal.users')

    // then: 값이 비어 있다
    expect(screen.getByRole('textbox', { name: '조건 1 값' })).toHaveValue('')
  })
})

describe('조건 결합', () => {
  // 테스트 코드: RQ-079
  it('결합을 바꾸면 조건 사이 접속어가 바뀐다', async () => {
    // when: 컬럼 하나와 조건 두 개를 넣는다
    const { user } = await openDesigner()
    await addColumn(user, 'Deal code')
    await addCondition(user, 'Vendor')
    await addCondition(user, 'Status')

    // then: 기본은 AND이고 접속어도 AND다
    expect(screen.getByRole('radio', { name: /AND/ })).toBeChecked()
    expect(screen.getByRole('radio', { name: /OR/ })).not.toBeChecked()
    expect(screen.getByText('AND')).toBeVisible()
    expect(screen.queryByText('OR')).not.toBeInTheDocument()

    // when: OR를 고른다
    await user.click(screen.getByRole('radio', { name: /OR/ }))

    // then: 접속어가 OR로 바뀐다
    expect(screen.getByText('OR')).toBeVisible()
    expect(screen.queryByText('AND')).not.toBeInTheDocument()
  })

  // 테스트 코드: RQ-079
  it('고른 결합을 요청에 담아 보낸다', async () => {
    // given: Deal code 컬럼과 Deal 이름 조건 은행
    const { user } = await openDesigner()
    await addColumn(user, 'Deal code')
    await addCondition(user, 'Deal 이름')
    await user.type(screen.getByRole('textbox', { name: '조건 1 값' }), '은행')

    // when: OR를 고르고 조회한다
    await user.click(screen.getByRole('radio', { name: /OR/ }))
    await runQuery(user)

    // then: 요청의 combine이 or다
    await screen.findByRole('table', { name: '조회 결과' })
    expect(lastQuery().combine).toBe('or')
  })

  // 테스트 코드: RQ-079
  it('결합 라디오는 조건 결합 범례로 묶인다', async () => {
    // when: 디자이너를 연다
    await openDesigner()

    // then: 조건 결합 그룹이 보인다
    expect(screen.getByRole('group', { name: '조건 결합' })).toBeVisible()
  })
})
