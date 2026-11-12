import { defaultMock } from '../../../test/fake/default'
import { cleanup, screen, waitFor, within } from '@testing-library/react'
import { describe, expect, it } from 'vitest'
import { gateway } from '../../../gateway'
import { renderAt } from '../../../test/mockApp'
import { detailPath } from '../../../test/detailTestUtils'
import { USER_ID } from '../../../test/fake/seed/ids'

async function openDeal(no: number, title: string) {
  const view = await renderAt(await detailPath(no))
  await screen.findByRole('heading', { level: 1, name: title })
  return view
}

const customerCard = () => screen.getByRole('region', { name: '고객' })
const partnerCard = () => screen.getByRole('region', { name: '파트너' })

function valueOf(card: HTMLElement, label: string): string {
  return within(card).getByRole('button', { name: label }).textContent ?? ''
}

describe('고객사 인라인 편집 (회사명 pulldown + 자동완성)', () => {
  // 고객 회사명을 누르면 회사 목록이 열리고 부분·대소문자 무시 글자로 걸러진다.
  // 테스트 코드: DD-087
  it('opens the company list on click and filters it by partial, case-insensitive text', async () => {
    // given: 고객 한빛은행 Deal
    const { user } = await openDeal(1, '한빛은행 ITDR 도입')
    await defaultMock.signInAs(USER_ID.root) // 연락처 직접 등록은 admin만 가능하다.
    await gateway.contacts.create('customer', { company: 'Acme', name: 'Kim', title: '', email: null, phone: null })
    await defaultMock.signInAs(USER_ID.kim)

    // when: 회사명 버튼을 누른다
    await user.click(within(customerCard()).getByRole('button', { name: '고객 회사명 수정' }))
    const company = within(customerCard()).getByRole('combobox', { name: '고객 회사명' })

    // then: 회사 목록이 열려 고객사만 보인다
    expect(company).toHaveFocus()
    const all = await screen.findByRole('listbox', { name: '고객 회사명' })
    const names = within(all).getAllByRole('option').map((o) => o.textContent)
    expect(names).toEqual(expect.arrayContaining(['한빛은행', '누리통신', '하늘카드', 'Acme']))
    expect(names).not.toContain('에이원시스템')

    // when: '하'를 입력한다
    await user.clear(company)
    await user.type(company, '하')
    // then: '하늘카드'로 걸러진다
    expect(within(await screen.findByRole('listbox', { name: '고객 회사명' })).getAllByRole('option').map((o) => o.textContent)).toEqual(['하늘카드'])
    // when: 'aCM'을 입력한다
    await user.clear(company)
    await user.type(company, 'aCM')
    // then: 대소문자 무시로 'Acme'가 걸러진다
    expect(within(await screen.findByRole('listbox', { name: '고객 회사명' })).getAllByRole('option').map((o) => o.textContent)).toEqual(['Acme'])
  })

  // 다른 기존 회사를 고르면 담당자가 비고 담당자 목록이 열리며, 담당자를 고르면 연락 정보가 채워져 저장된다.
  // 테스트 코드: DD-087
  it('clears the person and opens the person list when another existing company is picked, then fills the contact info', async () => {
    // given: 고객 한빛은행 Deal
    const { user } = await openDeal(1, '한빛은행 ITDR 도입')

    // when: 회사 하늘카드를 고른다
    await user.click(within(customerCard()).getByRole('button', { name: '고객 회사명 수정' }))
    await user.click(await screen.findByRole('option', { name: '하늘카드' }))
    const person = within(customerCard()).getByRole('combobox', { name: '고객 담당자명' })

    // then: 담당자·직급이 비고 담당자 목록이 열린다
    expect(person).toHaveValue('')
    expect(person).toHaveFocus()
    expect(within(customerCard()).getByLabelText('고객 직급')).toHaveValue('')
    const list = await screen.findByRole('listbox', { name: '고객 담당자명' })
    expect(within(list).getAllByRole('option').map((o) => o.textContent)).toEqual([
      expect.stringContaining('신동혁'),
      expect.stringContaining('윤소라'),
    ])
    expect(within(customerCard()).queryByText(/신규 고객사입니다/)).not.toBeInTheDocument()

    // when: '윤'을 입력한다
    await user.type(person, '윤')
    // then: 후보가 하나로 걸러진다
    expect(within(await screen.findByRole('listbox', { name: '고객 담당자명' })).getAllByRole('option')).toHaveLength(1)
    // when: 담당자 윤소라를 고른다 (후보를 고르는 순간 반영되고 저장 버튼은 없다)
    await user.click(await screen.findByRole('option', { name: /윤소라/ }))
    // then: 연락 정보가 채워지고 '고객 연락처가 저장되었습니다.'가 보인다
    await waitFor(() => expect(valueOf(customerCard(), '고객 회사명 수정')).toBe('하늘카드'))
    expect(valueOf(customerCard(), '고객 담당자명 수정')).toBe('윤소라')
    expect(valueOf(customerCard(), '고객 직급 수정')).toBe('과장')
    expect(valueOf(customerCard(), '고객 이메일 수정')).toBe('yoon@haneul.test')
    expect(valueOf(customerCard(), '고객 전화 수정')).toBe('010-9999-0000')
    expect(await screen.findByText('고객 연락처가 저장되었습니다.')).toBeVisible()

    // when: Deal History 탭을 연다
    await user.click(screen.getByRole('tab', { name: 'Deal History' }))
    // then: 고객 연락처 이력 행에 하늘카드·윤소라가 있다
    const row = (await screen.findAllByRole('row')).find((r) => within(r).queryByRole('cell', { name: '고객 연락처' }))
    expect(row).toBeDefined()
    expect(row).toHaveTextContent('하늘카드')
    expect(row).toHaveTextContent('윤소라')
  })

  // 목록에 없는 회사는 신규로 안내하고 담당자 정보를 비우며 담당자명이 필요하다.
  // 테스트 코드: DD-088
  it('treats a typed unknown company as new: clears every contact field, explains it and needs a person name', async () => {
    // given: 고객 한빛은행 Deal
    const { user } = await openDeal(1, '한빛은행 ITDR 도입')
    await user.click(within(customerCard()).getByRole('button', { name: '고객 회사명 수정' }))
    const company = within(customerCard()).getByRole('combobox', { name: '고객 회사명' })

    // when: 없는 회사명 '신규상사'를 입력한다
    await user.clear(company)
    await user.type(company, '신규상사')

    // then: 신규 안내가 보이고 모든 칸이 빈다
    expect(within(customerCard()).getByText('신규 고객사입니다. 담당자 정보를 입력하세요.')).toBeVisible()
    for (const label of ['고객 담당자명', '고객 직급', '고객 이메일', '고객 전화'])
      expect(within(customerCard()).getByLabelText(label)).toHaveValue('')
    expect(within(customerCard()).queryByRole('button', { name: /연락처 (저장|편집 취소)$/ })).not.toBeInTheDocument()

    // when: 담당자명 없이 Enter로 확정한다
    await user.click(within(customerCard()).getByRole('combobox', { name: '고객 담당자명' }))
    await user.keyboard('{Enter}')
    // then: 저장되지 않고 '담당자명을 입력하세요.' 오류와 함께 편집이 유지된다
    expect(await within(customerCard()).findByText('담당자명을 입력하세요.')).toBeVisible()
    expect(within(customerCard()).getByRole('combobox', { name: '고객 회사명' })).toHaveValue('신규상사')

    // when: 담당자 '홍길동'과 직급 '이사'를 입력하고 Enter를 누른다
    await user.type(within(customerCard()).getByRole('combobox', { name: '고객 담당자명' }), '홍길동')
    await user.type(within(customerCard()).getByLabelText('고객 직급'), '이사{Enter}')
    // then: 신규 회사·담당자·직급이 저장된다
    await waitFor(() => expect(valueOf(customerCard(), '고객 회사명 수정')).toBe('신규상사'))
    expect(valueOf(customerCard(), '고객 담당자명 수정')).toBe('홍길동')
    expect(valueOf(customerCard(), '고객 직급 수정')).toBe('이사')
    expect(valueOf(customerCard(), '고객 이메일 수정')).toBe('—')
  })

  // Esc로 연락처 편집 전체를 버리면 이전 연락처가 남는다.
  // 테스트 코드: DD-089
  it('discards the whole contact edit with Escape and keeps the old contact', async () => {
    // given: 회사명을 다른 글자로 바꾸는 중인 편집 세션
    const { user } = await openDeal(1, '한빛은행 ITDR 도입')

    await user.click(within(customerCard()).getByRole('button', { name: '고객 회사명 수정' }))
    await user.clear(within(customerCard()).getByRole('combobox', { name: '고객 회사명' }))
    await user.type(within(customerCard()).getByRole('combobox', { name: '고객 회사명' }), '다른회사')

    // when: Esc를 두 번 누른다
    await user.keyboard('{Escape}{Escape}')

    // then: 회사·담당자가 원래 값이다
    expect(valueOf(customerCard(), '고객 회사명 수정')).toBe('한빛은행')
    expect(valueOf(customerCard(), '고객 담당자명 수정')).toBe('정민수')
  })

  // 회사명·이메일에는 공백을 입력할 수 없고 안내가 나온다.
  // 테스트 코드: DD-090
  it('blocks spaces in company, person, email and phone and tells the user', async () => {
    // given: 고객 연락처 편집을 연 sales
    const { user } = await openDeal(1, '한빛은행 ITDR 도입')
    await user.click(within(customerCard()).getByRole('button', { name: '고객 회사명 수정' }))
    const company = within(customerCard()).getByRole('combobox', { name: '고객 회사명' })

    // when: 회사명에 '신 규'를 입력한다
    await user.clear(company)
    await user.type(company, '신 규')
    // then: 공백이 지워진 값이 되고 '공백은 입력할 수 없습니다.'가 보인다
    expect(company).toHaveValue('신규')
    expect(within(customerCard()).getByText('공백은 입력할 수 없습니다.')).toBeVisible()

    // when: 편집을 버리고 이메일에 'a b@x.kr'을 입력한다
    await user.keyboard('{Escape}{Escape}')
    await user.click(within(customerCard()).getByRole('button', { name: '고객 이메일 수정' }))
    const email = within(customerCard()).getByLabelText('고객 이메일')
    await user.clear(email)
    await user.type(email, 'a b@x.kr')
    // then: 공백이 지워진 값이 되고 안내가 보인다
    expect(email).toHaveValue('ab@x.kr')
    expect(within(customerCard()).getByText('공백은 입력할 수 없습니다.')).toBeVisible()
  })
})

describe('담당자 · 직급 · 이메일 · 전화 단일 필드 편집', () => {
  // 같은 회사의 다른 담당자를 목록에서 고르면 연락 정보가 채워진다.
  // 테스트 코드: DD-091
  it('picks another existing person of the same company from the list and fills the contact info', async () => {
    // given: 고객 한빛은행 Deal
    const { user } = await openDeal(1, '한빛은행 ITDR 도입')

    // when: 담당자명을 누른다
    await user.click(within(customerCard()).getByRole('button', { name: '고객 담당자명 수정' }))
    const list = await screen.findByRole('listbox', { name: '고객 담당자명' })

    // then: 같은 회사의 담당자 3명이 후보로 열린다
    expect(within(list).getAllByRole('option')).toHaveLength(3)
    // when: '오'로 걸러 '오지현'을 고른다
    await user.clear(within(customerCard()).getByRole('combobox', { name: '고객 담당자명' }))
    await user.type(within(customerCard()).getByRole('combobox', { name: '고객 담당자명' }), '오')
    await user.click(await screen.findByRole('option', { name: /오지현/ }))
    // then: 담당자·직급·이메일이 그 사람 정보로 바뀌고 회사는 그대로다
    await waitFor(() => expect(valueOf(customerCard(), '고객 담당자명 수정')).toBe('오지현'))
    expect(valueOf(customerCard(), '고객 직급 수정')).toBe('차장')
    expect(valueOf(customerCard(), '고객 이메일 수정')).toBe('oh@hanbit.test')
    expect(valueOf(customerCard(), '고객 회사명 수정')).toBe('한빛은행')
  })

  // 같은 회사의 새 담당자를 입력하면 직급·이메일·전화가 빈 신규 담당자가 된다.
  // 테스트 코드: DD-091
  it('takes a typed new person of the same company with empty contact info', async () => {
    // given: 고객 한빛은행 Deal
    const { user } = await openDeal(1, '한빛은행 ITDR 도입')
    await user.click(within(customerCard()).getByRole('button', { name: '고객 담당자명 수정' }))
    const person = within(customerCard()).getByRole('combobox', { name: '고객 담당자명' })

    // when: 담당자명에 '신입담당'을 입력하고 Enter를 누른다
    await user.clear(person)
    await user.type(person, '신입담당{Enter}')

    // then: 담당자가 바뀌고 직급·이메일·전화는 '—'다
    await waitFor(() => expect(valueOf(customerCard(), '고객 담당자명 수정')).toBe('신입담당'))
    expect(valueOf(customerCard(), '고객 직급 수정')).toBe('—')
    expect(valueOf(customerCard(), '고객 이메일 수정')).toBe('—')
    expect(valueOf(customerCard(), '고객 전화 수정')).toBe('—')
  })

  // 직급·이메일·전화를 직접 고치고 틀린 이메일은 그 칸 문구로 막는다.
  // 테스트 코드: DD-092
  it('edits title, email and phone directly and rejects a bad email', async () => {
    // given: 고객 한빛은행 Deal
    const { user } = await openDeal(1, '한빛은행 ITDR 도입')

    // when: 직급을 '팀장'으로 고친다
    await user.click(within(customerCard()).getByRole('button', { name: '고객 직급 수정' }))
    const title = within(customerCard()).getByLabelText('고객 직급')
    await user.clear(title)
    await user.type(title, '팀장{Enter}')
    // then: 직급이 바뀌고 담당자는 그대로다
    await waitFor(() => expect(valueOf(customerCard(), '고객 직급 수정')).toBe('팀장'))
    expect(valueOf(customerCard(), '고객 담당자명 수정')).toBe('정민수')

    // when: 틀린 이메일을 넣는다
    await user.click(within(customerCard()).getByRole('button', { name: '고객 이메일 수정' }))
    const email = within(customerCard()).getByLabelText('고객 이메일')
    await user.clear(email)
    await user.type(email, 'not-an-email{Enter}')
    // then: 이메일 형식 오류가 보인다
    expect(await within(customerCard()).findByRole('alert')).toHaveTextContent('이메일 형식이 올바르지 않습니다.')
    // when: 맞는 이메일로 고친다
    await user.clear(email)
    await user.type(email, 'new@hanbit.test{Enter}')
    // then: 이메일이 저장된다
    await waitFor(() => expect(valueOf(customerCard(), '고객 이메일 수정')).toBe('new@hanbit.test'))

    // when: 전화를 비운다
    await user.click(within(customerCard()).getByRole('button', { name: '고객 전화 수정' }))
    await user.clear(within(customerCard()).getByLabelText('고객 전화'))
    await user.keyboard('{Enter}')
    // then: 전화는 '—'가 된다
    await waitFor(() => expect(valueOf(customerCard(), '고객 전화 수정')).toBe('—'))
  })

  // 여러 Deal이 쓰는 연락처를 고칠 때 함께 바뀐다고 안내한다.
  // 테스트 코드: DD-093
  it('tells that a shared contact is changed for every deal using it', async () => {
    // given: 같은 고객 연락처를 쓰는 Deal이 둘 이상
    const { user } = await openDeal(1, '한빛은행 ITDR 도입')
    const deals = (await gateway.deals.list({ limit: 100 })).items
    let shared: { code: string; name: string } | null = null
    for (const deal of deals) {
      const rows = await gateway.contacts.byCompany('customer', deal.customer.company)
      if ((rows.find((r) => r.id === deal.customer.id)?.dealCount ?? 0) >= 2) {
        shared = deal
        break
      }
    }
    expect(shared).not.toBeNull()
    cleanup()
    await renderAt(`/deals/${shared?.code ?? ''}`)
    await screen.findByRole('heading', { level: 1, name: shared?.name ?? '' })

    // when: 고객 직급 편집을 연다
    await user.click(screen.getByRole('button', { name: '고객 직급 수정' }))

    // then: 'N개 Deal에서 함께 사용 중입니다. 수정하면 모두에 반영됩니다.'가 보인다
    expect(await screen.findByText(/개 Deal에서 함께 사용 중입니다. 수정하면 모두에 반영됩니다./)).toBeVisible()
  })
})

const PARTNER_EMPTY_LABELS = ['파트너 회사 입력', '파트너 담당자 입력', '파트너 직급 입력', '파트너 이메일 입력', '파트너 전화 입력']

describe('파트너 없음 상태 (BANT처럼 — 표시, 클릭해 바로 입력)', () => {
  // 파트너가 없으면 5행이 모두 '—' 버튼이고 '파트너 없음' 글자는 없다.
  // 테스트 코드: DD-094
  it('shows the same five rows as an existing partner, each value an em dash button, and no "파트너 없음" text', async () => {
    // given: 파트너가 없는 Deal
    await openDeal(5, '누리통신 NGFW 갱신')

    // when: Deal 상세를 연다
    const card = partnerCard()

    // then: 회사·담당자·직급·이메일·전화 5행이 '—' 클릭 버튼이고 '파트너 추가' 버튼도 없다
    expect(within(card).queryByText('파트너 없음')).not.toBeInTheDocument()
    expect(within(card).queryByRole('button', { name: '파트너 추가' })).not.toBeInTheDocument()
    for (const label of ['회사', '담당자', '직급', '이메일', '전화']) expect(within(card).getByText(label)).toBeVisible()
    for (const label of PARTNER_EMPTY_LABELS) {
      const button = within(card).getByRole('button', { name: label })
      expect(button).toHaveTextContent(/^—$/)
      expect(button).toHaveClass('dd-click')
    }
  })

  // 빈 파트너 값을 누르면 어느 것이든 회사명부터 추가 세션이 열린다.
  // 테스트 코드: DD-094
  it.each(PARTNER_EMPTY_LABELS)('opens the add-partner session starting at the company when "%s" is clicked', async (label) => {
    // given: 파트너가 없는 Deal
    const { user } = await openDeal(5, '누리통신 NGFW 갱신')

    // when: 5개 빈 값 중 하나를 누른다
    await user.click(within(partnerCard()).getByRole('button', { name: label }))

    // then: 회사명 입력에 포커스가 간다
    expect(within(partnerCard()).getByRole('combobox', { name: '파트너 회사명' })).toHaveFocus()
  })

  // 빈 값 어느 것에서든 파트너를 추가하면 '파트너가 추가되었습니다.'가 보인다.
  // 테스트 코드: DD-094
  it('adds a partner from any empty value and shows the added message', async () => {
    // given: 파트너가 없는 Deal
    const { user } = await openDeal(5, '누리통신 NGFW 갱신')

    // when: 이메일 빈 값을 눌러 새 회사·담당자를 입력하고 Enter를 누른다
    await user.click(within(partnerCard()).getByRole('button', { name: '파트너 이메일 입력' }))
    await user.type(within(partnerCard()).getByRole('combobox', { name: '파트너 회사명' }), '새파트너')
    await user.type(within(partnerCard()).getByRole('combobox', { name: '파트너 담당자명' }), '박파트')
    await user.tab()
    await user.keyboard('{Enter}')

    // then: 파트너 회사·담당자가 저장되고 추가 알림이 보인다
    await waitFor(() => expect(valueOf(partnerCard(), '파트너 회사명 수정')).toBe('새파트너'))
    expect(await screen.findByText('파트너가 추가되었습니다.')).toBeVisible()
    expect(valueOf(partnerCard(), '파트너 담당자명 수정')).toBe('박파트')
  })

  // user는 '—'만 보고 버튼이 없다.
  // 테스트 코드: DD-094
  it('shows only em dashes without any button for a read-only user', async () => {
    // given: 파트너가 없는 Deal과 user 역할
    await renderAt(await detailPath(5), { role: 'user' })
    await screen.findByRole('heading', { level: 1, name: '누리통신 NGFW 갱신' })

    // when: Deal 상세를 연다
    const card = partnerCard()

    // then: '—' 5개뿐이고 파트너 카드에 버튼이 없다
    expect(within(card).getAllByText('—')).toHaveLength(5)
    expect(within(card).queryByRole('button')).not.toBeInTheDocument()
    expect(within(card).queryByText('파트너 없음')).not.toBeInTheDocument()
  })
})

describe('파트너 인라인 편집', () => {
  // 파트너 회사명을 눌러 다른 기존 회사·담당자를 고르면 교체되고 이전 파트너 이력이 남는다.
  // 테스트 코드: DD-095
  it('replaces the partner by clicking the company and picking another existing company and person', async () => {
    // given: 활성 파트너가 있는 Deal
    const { user } = await openDeal(1, '한빛은행 ITDR 도입')

    // when: 회사명을 누른다
    await user.click(within(partnerCard()).getByRole('button', { name: '파트너 회사명 수정' }))
    // then: 비활성 안내가 보인다
    expect(within(partnerCard()).getByText(/이력으로 남고 비활성이 됩니다/)).toBeVisible()
    // when: 코어테크, 담당자 민지훈을 고른다
    await user.click(await screen.findByRole('option', { name: '코어테크' }))
    await user.click(await screen.findByRole('option', { name: /민지훈/ }))
    // then: 파트너가 교체되었다는 알림과 이전 파트너 이력이 보인다
    await waitFor(() => expect(valueOf(partnerCard(), '파트너 회사명 수정')).toBe('코어테크'))
    expect(await screen.findByText('파트너가 교체되었습니다.')).toBeVisible()
    expect(within(partnerCard()).getByText(/이전 파트너 이력/)).toBeVisible()
    // when: Deal History 탭을 연다
    await user.click(screen.getByRole('tab', { name: 'Deal History' }))
    // then: 파트너 변경 이력이 보인다
    expect(await screen.findByRole('cell', { name: '파트너' })).toBeVisible()
  })

  // 활성 파트너는 확인 대화상자를 거쳐야 제거된다.
  // 테스트 코드: DD-096
  it('removes the active partner only after a confirmation', async () => {
    // given: 활성 파트너가 있는 Deal
    const { user } = await openDeal(1, '한빛은행 ITDR 도입')

    // when: '파트너 제거'를 눌러 대화상자에서 취소한다
    await user.click(within(partnerCard()).getByRole('button', { name: '파트너 제거' }))
    const dialog = await screen.findByRole('dialog', { name: '파트너 제거' })
    await user.click(within(dialog).getByRole('button', { name: '취소' }))
    // then: 파트너가 그대로 남는다
    expect(within(partnerCard()).getByRole('button', { name: '파트너 회사명 수정' })).toBeVisible()
    // when: 다시 '파트너 제거'를 눌러 '제거'를 확인한다
    await user.click(within(partnerCard()).getByRole('button', { name: '파트너 제거' }))
    await user.click(within(await screen.findByRole('dialog', { name: '파트너 제거' })).getByRole('button', { name: '제거' }))
    // then: 5행이 '—'로 비고 '파트너 제거' 버튼이 없어진다
    await waitFor(() => expect(within(partnerCard()).getByRole('button', { name: '파트너 회사 입력' })).toHaveTextContent('—'))
    for (const label of PARTNER_EMPTY_LABELS) expect(within(partnerCard()).getByRole('button', { name: label })).toHaveTextContent('—')
    expect(within(partnerCard()).queryByText('파트너 없음')).not.toBeInTheDocument()
    expect(within(partnerCard()).queryByRole('button', { name: '파트너 제거' })).not.toBeInTheDocument()
  })

  // 파트너가 없는 Deal은 빈 값을 눌러 신규 파트너를 추가한다.
  // 테스트 코드: DD-094
  it('adds a partner to a deal that has none by clicking the empty value', async () => {
    // given: 파트너가 없는 Deal
    const { user } = await openDeal(5, '누리통신 NGFW 갱신')

    // when: '파트너 회사 입력'을 눌러 새 회사명을 입력한다
    await user.click(within(partnerCard()).getByRole('button', { name: '파트너 회사 입력' }))
    const company = within(partnerCard()).getByRole('combobox', { name: '파트너 회사명' })
    await user.type(company, '새파트너')
    // then: 신규 안내가 보인다
    expect(within(partnerCard()).getByText('신규 파트너입니다. 담당자 정보를 입력하세요.')).toBeVisible()
    // when: 담당자를 입력하고 Tab으로 직급 칸에 간다
    await user.type(within(partnerCard()).getByRole('combobox', { name: '파트너 담당자명' }), '박파트')
    await user.tab() // 포커스가 블록 안(직급)에 머물면 저장하지 않는다.
    // then: 포커스가 직급 칸에 있고 아직 저장되지 않는다
    expect(within(partnerCard()).getByLabelText('파트너 직급')).toHaveFocus()
    // when: 직급 칸에서 Enter를 누른다
    await user.keyboard('{Enter}')
    // then: 저장되어 추가 알림이 보인다
    await waitFor(() => expect(valueOf(partnerCard(), '파트너 회사명 수정')).toBe('새파트너'))
    expect(await screen.findByText('파트너가 추가되었습니다.')).toBeVisible()
  })
})
