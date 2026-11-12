import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { useState } from 'react'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import type { ContactDraft } from '../model/inputs'
import type { ContactKind, ContactRow } from '../model/types'
import { ContactPicker } from './ContactPicker'

function row(id: number, company: string, name: string, extra: Partial<ContactRow> = {}): ContactRow {
  return {
    id,
    kind: 'customer',
    company,
    name,
    title: '과장',
    email: `${name}@x.kr`,
    phone: '010-1111-2222',
    createdAt: '2026-01-01T00:00:00+09:00',
    updatedAt: '2026-01-01T00:00:00+09:00',
    dealCount: 1,
    ...extra,
  }
}

const ROWS: ContactRow[] = [
  row(1, '한빛상사', '김철수', { title: '부장', email: 'kim@hanbit.kr', phone: '010-1234-5678', dealCount: 3 }),
  row(2, '한빛상사', '이영희', { title: '대리', email: 'lee@hanbit.kr' }),
  row(3, '한빛상사', '박무메일', { title: '사원', email: null, phone: null }),
  row(4, '대한소프트', '최대한'),
  row(5, 'Acme', 'Kim', { title: '이사', email: 'kim@acme.kr' }),
]

const companies = vi.hoisted(() => ({ calls: [] as ContactKind[] }))
vi.mock('../../data/contacts', () => ({
  useContactCompanies: (kind: ContactKind) => {
    companies.calls.push(kind)
    return { data: ['Acme', '대한소프트', '한빛상사'] }
  },
  useContactsByCompany: (_kind: ContactKind, company: string) => ({
    data: company ? ROWS.filter((r) => r.company.toLowerCase() === company.toLowerCase()) : undefined,
  }),
}))
const EMPTY: ContactDraft = { contactId: null, company: '', name: '', title: '', email: null, phone: null }

function Host({
  kind = 'customer',
  initial = EMPTY,
  onValue,
  layout,
}: {
  kind?: ContactKind
  initial?: ContactDraft
  onValue?: (v: ContactDraft) => void
  layout?: 'stack' | 'rows'
}) {
  const [value, setValue] = useState(initial)
  return (
    <ContactPicker
      kind={kind}
      label={kind === 'customer' ? '고객' : '파트너'}
      {...(layout ? { layout } : {})}
      value={value}
      onChange={(v) => {
        setValue(v)
        onValue?.(v)
      }}
    />
  )
}

beforeEach(() => {
  companies.calls.length = 0
})

describe('ContactPicker', () => {
  // 선택기의 회사 후보는 그 종류의 회사 목록이다
  // 테스트 코드: CT-093
  it('lists distinct companies of the given kind', async () => {
    // given: 파트너용 선택기
    render(<Host kind="partner" />)

    // when: 회사명 콤보박스를 연다
    await userEvent.click(screen.getByRole('combobox', { name: '파트너 회사명' }))

    // then: 파트너 종류로 조회한 회사 목록이 후보로 나온다
    expect(companies.calls).toContain('partner')
    expect(screen.getAllByRole('option').map((o) => o.textContent)).toEqual(['Acme', '대한소프트', '한빛상사'])
  })

  // 회사를 정하면 그 회사의 담당자가 직급·이메일 설명과 함께 후보로 나온다
  // 테스트 코드: CT-094
  it('lists the people of the chosen company with title and email', async () => {
    // given: 고객용 선택기에서 회사 '한빛상사'를 고른다
    render(<Host />)
    await userEvent.click(screen.getByRole('combobox', { name: '고객 회사명' }))
    await userEvent.click(screen.getByRole('option', { name: '한빛상사' }))

    // when: 담당자명 콤보박스를 연다
    await userEvent.click(screen.getByRole('combobox', { name: '고객 담당자명' }))
    const options = screen.getAllByRole('option')
    // then: 그 회사 담당자 3명이 직급·이메일 설명과 함께 나온다
    expect(options).toHaveLength(3)
    expect(options[0]).toHaveTextContent('김철수')
    expect(options[0]).toHaveTextContent('부장')
    expect(options[0]).toHaveTextContent('kim@hanbit.kr')
  })

  // 기존 담당자를 고르면 직급·이메일·전화가 채워지고 그 연락처 id가 잡힌다
  // 테스트 코드: CT-095
  it('fills title, email and phone when an existing person is chosen', async () => {
    // given: 회사 '한빛상사'를 고르고 담당자 후보를 연다
    const onValue = vi.fn()
    render(<Host onValue={onValue} />)
    // when: '김철수'를 고른다
    await userEvent.click(screen.getByRole('combobox', { name: '고객 회사명' }))
    await userEvent.click(screen.getByRole('option', { name: '한빛상사' }))
    await userEvent.click(screen.getByRole('combobox', { name: '고객 담당자명' }))

    await userEvent.click(screen.getByRole('option', { name: /김철수/ }))

    // then: 직급·이메일·전화가 채워지고 값의 연락처 id가 1이다
    expect(screen.getByLabelText('고객 직급')).toHaveValue('부장')
    expect(screen.getByLabelText('고객 이메일')).toHaveValue('kim@hanbit.kr')
    expect(screen.getByLabelText('고객 전화')).toHaveValue('010-1234-5678')
    expect(onValue).toHaveBeenLastCalledWith({
      contactId: 1,
      company: '한빛상사',
      name: '김철수',
      title: '부장',
      email: 'kim@hanbit.kr',
      phone: '010-1234-5678',
    })
  })

  // 채운 연락 정보를 고쳐도 연락처 id는 유지된다
  // 테스트 코드: CT-096
  it('keeps the contact id when the user edits the filled fields, so the card is updated', async () => {
    // given: 기존 담당자 '김철수'를 골라 연락 정보가 채워졌다
    const onValue = vi.fn()
    render(<Host onValue={onValue} />)
    // when: 전화를 다른 번호로 고친다
    await userEvent.click(screen.getByRole('combobox', { name: '고객 회사명' }))
    await userEvent.click(screen.getByRole('option', { name: '한빛상사' }))
    await userEvent.click(screen.getByRole('combobox', { name: '고객 담당자명' }))
    await userEvent.click(screen.getByRole('option', { name: /김철수/ }))

    await userEvent.clear(screen.getByLabelText('고객 전화'))
    await userEvent.type(screen.getByLabelText('고객 전화'), '010-9999-0000')

    // then: 연락처 id는 1 그대로이고 전화만 바뀐다
    expect(onValue).toHaveBeenLastCalledWith(expect.objectContaining({ contactId: 1, phone: '010-9999-0000' }))
  })

  // 새 회사·사람을 직접 입력하면 새 연락처(id 없음)다
  // 테스트 코드: CT-097
  it('treats typing a new company and person as a new contact', async () => {
    // given: 빈 선택기
    const onValue = vi.fn()
    render(<Host onValue={onValue} />)

    // when: 새 회사명·담당자명·이메일을 직접 입력한다
    await userEvent.type(screen.getByRole('combobox', { name: '고객 회사명' }), '새회사')
    await userEvent.type(screen.getByRole('combobox', { name: '고객 담당자명' }), '홍길동')
    await userEvent.type(screen.getByLabelText('고객 이메일'), 'hong@new.kr')

    // then: 값의 연락처 id가 null이다
    expect(onValue).toHaveBeenLastCalledWith({
      contactId: null,
      company: '새회사',
      name: '홍길동',
      title: '',
      email: 'hong@new.kr',
      phone: null,
    })
  })

  // 선택기에서 이메일을 비우면 null이 된다
  // 테스트 코드: CT-100
  it('maps an emptied email to null', async () => {
    // given: 이메일이 있는 값
    const onValue = vi.fn()
    render(<Host onValue={onValue} initial={{ ...EMPTY, company: 'A', name: 'B', email: 'a@b.kr' }} />)

    // when: 이메일을 지운다
    await userEvent.clear(screen.getByLabelText('고객 이메일'))

    // then: 이메일이 null이다
    expect(onValue).toHaveBeenLastCalledWith(expect.objectContaining({ email: null }))
  })

  // 선택기에서 전화를 비우면 null이 된다
  // 테스트 코드: CT-100
  it('maps an emptied phone to null', async () => {
    // given: 전화가 있는 값
    const onValue = vi.fn()
    render(<Host onValue={onValue} initial={{ ...EMPTY, company: 'A', name: 'B', phone: '010-1234-5678' }} />)

    // when: 전화를 지운다
    await userEvent.clear(screen.getByLabelText('고객 전화'))

    // then: 전화가 null이다
    expect(onValue).toHaveBeenLastCalledWith(expect.objectContaining({ phone: null }))
  })

  // 회사명 입력 중 공백을 지우고 3초 안내를 보인다
  // 테스트 코드: CT-101
  it('blocks whitespace while typing and says so', async () => {
    // given: 빈 선택기
    const onValue = vi.fn()
    render(<Host onValue={onValue} />)

    // when: 회사명에 공백이 든 글을 입력한다
    await userEvent.type(screen.getByRole('combobox', { name: '고객 회사명' }), '한 빛')

    // then: 공백이 지워지고 '공백은 입력할 수 없습니다.' 안내가 보인다
    expect(screen.getByRole('combobox', { name: '고객 회사명' })).toHaveValue('한빛')
    expect(screen.getByText('공백은 입력할 수 없습니다.')).toBeInTheDocument()
  })

  // 담당자명·이메일·전화도 붙여넣기 포함 공백을 지운다
  // 테스트 코드: CT-101
  it('blocks whitespace in name, email and phone too, including pasted text', async () => {
    // given: 빈 선택기
    render(<Host />)

    // when: 담당자명·이메일·전화에 공백이 든 글을 붙여넣는다
    await userEvent.click(screen.getByRole('combobox', { name: '고객 담당자명' }))
    await userEvent.paste('홍 길동')
    await userEvent.click(screen.getByLabelText('고객 이메일'))
    await userEvent.paste('a @b.kr')
    await userEvent.click(screen.getByLabelText('고객 전화'))
    await userEvent.paste('010 1234')

    // then: 세 칸 모두 공백이 지워진다
    expect(screen.getByRole('combobox', { name: '고객 담당자명' })).toHaveValue('홍길동')
    expect(screen.getByLabelText('고객 이메일')).toHaveValue('a@b.kr')
    expect(screen.getByLabelText('고객 전화')).toHaveValue('0101234')
  })

  // 직급은 공백을 허용한다
  // 테스트 코드: CT-101
  it('allows spaces inside the title', async () => {
    // given: 빈 선택기
    const onValue = vi.fn()
    render(<Host onValue={onValue} />)

    // when: 직급에 공백이 든 글을 입력한다
    await userEvent.type(screen.getByLabelText('고객 직급'), '영업 팀장')

    // then: 공백이 그대로 남는다
    expect(screen.getByLabelText('고객 직급')).toHaveValue('영업 팀장')
  })

  // 회사명 대소문자가 달라도 같은 회사의 담당자가 후보로 나온다
  // 테스트 코드: CT-094
  it('shows the same-company people regardless of letter case', async () => {
    // given: 회사명이 대문자로 입력된 선택기
    render(<Host initial={{ ...EMPTY, company: 'ACME' }} />)


    // when: 담당자명 콤보박스를 연다
    await userEvent.click(screen.getByRole('combobox', { name: '고객 담당자명' }))
    const options = screen.getAllByRole('option')
    // then: 소문자로 등록된 같은 회사의 담당자가 나온다
    expect(options).toHaveLength(1)
    expect(options[0]).toHaveTextContent('Kim')
  })

  // 이메일 없이 기존 사람과 같은 회사명·담당자명이면 같은 사람 안내를 보인다
  // 테스트 코드: CT-103
  it('explains that a person without email is merged into the existing one', async () => {
    // when: 선택기를 그린다 (전제: 기존 담당자와 같은 회사명·담당자명이고 이메일이 없는 새 입력)
    render(<Host initial={{ ...EMPTY, company: '한빛상사', name: '박무메일' }} />)

    // then: 같은 사람으로 처리된다는 안내가 보인다
    expect(
      screen.getByText('기존 연락처와 같은 사람으로 처리됩니다(회사명·담당자명 일치, 이메일 없음).'),
    ).toBeInTheDocument()
  })

  // 이메일이 있으면 같은 사람 안내를 보이지 않는다
  // 테스트 코드: CT-103
  it('does not show the merge note when an email is given', () => {
    // when: 선택기를 그린다 (전제: 기존 담당자와 같은 회사명·담당자명이지만 이메일이 있는 입력)
    render(<Host initial={{ ...EMPTY, company: '한빛상사', name: '박무메일', email: 'x@y.kr' }} />)

    // then: 같은 사람 안내가 없다
    expect(screen.queryByText(/같은 사람으로 처리됩니다/)).not.toBeInTheDocument()
  })

  // 고른 연락처를 다른 Deal도 쓰면 공유 안내를 보인다
  // 테스트 코드: CT-104
  it('warns when the chosen contact is shared by other deals', async () => {
    // given: 3개 Deal이 쓰는 담당자 후보
    render(<Host />)
    // when: 그 담당자를 고른다
    await userEvent.click(screen.getByRole('combobox', { name: '고객 회사명' }))
    await userEvent.click(screen.getByRole('option', { name: '한빛상사' }))
    await userEvent.click(screen.getByRole('combobox', { name: '고객 담당자명' }))

    await userEvent.click(screen.getByRole('option', { name: /김철수/ }))

    // then: '3개 Deal에서 함께 사용 중' 안내가 보인다
    expect(
      screen.getByText('이 연락처는 3개 Deal에서 함께 사용 중입니다. 수정하면 모두에 반영됩니다.'),
    ).toBeInTheDocument()
  })

  // 이메일 칸을 떠난 뒤 형식이 틀리면 안내한다
  // 테스트 코드: CT-102
  it('shows an email format message after leaving the field', async () => {
    // given: 빈 선택기
    render(<Host />)

    // when: 틀린 이메일을 입력하고 칸을 떠난다
    await userEvent.type(screen.getByLabelText('고객 이메일'), 'not-an-email')
    await userEvent.tab()

    // then: 이메일 형식 안내가 보인다
    expect(screen.getByText('이메일 형식이 올바르지 않습니다.')).toBeInTheDocument()
  })

  // 폼이 넘긴 칸별 오류는 그 칸 아래에 alert로 보인다
  // 테스트 코드: CT-102
  it('shows errors handed in by the form', () => {
    // when: 선택기를 그린다 (전제: 폼이 회사명 오류를 넘긴 선택기)
    render(
      <ContactPicker
        kind="customer"
        label="고객"
        value={EMPTY}
        onChange={() => {}}
        errors={{ company: '고객 회사명을 입력하세요.' }}
      />,
    )

    // then: 그 오류가 alert로 보인다
    expect(screen.getByRole('alert')).toHaveTextContent('고객 회사명을 입력하세요.')
  })

  // 폼이 넘긴 이메일 오류가 이메일 형식 안내보다 우선한다
  // 테스트 코드: CT-102
  it('prefers the email error from the form over the format message', async () => {
    // given: 폼이 이메일 오류를 넘기고 틀린 이메일이 입력된 선택기
    render(
      <ContactPicker
        kind="customer"
        label="고객"
        value={{ ...EMPTY, email: 'not-an-email' }}
        onChange={() => {}}
        errors={{ email: '이메일을 확인하세요.' }}
      />,
    )

    // when: 이메일 칸을 떠난다
    await userEvent.click(screen.getByLabelText('고객 이메일'))
    await userEvent.tab()

    // then: 폼 오류가 보이고 형식 안내는 보이지 않는다
    expect(screen.getByRole('alert')).toHaveTextContent('이메일을 확인하세요.')
    expect(screen.queryByText('이메일 형식이 올바르지 않습니다.')).not.toBeInTheDocument()
  })

  // 회사를 다른 회사로 바꾸면 고른 사람과 연락 정보가 비워진다
  // 테스트 코드: CT-099
  it('clears the old person when the company is changed to another one', async () => {
    // given: 기존 연락처를 고른 값
    const onValue = vi.fn()
    render(
      <Host
        onValue={onValue}
        initial={{ contactId: 1, company: '한빛상사', name: '김철수', title: '부장', email: 'kim@hanbit.kr', phone: null }}
      />,
    )

    // when: 회사명을 다른 회사로 바꾼다
    await userEvent.clear(screen.getByRole('combobox', { name: '고객 회사명' }))
    await userEvent.type(screen.getByRole('combobox', { name: '고객 회사명' }), '다른회사')

    // then: 연락처 id·담당자명·연락 정보가 비워진다
    expect(onValue).toHaveBeenLastCalledWith({
      contactId: null,
      company: '다른회사',
      name: '',
      title: '',
      email: null,
      phone: null,
    })
  })

  // 회사명의 대소문자만 바꾸면 고른 사람이 유지된다
  // 테스트 코드: CT-099
  it('keeps the chosen person when only the letter case of the company changes', async () => {
    // given: 'Acme'의 담당자를 고른 값
    const onValue = vi.fn()
    render(
      <Host
        onValue={onValue}
        initial={{ contactId: 5, company: 'Acme', name: 'Kim', title: '이사', email: 'kim@acme.kr', phone: null }}
      />,
    )

    // when: 회사명을 대문자 'ACME'로 바꾼다
    await userEvent.tripleClick(screen.getByRole('combobox', { name: '고객 회사명' }))
    await userEvent.paste('ACME')

    // then: 연락처 id와 담당자명이 유지된다
    expect(onValue).toHaveBeenLastCalledWith({
      contactId: 5,
      company: 'ACME',
      name: 'Kim',
      title: '이사',
      email: 'kim@acme.kr',
      phone: null,
    })
  })

  // 고른 담당자의 이름을 다른 이름으로 바꾸면 연락처 id가 풀린다
  // 테스트 코드: CT-098
  it('releases the contact id when the chosen name is changed to another name', async () => {
    // given: 기존 담당자 '김철수'를 고른 값
    const onValue = vi.fn()
    render(<Host onValue={onValue} />)
    // when: 담당자명을 다른 이름으로 바꾼다
    await userEvent.click(screen.getByRole('combobox', { name: '고객 회사명' }))
    await userEvent.click(screen.getByRole('option', { name: '한빛상사' }))
    await userEvent.click(screen.getByRole('combobox', { name: '고객 담당자명' }))
    await userEvent.click(screen.getByRole('option', { name: /김철수/ }))

    await userEvent.clear(screen.getByRole('combobox', { name: '고객 담당자명' }))
    await userEvent.type(screen.getByRole('combobox', { name: '고객 담당자명' }), '다른이름')

    // then: 연락처 id가 null이고 회사명은 유지된다
    expect(onValue).toHaveBeenLastCalledWith(expect.objectContaining({ contactId: null, company: '한빛상사', name: '다른이름' }))
  })

  // rows 배치는 짧은 보이는 라벨과 전체 접근성 이름을 쓴다
  // 테스트 코드: CT-105
  it('renders short visible labels in the rows layout', () => {
    // given: rows 배치 선택기
    render(<Host layout="rows" />)

    const group = screen.getByRole('group', { name: '고객' })
    const shown = [
      ['고객 회사명', '회사'],
      ['고객 담당자명', '담당자'],
      ['고객 직급', '직급'],
      ['고객 이메일', '이메일'],
      ['고객 전화', '전화'],
    ] as const
    // when: 선택기를 그린다
    for (const [accessible, text] of shown) {
      const input = screen.getByLabelText(accessible) as HTMLInputElement
      expect(group).toContainElement(input)
      expect(Array.from(input.labels ?? []).map((l) => l.textContent)).toContain(text)
    }
    // then: 보이는 라벨은 짧고 접근성 이름은 전체 글자다
    expect(group).toHaveClass('contact-picker--rows')
  })

  // 기본 배치는 전체 라벨을 쓴다
  // 테스트 코드: CT-105
  it('keeps the stacked layout and full labels by default', () => {
    // given: 기본 배치 선택기
    render(<Host />)

    // when: 선택기를 그린다
    const group = screen.getByRole('group', { name: '고객' })
    // then: 범례가 있고 칸 라벨은 전체 글자다
    expect(group).not.toHaveClass('contact-picker--rows')
    const input = screen.getByLabelText('고객 회사명') as HTMLInputElement
    expect(Array.from(input.labels ?? []).map((l) => l.textContent)).toContain('고객 회사명')
  })
})
