import { fireEvent, screen, waitFor, within } from '@testing-library/react'
import { describe, expect, it } from 'vitest'
import { kvPairs } from '../../../test/kvPairs'
import { renderAt } from '../../../test/mockApp'
import { DETAIL_URL, openEdit, pickPerson, save } from './testHelpers'

async function openNew() {
  const view = await renderAt('/deals/new')
  await screen.findByRole('heading', { name: 'Deal 등록' })
  await screen.findByLabelText('Deal Name')
  return view
}

const tile = (name: string) => screen.getByRole('region', { name })
const follows = (a: Element, b: Element) => Boolean(a.compareDocumentPosition(b) & Node.DOCUMENT_POSITION_FOLLOWING)

describe('Deal 등록·수정 폼 타일 구성 (AC-10, AC-22)', () => {
  it('renders the deal info, customer, partner and BANT tiles in the detail order', async () => {
    await openNew()
    const names = ['Deal 정보', '고객', '파트너', 'BANT']
    const tiles = names.map(tile)
    tiles.forEach((region, i) => {
      const first = region.firstElementChild as HTMLElement
      expect(first.tagName).toBe('H2')
      expect(first).toHaveTextContent(names[i] as string)
      expect(region).toHaveClass('form-section')
      const next = tiles[i + 1]
      if (next) expect(follows(region, next)).toBe(true)
    })
    expect(follows(tiles[3] as HTMLElement, screen.getByRole('button', { name: '저장' }))).toBe(true)
    for (const old of ['기본 정보', '고객 · 파트너', '진행 · 금액', '견적 · POC · 구매절차']) {
      expect(screen.queryByRole('heading', { name: old })).not.toBeInTheDocument()
    }
  })
})

describe('Deal 정보 타일의 항목 (AC-11, AC-12, AC-14, AC-15)', () => {
  it('orders the deal info inputs like the detail page', async () => {
    await openNew()
    const info = tile('Deal 정보')
    const items = [
      within(info).getByLabelText('Deal Name'),
      within(info).getByLabelText('Owner'),
      within(info).getByLabelText('Status'),
      within(info).getByLabelText('Forecast'),
      within(info).getByLabelText('금액(단위:천원)'),
      within(info).getByLabelText('Expected Close'),
      within(info).getByLabelText('Vendor'),
      within(info).getByLabelText('Solution'),
      within(info).getByLabelText('Users'),
      within(info).getByRole('group', { name: '견적' }),
      within(info).getByRole('group', { name: 'POC' }),
      within(info).getByLabelText('구매절차'),
    ]
    items.slice(1).forEach((item, i) => expect(follows(items[i] as Element, item)).toBe(true))
    for (const absent of ['Next Action', '최종 업데이트', '등록일', 'Deal code']) {
      expect(within(info).queryByText(absent)).not.toBeInTheDocument()
    }
  })

  it('marks Users as required and no longer calls it optional', async () => {
    await openNew()
    const info = tile('Deal 정보')
    expect(within(info).getByLabelText('Users').closest('.field')).toHaveClass('required')
    expect(within(info).queryByText(/\(선택\)/)).not.toBeInTheDocument()
    expect(within(info).getByText('견적 단위 사용자 수')).toBeVisible()
  })

  it('shows the deal code as a read-only item on the edit form', async () => {
    const { code } = await openEdit('누리통신 MFA')
    const info = tile('Deal 정보')
    const label = within(info).getByText('Deal code')
    const value = within(info).getByText(code)
    const row = label.closest('.kv-row') as HTMLElement
    expect(row).toContainElement(value)
    expect(row.querySelector('input, select, textarea')).toBeNull()
    expect(follows(within(info).getByLabelText('Deal Name'), label)).toBe(true)
    expect(follows(label, within(info).getByLabelText('Owner'))).toBe(true)
    expect(screen.getAllByText(/Deal code/)).toHaveLength(1)
    const h1 = screen.getByRole('heading', { level: 1, name: 'Deal 수정' })
    // AC-12: h1 아래 안내 문단이 없다. h1 다음 형제는 form이고, form 밖(페이지 머리)에는 Deal code 글자가 없다.
    const form = h1.nextElementSibling as HTMLElement
    expect(form.tagName).toBe('FORM')
    expect(form).toContainElement(info)
    for (const child of Array.from(h1.parentElement?.children ?? [])) {
      if (child !== form) expect(child.textContent ?? '').not.toContain('Deal code')
    }
  })

  it('has no deal code item on the registration form', async () => {
    await openNew()
    expect(screen.queryByText(/Deal code/)).not.toBeInTheDocument()
  })

  it('uses a single line input for the procurement', async () => {
    await openNew()
    expect(screen.getByLabelText('구매절차').tagName).toBe('INPUT')
  })

  it('groups the quote and poc inputs under one label each', async () => {
    await openNew()
    const quote = screen.getByRole('group', { name: '견적' })
    expect(within(quote).getByLabelText('견적 제출여부').tagName).toBe('SELECT')
    expect(within(quote).getByLabelText('견적 제출일')).toHaveAttribute('placeholder', 'yyyymmdd')
    const poc = screen.getByRole('group', { name: 'POC' })
    expect(within(poc).getByLabelText('POC 여부').tagName).toBe('SELECT')
    expect(within(poc).getByLabelText('POC 완료일')).toHaveAttribute('placeholder', 'yyyymmdd')
  })

  it('keeps the currency notice inside the deal info tile', async () => {
    await openNew()
    expect(within(tile('Deal 정보')).getAllByText(/KRW/).length).toBeGreaterThan(0)
  })

  it('saves the quote, poc and procurement entered on the new form', async () => {
    const { user, location } = await openNew()
    await user.type(screen.getByLabelText('Deal Name'), '견적 저장 테스트')
    await pickPerson(user, '고객', '한빛은행', /정민수/)
    await user.type(screen.getByLabelText('금액(단위:천원)'), '100000')
    await user.type(screen.getByLabelText('Solution'), 'ITDR')
    await user.type(screen.getByLabelText('Users'), '10')
    fireEvent.change(screen.getByLabelText('Expected Close'), { target: { value: '2027-06-01' } })
    await user.selectOptions(screen.getByLabelText('견적 제출여부'), 'YES')
    fireEvent.change(screen.getByLabelText('견적 제출일'), { target: { value: '2027-01-10' } })
    await user.selectOptions(screen.getByLabelText('POC 여부'), 'ING')
    await user.type(screen.getByLabelText('구매절차'), '수의계약')
    await save(user)
    await waitFor(() => expect(location()).toMatch(DETAIL_URL))

    await screen.findByRole('heading', { level: 1, name: '견적 저장 테스트' })
    const facts = Object.fromEntries(kvPairs(tile('Deal 정보')))
    expect(facts['견적']).toMatch(/^제출 \(2027-01-10\)/)
    expect(facts['POC']).toMatch(/^ING · 진행 중/)
    expect(facts['구매절차']).toBe('수의계약')
  })
})

describe('라벨-입력 한 행 (AC-13)', () => {
  it('puts each label and its input in the same row', async () => {
    await openNew()
    const cases: Array<[string, string, string]> = [
      ['Deal Name', '.kv-row, .field', 'Deal Name'],
      ['금액(단위:천원)', '.kv-row, .field', '금액(단위:천원)'],
      ['Owner', '.kv-row', 'Owner'],
      ['Status', '.kv-row', 'Status'],
      ['Budget', '.kv-row', 'Budget'],
      ['고객 직급', '.kv-row, .field', '직급'],
    ]
    for (const [accessible, selector, shown] of cases) {
      const row = screen.getByLabelText(accessible).closest(selector) as HTMLElement
      expect(row, accessible).not.toBeNull()
      expect((row.firstElementChild as HTMLElement).textContent?.startsWith(shown)).toBe(true)
    }
  })

  it('shows a validation message in the row of its input', async () => {
    const { user } = await openNew()
    await save(user)
    await screen.findAllByRole('alert')
    for (const [label, message] of [
      ['Deal Name', 'Deal Name을 입력하세요.'],
      ['Expected Close', 'Expected Close를 입력하세요.'],
      ['Solution', 'Solution을 입력하세요.'],
    ] as const) {
      const row = screen.getByLabelText(label).closest('.kv-row, .field') as HTMLElement
      expect(within(row).getByRole('alert')).toHaveTextContent(message)
    }
  })
})

describe('고객·파트너·BANT 타일 (AC-16, AC-17)', () => {
  it('shows the contact rows with short labels and keeps the accessible names', async () => {
    await openNew()
    const shown = { 회사명: '회사', 담당자명: '담당자', 직급: '직급', 이메일: '이메일', 전화: '전화' }
    for (const [kind, region] of [['고객', tile('고객')], ['파트너', tile('파트너')]] as const) {
      for (const [field, text] of Object.entries(shown)) {
        const input = within(region).getByLabelText(`${kind} ${field}`) as HTMLInputElement
        expect(Array.from(input.labels ?? []).map((l) => l.textContent)).toContain(text)
      }
    }
  })

  it('keeps the partner notices and the remove button inside the partner tile', async () => {
    const { user } = await openEdit('누리통신 MFA')
    const partner = tile('파트너')
    await user.click(within(partner).getByRole('button', { name: '파트너 제거' }))
    expect(within(partner).getByText(/저장하면 기존 활성 파트너\(.+\)가 제거되고 이력으로 남습니다\./)).toBeVisible()
  })

  it('keeps each BANT autocomplete input in its own row, with no new label button', async () => {
    await openNew()
    const bant = tile('BANT')
    expect(within(bant).getByRole('group', { name: 'BANT' })).toBeVisible()
    for (const category of ['Budget', 'Authority', 'Need', 'Timeline']) {
      const input = within(bant).getByRole('combobox', { name: category })
      const row = input.closest('.kv-row') as HTMLElement
      expect(row, category).not.toBeNull()
      expect(within(row).getAllByRole('combobox')).toHaveLength(1)
    }
    expect(within(bant).queryByRole('button', { name: /새 Label/ })).not.toBeInTheDocument()
  })
})

describe('전역 .field 스타일 범위 (회귀 방지)', () => {
  it('keeps the quote and poc rows inside the shared field styling', async () => {
    await openNew()
    for (const name of ['견적', 'POC']) {
      const row = screen.getByRole('group', { name }).closest('.kv-row') as HTMLElement
      expect(row, name).not.toBeNull()
      expect(row).toHaveClass('field')
    }
  })

  it('keeps the deal code row inside the shared field styling on the edit form', async () => {
    await openEdit('누리통신 MFA')
    const row = within(tile('Deal 정보')).getByText('Deal code').closest('.kv-row') as HTMLElement
    expect(row).toHaveClass('field')
  })
})
