import { fireEvent, screen, waitFor, within } from '@testing-library/react'
import { afterEach, describe, expect, it, vi } from 'vitest'
import { gateway } from '../../../gateway'
import { renderAt, type TestRole } from '../../../test/mockApp'
import { detailPath } from '../../../test/detailTestUtils'

afterEach(() => vi.restoreAllMocks())

async function openDeal(no: number, title: string, role?: TestRole) {
  const view = await renderAt(await detailPath(no), role === undefined ? {} : { role })
  await screen.findByRole('heading', { level: 1, name: title })
  return view
}

describe('수정 버튼 제거와 권한 (클릭 편집)', () => {
  // 쓰기 권한자에게 수정 링크와 옛 편집 조각(연락처 수정·파트너 교체·새 Label 버튼)은 없고 삭제 버튼은 켜져 있다.
  // 테스트 코드: DD-070
  it('has no edit link, no tile edit buttons and no editor pieces on the detail page for a writer', async () => {
    // when: Deal 상세를 연다 (전제: Owner 본인 sales)
    await openDeal(1, '한빛은행 ITDR 도입')

    // then: '수정' 링크·'고객 연락처 수정'·'파트너 교체'·'새 Label' 버튼이 없고 'Deal 삭제'가 켜져 있다
    expect(screen.queryByRole('link', { name: '수정' })).not.toBeInTheDocument()
    expect(screen.queryByRole('button', { name: '고객 연락처 수정' })).not.toBeInTheDocument()
    expect(screen.queryByRole('button', { name: '파트너 교체' })).not.toBeInTheDocument()
    expect(screen.queryByRole('button', { name: /새 Label$/ })).not.toBeInTheDocument()
    expect(screen.getByRole('button', { name: 'Deal 삭제' })).toBeEnabled()
  })

  // 쓰기 권한자는 모든 값에 클릭 편집 버튼을 가진다.
  // 테스트 코드: DD-070
  it('gives a writer a click-to-edit button on every field value', async () => {
    // given: sales 사용자
    await openDeal(1, '한빛은행 ITDR 도입')

    // when: Deal 상세를 연다
    const names = [
      'Owner 수정',
      'Vendor 수정',
      'Product 수정',
      'Users count 수정',
      '견적 제출여부 수정',
      '견적 제출일 수정',
      'POC 여부 수정',
      'POC 완료일 수정',
      '구매절차 수정',
      '금액(단위:원) 수정',
      'Expected Close 수정',
      'Status 수정',
      'Forecast 수정',
      'Budget 수정',
      'Authority 수정',
      'Need 수정',
      'Timeline 수정',
      '고객 회사명 수정',
      '고객 담당자명 수정',
      '고객 직급 수정',
      '고객 이메일 수정',
      '고객 전화 수정',
      '파트너 회사명 수정',
      '파트너 담당자명 수정',
      '파트너 직급 수정',
      '파트너 이메일 수정',
      '파트너 전화 수정',
    ]

    // then: Owner부터 파트너 전화까지 27개 '<항목> 수정' 버튼과 이름 편집 title이 보인다
    for (const name of names) expect(screen.getByRole('button', { name })).toBeVisible()
    expect(screen.getByTitle('Deal 이름 수정')).toBeVisible()
  })

  // user는 같은 값을 글자로만 보고 편집 버튼이 없다.
  // 테스트 코드: DD-073
  it('shows a viewer the same values without any click-to-edit control', async () => {
    // when: Deal 상세를 연다 (전제: user 역할 사용자)
    await openDeal(1, '한빛은행 ITDR 도입', 'user')

    // then: '<항목> 수정' 버튼과 이름 편집이 없고 Owner·Vendor·고객·BANT 값이 보인다
    expect(screen.queryAllByRole('button', { name: / 수정$/ })).toHaveLength(0)
    expect(screen.queryByTitle('Deal 이름 수정')).not.toBeInTheDocument()
    expect(within(screen.getByRole('region', { name: 'Deal 정보' })).getByText('김영업')).toBeVisible()
    expect(screen.getByText('Silverfort')).toBeVisible()
    expect(screen.getByText('정민수')).toBeVisible()
    expect(screen.getByText('단독 예산 확보')).toBeVisible()
  })
})

describe('값 클릭 → 입력기 (Enter 저장 / Esc 취소 / 키보드)', () => {
  // Enter·Space로 편집을 열면 입력기에 포커스가 가고 Esc로 닫는다.
  // 테스트 코드: DD-075
  it('opens the editor with the keyboard (Enter and Space) and focuses the input', async () => {
    // given: sales 사용자
    const { user } = await openDeal(1, '한빛은행 ITDR 도입')
    screen.getByRole('button', { name: 'Vendor 수정' }).focus()

    // when: Vendor 버튼에서 Enter를 누른다
    await user.keyboard('{Enter}')
    // then: 입력기에 포커스가 간다
    expect(screen.getByRole('combobox', { name: 'Vendor' })).toHaveFocus()
    // when: Esc를 누른다
    await user.keyboard('{Escape}')
    // then: Vendor 편집이 닫힌다
    expect(screen.queryByRole('combobox', { name: 'Vendor' })).not.toBeInTheDocument()
    // when: Product 버튼에서 Space를 누른다
    screen.getByRole('button', { name: 'Product 수정' }).focus()
    await user.keyboard(' ')
    // then: Product 입력기에 포커스가 간다
    expect(screen.getByLabelText('Product')).toHaveFocus()
  })

  // Deal 이름을 Enter로 저장하면 제목이 바뀌고 성공 알림이 보인다.
  // 테스트 코드: DD-075
  it('saves the deal name with Enter and shows the success notice', async () => {
    // given: sales 사용자
    const { user } = await openDeal(1, '한빛은행 ITDR 도입')
    await user.click(screen.getByTitle('Deal 이름 수정'))
    const input = screen.getByLabelText('Deal 이름')

    // when: 이름 편집에 새 이름을 입력하고 Enter를 누른다
    await user.clear(input)
    await user.type(input, '한빛은행 ITDR 확장{Enter}')

    // then: 제목이 새 이름이고 'Deal 이름이 변경되었습니다.'가 보인다
    expect(await screen.findByRole('heading', { level: 1, name: '한빛은행 ITDR 확장' })).toBeVisible()
    expect(await screen.findByText('Deal 이름이 변경되었습니다.')).toBeVisible()
  })

  // Esc는 입력을 버리고 원래 값을 보이며 저장·취소 버튼은 없다.
  // 테스트 코드: DD-076
  it('discards the typed value with Escape and shows the original value (no buttons)', async () => {
    // given: 구매절차가 '조달청 경쟁 입찰'인 Deal
    const { user } = await openDeal(1, '한빛은행 ITDR 도입')

    // when: 구매절차에 글자를 입력하고 Esc를 누른다
    await user.click(screen.getByRole('button', { name: '구매절차 수정' }))
    await user.type(screen.getByLabelText('구매절차'), '추가{Escape}')

    // then: 편집이 닫히고 원래 값이 보이며 저장·취소 버튼이 없다
    expect(screen.queryByLabelText('구매절차')).not.toBeInTheDocument()
    expect(screen.getByRole('button', { name: '구매절차 수정' })).toHaveTextContent('조달청 경쟁 입찰')

    expect(screen.queryByRole('button', { name: /(저장|편집 취소)$/ })).not.toBeInTheDocument()
  })

  // 입력형은 포커스가 나가면 바뀐 값을 저장하고 그대로면 요청 없이 닫는다.
  // 테스트 코드: DD-077
  it('saves a typed value when focus leaves the input, and does nothing when it is unchanged', async () => {
    // given: 구매절차 편집을 연 sales
    const { user } = await openDeal(1, '한빛은행 ITDR 도입')

    // when: 글자를 더한 뒤 Tab으로 나간다
    await user.click(screen.getByRole('button', { name: '구매절차 수정' }))
    await user.type(screen.getByLabelText('구매절차'), ' 추가')
    expect(screen.queryByRole('button', { name: /(저장|편집 취소)$/ })).not.toBeInTheDocument()
    await user.tab()
    // then: 저장 알림과 새 값이 보인다
    await waitFor(() => expect(screen.getByRole('button', { name: '구매절차 수정' })).toHaveTextContent('조달청 경쟁 입찰 추가'))
    expect(await screen.findByText('구매절차가 변경되었습니다.')).toBeVisible()

    // when: 다시 열어 그대로 Tab으로 나간다
    await user.click(screen.getByRole('button', { name: '구매절차 수정' }))
    await user.tab()
    // then: 아무 일 없이 닫힌다
    expect(screen.getByRole('button', { name: '구매절차 수정' })).toBeVisible()
    expect(screen.queryByLabelText('구매절차')).not.toBeInTheDocument()
  })

  // 화면 검증이 실패하면 오류 문구를 보이고 편집을 유지한다.
  // 테스트 코드: DD-078
  it('keeps the editor open with the message when validation fails on Enter', async () => {
    // given: Deal 이름 편집을 연 sales
    const { user } = await openDeal(1, '한빛은행 ITDR 도입')

    // when: 이름을 비우고 Enter를 누른다
    await user.click(screen.getByTitle('Deal 이름 수정'))
    await user.clear(screen.getByLabelText('Deal 이름'))
    await user.keyboard('{Enter}')

    // then: 'Deal Name을 입력하세요.' 알림이 보이고 입력이 그대로 열려 있다
    expect(await screen.findByRole('alert')).toHaveTextContent('Deal Name을 입력하세요.')
    expect(screen.getByLabelText('Deal 이름')).toBeVisible()
  })
})

describe('Owner · Vendor · Product · Users count · 견적 · POC · 구매절차', () => {
  // Owner 후보는 재직 sales뿐이라 퇴사자·user는 없고 고르면 바뀌며 이력에 남는다.
  // 테스트 코드: DD-079
  it('lets the writer pick another sales owner and never offers the resigned one', async () => {
    // given: sales 사용자
    const { user } = await openDeal(1, '한빛은행 ITDR 도입')

    // when: Owner를 누른다
    await user.click(screen.getByRole('button', { name: 'Owner 수정' }))
    const select = screen.getByLabelText('Owner')
    // then: 퇴사자·user 옵션이 없다
    expect(within(select).queryByRole('option', { name: '강퇴사(퇴사)' })).not.toBeInTheDocument()
    expect(within(select).queryByRole('option', { name: '한조회' })).not.toBeInTheDocument()
    // when: 박영업을 고른다
    await user.selectOptions(select, '박영업')
    // then: Owner가 바뀐다
    await waitFor(() => expect(screen.getByRole('button', { name: 'Owner 수정' })).toHaveTextContent('박영업'))
    // when: Deal History 탭을 연다
    await user.click(screen.getByRole('tab', { name: 'Deal History' }))
    // then: Owner 이력이 있다
    expect(await screen.findByRole('cell', { name: 'Owner' })).toBeVisible()
  })

  // Vendor는 선택 상자, Product는 자유 입력으로 고친다.
  // 테스트 코드: DD-080
  it('edits Vendor with a select and Product as a free text input', async () => {
    // given: sales 사용자
    const { user } = await openDeal(1, '한빛은행 ITDR 도입')

    // when: Vendor 편집을 연다
    await user.click(screen.getByRole('button', { name: 'Vendor 수정' }))
    // then: Vendor는 select다
    expect(screen.getByRole('combobox', { name: 'Vendor' }).tagName).toBe('SELECT')
    expect(screen.queryByRole('listbox', { name: 'Vendor' })).not.toBeInTheDocument()
    // when: Vendor 편집을 닫고 Product 편집을 연다
    await user.keyboard('{Escape}')
    await user.click(screen.getByRole('button', { name: 'Product 수정' }))
    // then: Product는 현재 값이 든 input이다
    expect(screen.getByLabelText('Product').tagName).toBe('INPUT')
    expect(screen.queryByRole('combobox', { name: 'Product' })).not.toBeInTheDocument()
    expect(screen.getByLabelText('Product')).toHaveValue('ITDR')
  })

  // 빈 Product는 문구 없이 저장하고 '—'로 보이며, Esc는 값을 되돌리지 않는다.
  // 테스트 코드: DD-080
  it('saves an empty Product without a message and shows a dash', async () => {
    // given: Product가 ITDR인 Deal
    const update = vi.spyOn(gateway.deals, 'update')
    const { user } = await openDeal(1, '한빛은행 ITDR 도입')
    await user.click(screen.getByRole('button', { name: 'Product 수정' }))
    const product = screen.getByLabelText('Product')

    // when: Product를 공백만으로 바꿔 Enter를 누른다
    await user.clear(product)
    await user.type(product, '   {Enter}')

    // then: 'Product를 입력하세요.'가 없고 product ''만 보내며 값이 '—'로 보인다
    expect(await screen.findByText('Product가 변경되었습니다.')).toBeVisible()
    expect(screen.queryByText('Product를 입력하세요.')).not.toBeInTheDocument()
    expect(update).toHaveBeenCalledWith(expect.any(String), { product: '' })
    await waitFor(() => expect(screen.getByRole('button', { name: 'Product 수정' })).toHaveTextContent('—'))
  })

  // Users count는 0 이상 정수만 저장한다.
  // 테스트 코드: DD-081
  it('saves Users count as a non-negative integer', async () => {
    // given: sales 사용자
    const { user } = await openDeal(1, '한빛은행 ITDR 도입')
    await user.click(screen.getByRole('button', { name: 'Users count 수정' }))
    const users = screen.getByLabelText('Users count')

    // when: -1을 입력해 Enter를 누른다
    await user.clear(users)
    await user.type(users, '-1{Enter}')
    // then: 문구로 막힌다
    expect(await screen.findByRole('alert')).toHaveTextContent('Users count는 0 이상의 정수로 입력하세요.')
    // when: 2500을 입력해 Enter를 누른다
    await user.clear(users)
    await user.type(users, '2500{Enter}')
    // then: 저장되어 보인다
    await waitFor(() => expect(screen.getByRole('button', { name: 'Users count 수정' })).toHaveTextContent('2500'))
  })

  // 빈 Users count는 요청 없이 문구로 막는다.
  // 테스트 코드: DD-081
  it('does not save an empty Users count and keeps the shown value', async () => {
    // given: sales 사용자
    const update = vi.spyOn(gateway.deals, 'update')
    const { user } = await openDeal(1, '한빛은행 ITDR 도입')
    const shown = screen.getByRole('button', { name: 'Users count 수정' }).textContent
    await user.click(screen.getByRole('button', { name: 'Users count 수정' }))
    const users = screen.getByLabelText('Users count')

    // when: Users count를 비우고 Enter를 누른다
    await user.clear(users)
    await user.type(users, '{Enter}')

    // then: 'Users count를 입력하세요.'가 보이고 요청이 없으며 값이 그대로다
    expect(await screen.findByRole('alert')).toHaveTextContent('Users count를 입력하세요.')
    expect(update).not.toHaveBeenCalled()
    // when: Esc를 누른다
    await user.keyboard('{Escape}')
    // then: 값이 그대로다
    expect(screen.getByRole('button', { name: 'Users count 수정' })).toHaveTextContent(shown ?? '')
  })

  // Users count 0도 저장되어 0으로 보인다.
  // 테스트 코드: DD-081
  it('saves Users count of zero and shows it as 0', async () => {
    // given: sales 사용자
    const { user } = await openDeal(1, '한빛은행 ITDR 도입')
    await user.click(screen.getByRole('button', { name: 'Users count 수정' }))
    const users = screen.getByLabelText('Users count')

    // when: Users count에 0을 입력해 Enter를 누른다
    await user.clear(users)
    await user.type(users, '0{Enter}')

    // then: 값이 0으로 보인다
    await waitFor(() => expect(screen.getByRole('button', { name: 'Users count 수정' })).toHaveTextContent(/^0$/))
  })

  // 견적 제출여부, POC 여부·완료일, 구매절차를 각각 그 자리에서 고친다.
  // 테스트 코드: DD-082
  it('edits the quote, the POC and the procurement in place', async () => {
    // given: sales 사용자
    const { user } = await openDeal(1, '한빛은행 ITDR 도입')

    // when: 견적 제출여부를 NO로 고친다
    await user.click(screen.getByRole('button', { name: '견적 제출여부 수정' }))
    await user.selectOptions(screen.getByLabelText('견적 제출여부'), 'NO')
    // then: '미제출'로 보인다
    await waitFor(() => expect(screen.getByRole('button', { name: '견적 제출여부 수정' })).toHaveTextContent('미제출'))

    // when: POC 여부를 ING로 고친다
    await user.click(screen.getByRole('button', { name: 'POC 여부 수정' }))
    await user.selectOptions(screen.getByLabelText('POC 여부'), 'ING')
    // then: 'ING'로 보인다
    await waitFor(() => expect(screen.getByRole('button', { name: 'POC 여부 수정' })).toHaveTextContent('ING'))

    // when: POC 완료일을 고친다
    await user.click(screen.getByRole('button', { name: 'POC 완료일 수정' }))
    const date = screen.getByLabelText('POC 완료일')
    await user.clear(date)
    await user.type(date, '2026-12-01{Enter}')
    // then: 새 날짜로 보인다
    await waitFor(() => expect(screen.getByRole('button', { name: 'POC 완료일 수정' })).toHaveTextContent('2026-12-01'))

    // when: 구매절차를 고친다
    await user.click(screen.getByRole('button', { name: '구매절차 수정' }))
    const procurement = screen.getByLabelText('구매절차')
    await user.clear(procurement)
    await user.type(procurement, '수의계약{Enter}')
    // then: 새 구매절차로 보인다
    await waitFor(() => expect(screen.getByRole('button', { name: '구매절차 수정' })).toHaveTextContent('수의계약'))
  })
})

describe('BANT Label 인라인 편집', () => {
  async function openBant(no: number, title: string, role?: TestRole) {
    const view = await openDeal(no, title, role)
    return { ...view, bant: screen.getByRole('region', { name: 'BANT' }) }
  }
  const currentLabels = async () => (await gateway.labels.list()).length

  // BANT 값을 누르면 현재 Label이 든 자동완성 입력이 열리고 '새 Label' 항목은 없다.
  // 테스트 코드: DD-084
  it('opens an autocomplete text input with the current label and has no new-label option', async () => {
    // given: Timeline이 '금년 구매'인 Deal
    const { user, bant } = await openBant(1, '한빛은행 ITDR 도입')


    // when: Timeline을 누른다
    await user.click(within(bant).getByRole('button', { name: 'Timeline 수정' }))
    const input = within(bant).getByRole('combobox', { name: 'Timeline' })

    // then: 현재 Label이 든 input이 열리고 '새 Label 만들기' 항목이 없다
    expect(input.tagName).toBe('INPUT')
    expect(input).toHaveDisplayValue('금년 구매')
    expect(within(bant).queryByRole('option', { name: /새 Label 만들기/ })).not.toBeInTheDocument()
    expect(within(bant).queryByLabelText(/새 Label 이름/)).not.toBeInTheDocument()
  })

  // 자동완성 후보는 그 구분의 Label뿐이다.
  // 테스트 코드: DD-084
  it('lists only the labels of that category', async () => {
    // given: 대한제조 MFA 확대 Deal
    const { user, bant } = await openBant(2, '대한제조 MFA 확대')


    // when: Need 입력을 비워 후보를 연다
    await user.click(within(bant).getByRole('button', { name: 'Need 수정' }))
    await user.clear(within(bant).getByRole('combobox', { name: 'Need' }))
    const names = within(screen.getByRole('listbox', { name: 'Need' }))
      .getAllByRole('option')
      .map((o) => o.textContent)

    // then: 후보가 Need 구분 Label뿐이다
    expect(names).toEqual(['보안 사고 발생', 'CISO 지시', '보안 강화 요건', '컴플라이언스', '모름'])
  })

  // 후보를 고르면 즉시 저장되고 알림·이력이 남는다.
  // 테스트 코드: DD-084
  it('saves a picked candidate at once, shows the notice and records the history', async () => {
    // given: 대한제조 MFA 확대 Deal
    const update = vi.spyOn(gateway.deals, 'update')
    const { user, bant } = await openBant(2, '대한제조 MFA 확대')
    const need = (await gateway.labels.list()).find((l) => l.category === 'need' && l.name === '컴플라이언스')

    // when: Need 후보 '컴플라이언스'를 고른다
    await user.click(within(bant).getByRole('button', { name: 'Need 수정' }))
    await user.click(within(bant).getByRole('combobox', { name: 'Need' }))
    await user.click(await screen.findByRole('option', { name: '컴플라이언스' }))

    // then: id로 저장되고 'BANT Need Label이 변경되었습니다.' 알림과 BANT 이력이 보인다
    await waitFor(() => expect(within(bant).getByRole('button', { name: 'Need 수정' })).toHaveTextContent('컴플라이언스'))
    expect(await screen.findByText('BANT Need Label이 변경되었습니다.')).toBeVisible()
    expect(update.mock.calls[0]?.[1].bant?.need).toEqual({ id: need?.id })
    // when: Deal History 탭을 연다
    await user.click(screen.getByRole('tab', { name: 'Deal History' }))
    // then: BANT 이력이 보인다
    expect(await screen.findByRole('cell', { name: 'BANT Label: Need' })).toBeVisible()
  })

  // 새 이름을 입력하고 Enter로 저장하면 그 구분에 새 Label이 만들어진다.
  // 테스트 코드: DD-085
  it('saves a typed new label with Enter, creating it in that category', async () => {
    // given: 대한제조 MFA 확대 Deal
    const update = vi.spyOn(gateway.deals, 'update')
    const { user, bant } = await openBant(2, '대한제조 MFA 확대')
    const before = await currentLabels()

    // when: Need에 '신규 요건'을 입력하고 Enter를 누른다
    await user.click(within(bant).getByRole('button', { name: 'Need 수정' }))
    await user.type(within(bant).getByRole('combobox', { name: 'Need' }), '신규 요건{Enter}')

    // then: 이름으로 저장되고 Label이 하나 늘며 Need 구분의 직접 만든 Label이다
    await waitFor(() => expect(within(bant).getByRole('button', { name: 'Need 수정' })).toHaveTextContent('신규 요건'))
    expect(update.mock.calls[0]?.[1].bant?.need).toEqual({ name: '신규 요건' })
    expect(await currentLabels()).toBe(before + 1)
    expect((await gateway.labels.list()).find((l) => l.name === '신규 요건')).toMatchObject({ category: 'need', isDefault: false })
  })

  // 새 이름 입력 뒤 포커스가 나가도 저장된다.
  // 테스트 코드: DD-085
  it('saves a typed new label when the focus leaves the input', async () => {
    // given: 대한제조 MFA 확대 Deal
    const { user, bant } = await openBant(2, '대한제조 MFA 확대')

    await user.click(within(bant).getByRole('button', { name: 'Timeline 수정' }))
    const input = within(bant).getByRole('combobox', { name: 'Timeline' })

    // when: Timeline에 새 이름을 입력하고 Tab으로 나간다
    await user.clear(input)
    await user.type(input, '내후년 구매 검토')
    await user.tab()

    // then: 새 이름이 Timeline 값으로 보인다
    await waitFor(() => expect(within(bant).getByRole('button', { name: 'Timeline 수정' })).toHaveTextContent('내후년 구매 검토'))
  })

  // 입력한 이름이 기존 Label과 같으면 새로 만들지 않고 그 id를 쓴다.
  // 테스트 코드: DD-085
  it('uses the existing label, not a new one, when the typed name equals it', async () => {
    // given: 대한제조 MFA 확대 Deal
    const update = vi.spyOn(gateway.deals, 'update')
    const { user, bant } = await openBant(2, '대한제조 MFA 확대')
    const before = await currentLabels()
    const budget = (await gateway.labels.list()).find((l) => l.category === 'budget' && l.name === '단독 예산 확보')


    // when: Budget에 기존 이름을 앞뒤 공백과 함께 입력하고 Enter를 누른다
    await user.click(within(bant).getByRole('button', { name: 'Budget 수정' }))
    const input = within(bant).getByRole('combobox', { name: 'Budget' })
    await user.clear(input)
    await user.type(input, ' 단독 예산 확보 {Enter}')

    // then: 기존 Label id로 저장되고 Label 수가 그대로다
    await waitFor(() => expect(within(bant).getByRole('button', { name: 'Budget 수정' })).toHaveTextContent('단독 예산 확보'))
    expect(update.mock.calls[0]?.[1].bant?.budget).toEqual({ id: budget?.id })
    expect(await currentLabels()).toBe(before)
  })

  // 하나를 바꿔도 요청은 네 구분을 모두 보내고 다른 구분은 현재 선택 그대로다.
  // 테스트 코드: DD-086
  it('sends the other categories as they are, so only one category changes', async () => {
    // given: 네 구분이 모두 선택된 Deal
    const update = vi.spyOn(gateway.deals, 'update')
    const { user, bant } = await openBant(1, '한빛은행 ITDR 도입')
    const labels = await gateway.labels.list()
    const idOf = (category: string, name: string) => labels.find((l) => l.category === category && l.name === name)?.id

    // when: Need를 비우고 Enter를 누른다
    await user.click(within(bant).getByRole('button', { name: 'Need 수정' }))
    await user.clear(within(bant).getByRole('combobox', { name: 'Need' }))
    await user.keyboard('{Enter}')

    // then: bant 요청이 Need만 null이고 나머지는 현재 id다
    await waitFor(() => expect(update).toHaveBeenCalledTimes(1))
    expect(update.mock.calls[0]?.[1].bant).toEqual({
      budget: { id: idOf('budget', '단독 예산 확보') },
      authority: { id: idOf('authority', 'CISO 보고 완료') },
      need: null,
      timeline: { id: idOf('timeline', '금년 구매') },
    })
  })

  // 입력을 비우고 확정하면 선택 안 함이 된다.
  // 테스트 코드: DD-086
  it('clears to not selected when the input is emptied and confirmed', async () => {
    // given: Timeline이 선택된 Deal
    const update = vi.spyOn(gateway.deals, 'update')
    const { user, bant } = await openBant(1, '한빛은행 ITDR 도입')

    // when: Timeline 입력을 비우고 Enter를 누른다
    await user.click(within(bant).getByRole('button', { name: 'Timeline 수정' }))
    await user.clear(within(bant).getByRole('combobox', { name: 'Timeline' }))
    await user.keyboard('{Enter}')

    // then: 값이 '—'이고 요청의 timeline이 null이다
    await waitFor(() => expect(within(bant).getByRole('button', { name: 'Timeline 수정' })).toHaveTextContent('—'))
    expect(update.mock.calls[0]?.[1].bant?.timeline).toBeNull()
  })

  // 선택이 그대로면 요청도 알림도 없다.
  // 테스트 코드: DD-086
  it('sends nothing when the value stays the same', async () => {
    // given: Timeline이 '금년 구매'인 Deal
    const update = vi.spyOn(gateway.deals, 'update')
    const { user, bant } = await openBant(1, '한빛은행 ITDR 도입')

    // when: 열었다 Enter로 닫는다
    await user.click(within(bant).getByRole('button', { name: 'Timeline 수정' }))
    await user.keyboard('{Enter}')
    // when: 다시 열어 같은 후보를 고른다
    await user.click(within(bant).getByRole('button', { name: 'Timeline 수정' }))
    await user.click(within(bant).getByRole('combobox', { name: 'Timeline' }))
    await user.click(await screen.findByRole('option', { name: '금년 구매' }))

    // then: 수정 요청이 없고 알림도 없다
    await waitFor(() => expect(within(bant).queryByRole('combobox', { name: 'Timeline' })).not.toBeInTheDocument())
    expect(update).not.toHaveBeenCalled()
    expect(screen.queryByText('BANT Timeline Label이 변경되었습니다.')).not.toBeInTheDocument()
  })

  // 51자 이름은 서버 문구를 보이고 편집을 유지한다.
  // 테스트 코드: DD-078
  it('shows the server message for a name over 50 characters and keeps the editor open', async () => {
    // given: 대한제조 MFA 확대 Deal
    const { user, bant } = await openBant(2, '대한제조 MFA 확대')

    // when: Need에 51자 이름을 넣고 Enter를 누른다
    await user.click(within(bant).getByRole('button', { name: 'Need 수정' }))
    fireEvent.change(within(bant).getByRole('combobox', { name: 'Need' }), { target: { value: 'x'.repeat(51) } })
    await user.keyboard('{Enter}')

    // then: 'Label 이름은 50자 이내로 입력하세요.' 알림이 보이고 입력이 열려 있다
    expect(await within(bant).findByRole('alert')).toHaveTextContent('Label 이름은 50자 이내로 입력하세요.')
    expect(within(bant).getByRole('combobox', { name: 'Need' })).toBeVisible()
  })

  // user에게는 BANT 편집이 없다.
  // 테스트 코드: DD-073
  it('does not offer the editor to a viewer', async () => {
    // when: Deal 상세를 연다 (전제: user 역할 사용자)
    const { bant } = await openBant(1, '한빛은행 ITDR 도입', 'user')

    // then: BANT 카드에 수정 버튼이 없고 값만 보인다
    expect(within(bant).queryByRole('button', { name: /수정$/ })).not.toBeInTheDocument()
    expect(within(bant).getByText('단독 예산 확보')).toBeVisible()
  })
})
