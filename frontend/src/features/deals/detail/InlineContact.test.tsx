import { cleanup, screen, waitFor, within } from '@testing-library/react'
import { describe, expect, it } from 'vitest'
import { gateway } from '../../../gateway'
import { renderAt } from '../../../test/mockApp'
import { detailPath } from '../../../test/detailTestUtils'

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
  it('opens the company list on click and filters it by partial, case-insensitive text', async () => {
    const { user } = await openDeal(1, '한빛은행 ITDR 도입')
    await gateway.auth.quickLogin('u-root') // 연락처 직접 등록은 admin만 가능하다.
    await gateway.contacts.create('customer', { company: 'Acme', name: 'Kim', title: '', email: null, phone: null })
    await gateway.auth.quickLogin('u-kim')
    await user.click(within(customerCard()).getByRole('button', { name: '고객 회사명 수정' }))
    const company = within(customerCard()).getByRole('combobox', { name: '고객 회사명' })
    expect(company).toHaveFocus()
    const all = await screen.findByRole('listbox', { name: '고객 회사명' })
    const names = within(all).getAllByRole('option').map((o) => o.textContent)
    expect(names).toEqual(expect.arrayContaining(['한빛은행', '누리통신', '하늘카드', 'Acme']))
    expect(names).not.toContain('에이원시스템')

    await user.clear(company)
    await user.type(company, '하')
    expect(within(await screen.findByRole('listbox', { name: '고객 회사명' })).getAllByRole('option').map((o) => o.textContent)).toEqual(['하늘카드'])
    await user.clear(company)
    await user.type(company, 'aCM')
    expect(within(await screen.findByRole('listbox', { name: '고객 회사명' })).getAllByRole('option').map((o) => o.textContent)).toEqual(['Acme'])
  })

  it('clears the person and opens the person list when another existing company is picked, then fills the contact info', async () => {
    const { user } = await openDeal(1, '한빛은행 ITDR 도입')
    await user.click(within(customerCard()).getByRole('button', { name: '고객 회사명 수정' }))
    await user.click(await screen.findByRole('option', { name: '하늘카드' }))

    const person = within(customerCard()).getByRole('combobox', { name: '고객 담당자명' })
    expect(person).toHaveValue('')
    expect(person).toHaveFocus()
    expect(within(customerCard()).getByLabelText('고객 직급')).toHaveValue('')
    const list = await screen.findByRole('listbox', { name: '고객 담당자명' })
    expect(within(list).getAllByRole('option').map((o) => o.textContent)).toEqual([
      expect.stringContaining('신동혁'),
      expect.stringContaining('윤소라'),
    ])
    expect(within(customerCard()).queryByText(/신규 고객사입니다/)).not.toBeInTheDocument()

    await user.type(person, '윤')
    expect(within(await screen.findByRole('listbox', { name: '고객 담당자명' })).getAllByRole('option')).toHaveLength(1)
    // 후보를 고르는 순간 반영되고, 연락 정보가 자동으로 채워진다(저장 버튼 없음).
    await user.click(await screen.findByRole('option', { name: /윤소라/ }))
    await waitFor(() => expect(valueOf(customerCard(), '고객 회사명 수정')).toBe('하늘카드'))
    expect(valueOf(customerCard(), '고객 담당자명 수정')).toBe('윤소라')
    expect(valueOf(customerCard(), '고객 직급 수정')).toBe('과장')
    expect(valueOf(customerCard(), '고객 이메일 수정')).toBe('yoon@haneul.test')
    expect(valueOf(customerCard(), '고객 전화 수정')).toBe('010-9999-0000')
    expect(await screen.findByText('고객 연락처가 저장되었습니다.')).toBeVisible()

    await user.click(screen.getByRole('tab', { name: 'Deal History' }))
    const row = (await screen.findAllByRole('row')).find((r) => within(r).queryByRole('cell', { name: '고객 연락처' }))
    expect(row).toBeDefined()
    expect(row).toHaveTextContent('하늘카드')
    expect(row).toHaveTextContent('윤소라')
  })

  it('treats a typed unknown company as new: clears every contact field, explains it and needs a person name', async () => {
    const { user } = await openDeal(1, '한빛은행 ITDR 도입')
    await user.click(within(customerCard()).getByRole('button', { name: '고객 회사명 수정' }))
    const company = within(customerCard()).getByRole('combobox', { name: '고객 회사명' })
    await user.clear(company)
    await user.type(company, '신규상사')

    expect(within(customerCard()).getByText('신규 고객사입니다. 담당자 정보를 입력하세요.')).toBeVisible()
    for (const label of ['고객 담당자명', '고객 직급', '고객 이메일', '고객 전화'])
      expect(within(customerCard()).getByLabelText(label)).toHaveValue('')
    expect(within(customerCard()).queryByRole('button', { name: /연락처 (저장|편집 취소)$/ })).not.toBeInTheDocument()

    // 담당자명이 비어 있으면 Enter로 확정해도 저장되지 않고 오류와 함께 편집이 유지된다.
    await user.click(within(customerCard()).getByRole('combobox', { name: '고객 담당자명' }))
    await user.keyboard('{Enter}')
    expect(await within(customerCard()).findByText('담당자명을 입력하세요.')).toBeVisible()
    expect(within(customerCard()).getByRole('combobox', { name: '고객 회사명' })).toHaveValue('신규상사')

    await user.type(within(customerCard()).getByRole('combobox', { name: '고객 담당자명' }), '홍길동')
    await user.type(within(customerCard()).getByLabelText('고객 직급'), '이사{Enter}')
    await waitFor(() => expect(valueOf(customerCard(), '고객 회사명 수정')).toBe('신규상사'))
    expect(valueOf(customerCard(), '고객 담당자명 수정')).toBe('홍길동')
    expect(valueOf(customerCard(), '고객 직급 수정')).toBe('이사')
    expect(valueOf(customerCard(), '고객 이메일 수정')).toBe('—')
  })

  it('discards the whole contact edit with Escape and keeps the old contact', async () => {
    const { user } = await openDeal(1, '한빛은행 ITDR 도입')
    await user.click(within(customerCard()).getByRole('button', { name: '고객 회사명 수정' }))
    await user.clear(within(customerCard()).getByRole('combobox', { name: '고객 회사명' }))
    await user.type(within(customerCard()).getByRole('combobox', { name: '고객 회사명' }), '다른회사')
    await user.keyboard('{Escape}{Escape}')
    expect(valueOf(customerCard(), '고객 회사명 수정')).toBe('한빛은행')
    expect(valueOf(customerCard(), '고객 담당자명 수정')).toBe('정민수')
  })

  it('blocks spaces in company, person, email and phone and tells the user', async () => {
    const { user } = await openDeal(1, '한빛은행 ITDR 도입')
    await user.click(within(customerCard()).getByRole('button', { name: '고객 회사명 수정' }))
    const company = within(customerCard()).getByRole('combobox', { name: '고객 회사명' })
    await user.clear(company)
    await user.type(company, '신 규')
    expect(company).toHaveValue('신규')
    expect(within(customerCard()).getByText('공백은 입력할 수 없습니다.')).toBeVisible()
    await user.keyboard('{Escape}{Escape}')

    await user.click(within(customerCard()).getByRole('button', { name: '고객 이메일 수정' }))
    const email = within(customerCard()).getByLabelText('고객 이메일')
    await user.clear(email)
    await user.type(email, 'a b@x.kr')
    expect(email).toHaveValue('ab@x.kr')
    expect(within(customerCard()).getByText('공백은 입력할 수 없습니다.')).toBeVisible()
  })
})

describe('담당자 · 직급 · 이메일 · 전화 단일 필드 편집', () => {
  it('picks another existing person of the same company from the list and fills the contact info', async () => {
    const { user } = await openDeal(1, '한빛은행 ITDR 도입')
    await user.click(within(customerCard()).getByRole('button', { name: '고객 담당자명 수정' }))
    const list = await screen.findByRole('listbox', { name: '고객 담당자명' })
    expect(within(list).getAllByRole('option')).toHaveLength(3)
    await user.clear(within(customerCard()).getByRole('combobox', { name: '고객 담당자명' }))
    await user.type(within(customerCard()).getByRole('combobox', { name: '고객 담당자명' }), '오')
    await user.click(await screen.findByRole('option', { name: /오지현/ }))
    await waitFor(() => expect(valueOf(customerCard(), '고객 담당자명 수정')).toBe('오지현'))
    expect(valueOf(customerCard(), '고객 직급 수정')).toBe('차장')
    expect(valueOf(customerCard(), '고객 이메일 수정')).toBe('oh@hanbit.test')
    expect(valueOf(customerCard(), '고객 회사명 수정')).toBe('한빛은행')
  })

  it('takes a typed new person of the same company with empty contact info', async () => {
    const { user } = await openDeal(1, '한빛은행 ITDR 도입')
    await user.click(within(customerCard()).getByRole('button', { name: '고객 담당자명 수정' }))
    const person = within(customerCard()).getByRole('combobox', { name: '고객 담당자명' })
    await user.clear(person)
    await user.type(person, '신입담당{Enter}')
    await waitFor(() => expect(valueOf(customerCard(), '고객 담당자명 수정')).toBe('신입담당'))
    expect(valueOf(customerCard(), '고객 직급 수정')).toBe('—')
    expect(valueOf(customerCard(), '고객 이메일 수정')).toBe('—')
    expect(valueOf(customerCard(), '고객 전화 수정')).toBe('—')
  })

  it('edits title, email and phone directly and rejects a bad email', async () => {
    const { user } = await openDeal(1, '한빛은행 ITDR 도입')
    await user.click(within(customerCard()).getByRole('button', { name: '고객 직급 수정' }))
    const title = within(customerCard()).getByLabelText('고객 직급')
    await user.clear(title)
    await user.type(title, '팀장{Enter}')
    await waitFor(() => expect(valueOf(customerCard(), '고객 직급 수정')).toBe('팀장'))
    expect(valueOf(customerCard(), '고객 담당자명 수정')).toBe('정민수')

    await user.click(within(customerCard()).getByRole('button', { name: '고객 이메일 수정' }))
    const email = within(customerCard()).getByLabelText('고객 이메일')
    await user.clear(email)
    await user.type(email, 'not-an-email{Enter}')
    expect(await within(customerCard()).findByRole('alert')).toHaveTextContent('이메일 형식이 올바르지 않습니다.')
    await user.clear(email)
    await user.type(email, 'new@hanbit.test{Enter}')
    await waitFor(() => expect(valueOf(customerCard(), '고객 이메일 수정')).toBe('new@hanbit.test'))

    await user.click(within(customerCard()).getByRole('button', { name: '고객 전화 수정' }))
    await user.clear(within(customerCard()).getByLabelText('고객 전화'))
    await user.keyboard('{Enter}')
    await waitFor(() => expect(valueOf(customerCard(), '고객 전화 수정')).toBe('—'))
  })

  it('tells that a shared contact is changed for every deal using it', async () => {
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
    await user.click(screen.getByRole('button', { name: '고객 직급 수정' }))
    expect(await screen.findByText(/개 Deal에서 함께 사용 중입니다. 수정하면 모두에 반영됩니다./)).toBeVisible()
  })
})

describe('파트너 인라인 편집', () => {
  it('replaces the partner by clicking the company and picking another existing company and person', async () => {
    const { user } = await openDeal(1, '한빛은행 ITDR 도입')
    await user.click(within(partnerCard()).getByRole('button', { name: '파트너 회사명 수정' }))
    expect(within(partnerCard()).getByText(/이력으로 남고 비활성이 됩니다/)).toBeVisible()
    await user.click(await screen.findByRole('option', { name: '코어테크' }))
    await user.click(await screen.findByRole('option', { name: /민지훈/ }))
    await waitFor(() => expect(valueOf(partnerCard(), '파트너 회사명 수정')).toBe('코어테크'))
    expect(await screen.findByText('파트너가 교체되었습니다.')).toBeVisible()
    expect(within(partnerCard()).getByText(/이전 파트너 이력/)).toBeVisible()
    await user.click(screen.getByRole('tab', { name: 'Deal History' }))
    expect(await screen.findByRole('cell', { name: '파트너' })).toBeVisible()
  })

  it('removes the active partner only after a confirmation', async () => {
    const { user } = await openDeal(1, '한빛은행 ITDR 도입')
    await user.click(within(partnerCard()).getByRole('button', { name: '파트너 제거' }))
    const dialog = await screen.findByRole('dialog', { name: '파트너 제거' })
    await user.click(within(dialog).getByRole('button', { name: '취소' }))
    expect(within(partnerCard()).queryByText('파트너 없음')).not.toBeInTheDocument()
    await user.click(within(partnerCard()).getByRole('button', { name: '파트너 제거' }))
    await user.click(within(await screen.findByRole('dialog', { name: '파트너 제거' })).getByRole('button', { name: '제거' }))
    await waitFor(() => expect(within(partnerCard()).getByText('파트너 없음')).toBeVisible())
    expect(within(partnerCard()).queryByRole('button', { name: '파트너 제거' })).not.toBeInTheDocument()
  })

  it('adds a partner to a deal that has none by clicking the empty value', async () => {
    const { user } = await openDeal(5, '누리통신 NGFW 갱신')
    await user.click(within(partnerCard()).getByRole('button', { name: '파트너 추가' }))
    const company = within(partnerCard()).getByRole('combobox', { name: '파트너 회사명' })
    await user.type(company, '새파트너')
    expect(within(partnerCard()).getByText('신규 파트너입니다. 담당자 정보를 입력하세요.')).toBeVisible()
    await user.type(within(partnerCard()).getByRole('combobox', { name: '파트너 담당자명' }), '박파트')
    await user.tab() // 포커스가 블록 안(직급)에 머물면 저장하지 않는다.
    expect(within(partnerCard()).getByLabelText('파트너 직급')).toHaveFocus()
    await user.keyboard('{Enter}')
    await waitFor(() => expect(valueOf(partnerCard(), '파트너 회사명 수정')).toBe('새파트너'))
    expect(await screen.findByText('파트너가 추가되었습니다.')).toBeVisible()
  })
})
