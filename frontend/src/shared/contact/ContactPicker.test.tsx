import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { useState } from 'react'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import type { ContactDraft } from '../model/inputs'
import type { ContactKind, ContactRow } from '../model/types'
import { ContactPicker } from './ContactPicker'

function row(id: string, company: string, name: string, extra: Partial<ContactRow> = {}): ContactRow {
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
  row('c1', '한빛상사', '김철수', { title: '부장', email: 'kim@hanbit.kr', phone: '010-1234-5678', dealCount: 3 }),
  row('c2', '한빛상사', '이영희', { title: '대리', email: 'lee@hanbit.kr' }),
  row('c3', '한빛상사', '박무메일', { title: '사원', email: null, phone: null }),
  row('c4', '대한소프트', '최대한'),
]

const companies = vi.hoisted(() => ({ calls: [] as ContactKind[] }))
vi.mock('../../data/contacts', () => ({
  useContactCompanies: (kind: ContactKind) => {
    companies.calls.push(kind)
    return { data: ['대한소프트', '한빛상사'] }
  },
  useContactsByCompany: (_kind: ContactKind, company: string) => ({
    data: company ? ROWS.filter((r) => r.company.toLowerCase() === company.toLowerCase()) : undefined,
  }),
}))
// A-1의 contactRules 본문이 들어오기 전에도 같은 계약으로 검증하기 위한 최소 구현.
vi.mock('../model/contactRules', () => ({
  WHITESPACE_MESSAGE: '공백은 입력할 수 없습니다.',
  EMAIL_FORMAT_MESSAGE: '이메일 형식이 올바르지 않습니다.',
  stripWhitespace: (t: string) => t.replace(/\s/g, ''),
  validateContactInput: (i: { email: string | null }) =>
    i.email && !/^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(i.email) ? { email: '이메일 형식이 올바르지 않습니다.' } : {},
  findSamePerson: (
    contacts: ContactRow[],
    _kind: string,
    c: { company: string; name: string; email: string | null },
  ) =>
    contacts.find(
      (x) =>
        x.company.toLowerCase() === c.company.toLowerCase() &&
        x.name.toLowerCase() === c.name.toLowerCase() &&
        (c.email === null || x.email === null || x.email.toLowerCase() === c.email.toLowerCase()),
    ) ?? null,
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
  it('lists distinct companies of the given kind', async () => {
    render(<Host kind="partner" />)

    await userEvent.click(screen.getByRole('combobox', { name: '파트너 회사명' }))

    expect(companies.calls).toContain('partner')
    expect(screen.getAllByRole('option').map((o) => o.textContent)).toEqual(['대한소프트', '한빛상사'])
  })

  it('lists the people of the chosen company with title and email', async () => {
    render(<Host />)
    await userEvent.click(screen.getByRole('combobox', { name: '고객 회사명' }))
    await userEvent.click(screen.getByRole('option', { name: '한빛상사' }))

    await userEvent.click(screen.getByRole('combobox', { name: '고객 담당자명' }))

    const options = screen.getAllByRole('option')
    expect(options).toHaveLength(3)
    expect(options[0]).toHaveTextContent('김철수')
    expect(options[0]).toHaveTextContent('부장')
    expect(options[0]).toHaveTextContent('kim@hanbit.kr')
  })

  it('fills title, email and phone when an existing person is chosen', async () => {
    const onValue = vi.fn()
    render(<Host onValue={onValue} />)
    await userEvent.click(screen.getByRole('combobox', { name: '고객 회사명' }))
    await userEvent.click(screen.getByRole('option', { name: '한빛상사' }))
    await userEvent.click(screen.getByRole('combobox', { name: '고객 담당자명' }))

    await userEvent.click(screen.getByRole('option', { name: /김철수/ }))

    expect(screen.getByLabelText('고객 직급')).toHaveValue('부장')
    expect(screen.getByLabelText('고객 이메일')).toHaveValue('kim@hanbit.kr')
    expect(screen.getByLabelText('고객 전화')).toHaveValue('010-1234-5678')
    expect(onValue).toHaveBeenLastCalledWith({
      contactId: 'c1',
      company: '한빛상사',
      name: '김철수',
      title: '부장',
      email: 'kim@hanbit.kr',
      phone: '010-1234-5678',
    })
  })

  it('keeps the contact id when the user edits the filled fields, so the card is updated', async () => {
    const onValue = vi.fn()
    render(<Host onValue={onValue} />)
    await userEvent.click(screen.getByRole('combobox', { name: '고객 회사명' }))
    await userEvent.click(screen.getByRole('option', { name: '한빛상사' }))
    await userEvent.click(screen.getByRole('combobox', { name: '고객 담당자명' }))
    await userEvent.click(screen.getByRole('option', { name: /김철수/ }))

    await userEvent.clear(screen.getByLabelText('고객 전화'))
    await userEvent.type(screen.getByLabelText('고객 전화'), '010-9999-0000')

    expect(onValue).toHaveBeenLastCalledWith(expect.objectContaining({ contactId: 'c1', phone: '010-9999-0000' }))
  })

  it('treats typing a new company and person as a new contact', async () => {
    const onValue = vi.fn()
    render(<Host onValue={onValue} />)

    await userEvent.type(screen.getByRole('combobox', { name: '고객 회사명' }), '새회사')
    await userEvent.type(screen.getByRole('combobox', { name: '고객 담당자명' }), '홍길동')
    await userEvent.type(screen.getByLabelText('고객 이메일'), 'hong@new.kr')

    expect(onValue).toHaveBeenLastCalledWith({
      contactId: null,
      company: '새회사',
      name: '홍길동',
      title: '',
      email: 'hong@new.kr',
      phone: null,
    })
  })

  it('maps an emptied email to null', async () => {
    const onValue = vi.fn()
    render(<Host onValue={onValue} initial={{ ...EMPTY, company: 'A', name: 'B', email: 'a@b.kr' }} />)

    await userEvent.clear(screen.getByLabelText('고객 이메일'))

    expect(onValue).toHaveBeenLastCalledWith(expect.objectContaining({ email: null }))
  })

  it('blocks whitespace while typing and says so', async () => {
    const onValue = vi.fn()
    render(<Host onValue={onValue} />)

    await userEvent.type(screen.getByRole('combobox', { name: '고객 회사명' }), '한 빛')

    expect(screen.getByRole('combobox', { name: '고객 회사명' })).toHaveValue('한빛')
    expect(screen.getByText('공백은 입력할 수 없습니다.')).toBeInTheDocument()
  })

  it('blocks whitespace in name, email and phone too, including pasted text', async () => {
    render(<Host />)

    await userEvent.click(screen.getByRole('combobox', { name: '고객 담당자명' }))
    await userEvent.paste('홍 길동')
    await userEvent.click(screen.getByLabelText('고객 이메일'))
    await userEvent.paste('a @b.kr')
    await userEvent.click(screen.getByLabelText('고객 전화'))
    await userEvent.paste('010 1234')

    expect(screen.getByRole('combobox', { name: '고객 담당자명' })).toHaveValue('홍길동')
    expect(screen.getByLabelText('고객 이메일')).toHaveValue('a@b.kr')
    expect(screen.getByLabelText('고객 전화')).toHaveValue('0101234')
  })

  it('allows spaces inside the title', async () => {
    const onValue = vi.fn()
    render(<Host onValue={onValue} />)

    await userEvent.type(screen.getByLabelText('고객 직급'), '영업 팀장')

    expect(screen.getByLabelText('고객 직급')).toHaveValue('영업 팀장')
  })

  it('shows the same-company people regardless of letter case', async () => {
    render(<Host initial={{ ...EMPTY, company: '한빛상사' }} />)

    await userEvent.click(screen.getByRole('combobox', { name: '고객 담당자명' }))

    expect(screen.getAllByRole('option')).toHaveLength(3)
  })

  it('explains that a person without email is merged into the existing one', async () => {
    render(<Host initial={{ ...EMPTY, company: '한빛상사', name: '박무메일' }} />)

    expect(
      screen.getByText('기존 연락처와 같은 사람으로 처리됩니다(회사명·담당자명 일치, 이메일 없음).'),
    ).toBeInTheDocument()
  })

  it('does not show the merge note when an email is given', () => {
    render(<Host initial={{ ...EMPTY, company: '한빛상사', name: '박무메일', email: 'x@y.kr' }} />)

    expect(screen.queryByText(/같은 사람으로 처리됩니다/)).not.toBeInTheDocument()
  })

  it('warns when the chosen contact is shared by other deals', async () => {
    render(<Host />)
    await userEvent.click(screen.getByRole('combobox', { name: '고객 회사명' }))
    await userEvent.click(screen.getByRole('option', { name: '한빛상사' }))
    await userEvent.click(screen.getByRole('combobox', { name: '고객 담당자명' }))

    await userEvent.click(screen.getByRole('option', { name: /김철수/ }))

    expect(
      screen.getByText('이 연락처는 3개 Deal에서 함께 사용 중입니다. 수정하면 모두에 반영됩니다.'),
    ).toBeInTheDocument()
  })

  it('shows an email format message after leaving the field', async () => {
    render(<Host />)

    await userEvent.type(screen.getByLabelText('고객 이메일'), 'not-an-email')
    await userEvent.tab()

    expect(screen.getByText('이메일 형식이 올바르지 않습니다.')).toBeInTheDocument()
  })

  it('shows errors handed in by the form', () => {
    render(
      <ContactPicker
        kind="customer"
        label="고객"
        value={EMPTY}
        onChange={() => {}}
        errors={{ company: '고객 회사명을 입력하세요.' }}
      />,
    )

    expect(screen.getByRole('alert')).toHaveTextContent('고객 회사명을 입력하세요.')
  })

  it('clears the old person when the company is changed to another one', async () => {
    const onValue = vi.fn()
    render(
      <Host
        onValue={onValue}
        initial={{ contactId: 'c1', company: '한빛상사', name: '김철수', title: '부장', email: 'kim@hanbit.kr', phone: null }}
      />,
    )

    await userEvent.clear(screen.getByRole('combobox', { name: '고객 회사명' }))
    await userEvent.type(screen.getByRole('combobox', { name: '고객 회사명' }), '다른회사')

    expect(onValue).toHaveBeenLastCalledWith({
      contactId: null,
      company: '다른회사',
      name: '',
      title: '',
      email: null,
      phone: null,
    })
  })

  it('renders short visible labels in the rows layout', () => {
    render(<Host layout="rows" />)

    const group = screen.getByRole('group', { name: '고객' })
    const shown = [
      ['고객 회사명', '회사'],
      ['고객 담당자명', '담당자'],
      ['고객 직급', '직급'],
      ['고객 이메일', '이메일'],
      ['고객 전화', '전화'],
    ] as const
    for (const [accessible, text] of shown) {
      const input = screen.getByLabelText(accessible) as HTMLInputElement
      expect(group).toContainElement(input)
      expect(Array.from(input.labels ?? []).map((l) => l.textContent)).toContain(text)
    }
    expect(group).toHaveClass('contact-picker--rows')
  })

  it('keeps the stacked layout and full labels by default', () => {
    render(<Host />)

    const group = screen.getByRole('group', { name: '고객' })
    expect(group).not.toHaveClass('contact-picker--rows')
    const input = screen.getByLabelText('고객 회사명') as HTMLInputElement
    expect(Array.from(input.labels ?? []).map((l) => l.textContent)).toContain('고객 회사명')
  })
})
