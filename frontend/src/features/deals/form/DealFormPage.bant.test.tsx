import { fireEvent, screen, waitFor, within } from '@testing-library/react'
import type { UserEvent } from '@testing-library/user-event'
import { afterEach, describe, expect, it, vi } from 'vitest'
import { keys } from '../../../data/queryKeys'
import { gateway } from '../../../gateway'
import { ApiError } from '../../../shared/api/problem'
import { renderAt } from '../../../test/mockApp'
import { codeOf, DETAIL_URL, openEdit, save } from './testHelpers'

/**
 * Deal 폼의 BANT 4항목(AC-30, AC-31): 버튼 없이 텍스트 자동완성 입력이다.
 * 후보는 그 구분의 Label, 비우면 선택 안 함, 목록에 없는 이름은 저장할 때 새 Label이 된다.
 */
afterEach(() => vi.restoreAllMocks())

const CATEGORIES = ['Budget', 'Authority', 'Need', 'Timeline'] as const
const HINT = '목록에 없는 Label입니다. 저장하면 새 Label로 추가됩니다.'
const TOO_LONG = 'Label 이름은 50자 이내로 입력하세요.'

async function openNew() {
  const view = await renderAt('/deals/new')
  await screen.findByRole('heading', { name: 'Deal 등록' })
  return view
}

/** 저장에 필요한 나머지 필수 입력을 채운다. */
async function fillRequired(user: UserEvent, name = 'BANT 테스트 Deal') {
  await user.type(screen.getByLabelText('Deal Name'), name)
  await user.type(screen.getByLabelText('고객 회사명'), '신규고객사')
  await user.type(screen.getByLabelText('고객 담당자명'), '홍길동')
  await user.type(screen.getByLabelText('금액(단위:천원)'), '50000')
  await user.type(screen.getByLabelText('Users'), '10')
  fireEvent.change(screen.getByLabelText('Expected Close'), { target: { value: '2027-06-01' } })
}

const bantOf = (category: string) => within(screen.getByRole('group', { name: 'BANT' })).getByRole('combobox', { name: category })
const optionNames = (category: string) => within(screen.getByRole('listbox', { name: category })).getAllByRole('option').map((o) => o.textContent)

describe('BANT 입력의 모양 (AC-30)', () => {
  it('renders each item as a text combobox named by its category, in order', async () => {
    await openNew()

    const names = within(screen.getByRole('group', { name: 'BANT' }))
      .getAllByRole('combobox')
      .map((c) => c.getAttribute('aria-label') ?? (c as HTMLInputElement).labels?.[0]?.textContent)
    expect(names).toEqual([...CATEGORIES])
    for (const category of CATEGORIES) expect(bantOf(category).tagName).toBe('INPUT')
  })

  it('has no new-label button or new-label name input, and no select for the items', async () => {
    await openNew()
    const bant = screen.getByRole('group', { name: 'BANT' })

    expect(within(bant).queryByRole('button', { name: /새 Label/ })).not.toBeInTheDocument()
    expect(within(bant).queryByLabelText(/새 Label 이름/)).not.toBeInTheDocument()
    expect(within(bant).queryByRole('button', { name: '만들기' })).not.toBeInTheDocument()
    expect(bant.querySelector('select')).toBeNull()
  })

  it('starts empty on registration with the placeholder that says empty means not selected', async () => {
    await openNew()

    for (const category of CATEGORIES) {
      expect(bantOf(category)).toHaveDisplayValue('')
      expect(bantOf(category)).toHaveAttribute('placeholder', '비워 두면 선택 안 함')
    }
  })

  it('has no way to rename or delete an existing label', async () => {
    await openNew()
    const bant = screen.getByRole('group', { name: 'BANT' })

    expect(within(bant).queryByRole('button', { name: /수정|삭제|이름 변경/ })).not.toBeInTheDocument()
  })
})

describe('후보와 필터 (AC-30)', () => {
  it('shows only the labels of that category when focused', async () => {
    const { user } = await openNew()

    await user.click(bantOf('Budget'))

    await waitFor(() => expect(optionNames('Budget')).toEqual(['단독 예산 확보', '풀 예산 확보', '잔여 예산 활용', '예산 작업중', '내년 예산', '예산 없음', '미확인']))
    expect(screen.queryByRole('option', { name: 'CEO 보고 완료' })).not.toBeInTheDocument()
  })

  it('keeps the labels that contain the typed text', async () => {
    const { user } = await openNew()

    await user.type(bantOf('Authority'), '보고')

    await waitFor(() => expect(optionNames('Authority')).toEqual(['CEO 보고 완료', 'CISO 보고 완료', '팀장 보고 완료']))
  })

  it('fills the item with a picked label', async () => {
    const { user } = await openNew()
    await user.click(bantOf('Need'))

    await user.click(await screen.findByRole('option', { name: '컴플라이언스' }))

    expect(bantOf('Need')).toHaveDisplayValue('컴플라이언스')
  })

  it('shows a label made in Deal management in the candidates', async () => {
    const view = await openNew()
    await gateway.labels.create('budget', '분기 예산')
    await view.client.invalidateQueries()

    await view.user.click(bantOf('Budget'))

    await waitFor(() => expect(optionNames('Budget')).toContain('분기 예산'))
  })
})

describe('안내와 검증 (AC-31)', () => {
  it('hints that an unknown label will be added, and not for a listed one or a blank', async () => {
    const { user } = await openNew()
    const row = () => bantOf('Budget').closest('.kv-row') as HTMLElement

    await user.type(bantOf('Budget'), '분기 예산')
    expect(within(row()).getByText(HINT)).toBeVisible()

    await user.clear(bantOf('Budget'))
    await user.type(bantOf('Budget'), '풀 예산 확보')
    expect(within(row()).queryByText(HINT)).not.toBeInTheDocument()

    await user.clear(bantOf('Budget'))
    expect(within(row()).queryByText(HINT)).not.toBeInTheDocument()
  })

  it('does not take a label of another category as a match for the hint', async () => {
    const { user } = await openNew()

    await user.type(bantOf('Budget'), 'CEO 보고 완료')

    expect(within(bantOf('Budget').closest('.kv-row') as HTMLElement).getByText(HINT)).toBeVisible()
  })

  it('blocks saving a label over 50 characters with the message under that item only', async () => {
    const create = vi.spyOn(gateway.deals, 'create')
    const { user } = await openNew()
    await fillRequired(user)
    fireEvent.change(bantOf('Need'), { target: { value: 'x'.repeat(51) } })

    await save(user)

    const row = bantOf('Need').closest('.kv-row') as HTMLElement
    expect(within(row).getByText(TOO_LONG)).toBeVisible()
    expect(bantOf('Need')).toBeInvalid()
    expect(create).not.toHaveBeenCalled()
    expect(within(bantOf('Budget').closest('.kv-row') as HTMLElement).queryByText(TOO_LONG)).not.toBeInTheDocument()
  })

  it('accepts exactly 50 characters', async () => {
    const create = vi.spyOn(gateway.deals, 'create')
    const { user, location } = await openNew()
    await fillRequired(user)
    fireEvent.change(bantOf('Need'), { target: { value: 'y'.repeat(50) } })

    await save(user)

    await waitFor(() => expect(location()).toMatch(DETAIL_URL))
    expect(create.mock.calls[0]?.[0].bant.need).toEqual({ name: 'y'.repeat(50) })
  })
})

describe('저장 (AC-31)', () => {
  it('saves blank items as not selected', async () => {
    const create = vi.spyOn(gateway.deals, 'create')
    const { user, location } = await openNew()
    await fillRequired(user)

    await save(user)

    await waitFor(() => expect(location()).toMatch(DETAIL_URL))
    expect(create.mock.calls[0]?.[0].bant).toEqual({ budget: null, authority: null, need: null, timeline: null })
    const bant = await screen.findByRole('region', { name: 'BANT' })
    expect(within(bant).getByRole('button', { name: 'Budget 수정' })).toHaveTextContent('—')
  })

  it('treats a blank-only item as not selected', async () => {
    const create = vi.spyOn(gateway.deals, 'create')
    const { user, location } = await openNew()
    await fillRequired(user)
    await user.type(bantOf('Timeline'), '   ')

    await save(user)

    await waitFor(() => expect(location()).toMatch(DETAIL_URL))
    expect(create.mock.calls[0]?.[0].bant.timeline).toBeNull()
  })

  it('sends the id of a picked label, also when the typed text differs only in spaces', async () => {
    const create = vi.spyOn(gateway.deals, 'create')
    const { user } = await openNew()
    const labels = await gateway.labels.list()
    const budget = labels.find((l) => l.category === 'budget' && l.name === '단독 예산 확보')
    const authority = labels.find((l) => l.category === 'authority' && l.name === 'CEO 보고 완료')
    await fillRequired(user)
    await user.click(bantOf('Budget'))
    await user.click(await screen.findByRole('option', { name: '단독 예산 확보' }))
    await user.type(bantOf('Authority'), '  CEO 보고 완료  ')

    await save(user)

    await waitFor(() => expect(create).toHaveBeenCalledTimes(1))
    expect(create.mock.calls[0]?.[0].bant).toMatchObject({ budget: { id: budget?.id }, authority: { id: authority?.id } })
  })

  it('sends the name of an unknown label and creates it in that category', async () => {
    const create = vi.spyOn(gateway.deals, 'create')
    const { user, location } = await openNew()
    await fillRequired(user)
    await user.type(bantOf('Budget'), '  즉석 예산 라벨  ')

    await save(user)

    await waitFor(() => expect(location()).toMatch(DETAIL_URL))
    expect(create.mock.calls[0]?.[0].bant.budget).toEqual({ name: '즉석 예산 라벨' })
    const created = (await gateway.labels.list()).find((l) => l.name === '즉석 예산 라벨')
    expect(created).toMatchObject({ category: 'budget', isDefault: false })
    const bant = await screen.findByRole('region', { name: 'BANT' })
    expect(within(bant).getByRole('button', { name: 'Budget 수정' })).toHaveTextContent('즉석 예산 라벨')
  })

  it('allows the same new name in another category and creates one label for each', async () => {
    const { user, location } = await openNew()
    await fillRequired(user)
    await user.type(bantOf('Budget'), '공통 이름')
    await user.type(bantOf('Authority'), '공통 이름')

    await save(user)

    await waitFor(() => expect(location()).toMatch(DETAIL_URL))
    const made = (await gateway.labels.list()).filter((l) => l.name === '공통 이름')
    expect(made.map((l) => l.category).sort()).toEqual(['authority', 'budget'])
  })

  it('shows the server message and creates no label when a later validation fails', async () => {
    const { user } = await openNew()
    const before = (await gateway.labels.list()).length
    await fillRequired(user)
    await user.type(bantOf('Need'), '실패할 라벨')
    fireEvent.change(screen.getByLabelText('구매절차'), { target: { value: 'a'.repeat(501) } })

    await save(user)

    expect(await screen.findByText('구매절차는 500자 이내로 입력하세요.')).toBeVisible()
    expect(await gateway.labels.list()).toHaveLength(before)
    expect(bantOf('Need')).toHaveDisplayValue('실패할 라벨')
  })
})

describe('수정 폼 (AC-31, R2)', () => {
  it('prefills the current label names, and empty for an unselected item', async () => {
    const { code } = await openEdit('대한제조 MFA 확대')
    const bant = (await gateway.deals.get(code)).bant
    const labels = await gateway.labels.list()
    const nameOf = (id: number | null) => (id === null ? '' : (labels.find((l) => l.id === id)?.name ?? '?'))
    await waitFor(() => expect(bantOf('Budget')).toHaveDisplayValue(nameOf(bant.budget)))

    expect(bantOf('Authority')).toHaveDisplayValue(nameOf(bant.authority))
    expect(bantOf('Need')).toHaveDisplayValue(nameOf(bant.need))
    expect(bantOf('Timeline')).toHaveDisplayValue(nameOf(bant.timeline))
    expect([bant.budget, bant.authority, bant.need, bant.timeline].some((id) => id !== null)).toBe(true)
  })

  it('saves untouched items as their current ids', async () => {
    const update = vi.spyOn(gateway.deals, 'update')
    const { user, location, code } = await openEdit('대한제조 MFA 확대')
    await waitFor(() => expect(bantOf('Budget')).not.toHaveDisplayValue(''))
    const before = (await gateway.deals.get(code)).bant

    await save(user)

    await waitFor(() => expect(location()).toBe(`/deals/${code}`))
    const sent = update.mock.calls[0]?.[1].bant
    expect(sent).toEqual({
      budget: before.budget ? { id: before.budget } : null,
      authority: before.authority ? { id: before.authority } : null,
      need: before.need ? { id: before.need } : null,
      timeline: before.timeline ? { id: before.timeline } : null,
    })
  })

  it('clears an item to not selected when the text is emptied', async () => {
    const { user, location, code } = await openEdit('대한제조 MFA 확대')
    await waitFor(() => expect(bantOf('Budget')).not.toHaveDisplayValue(''))

    await user.clear(bantOf('Budget'))
    await save(user)

    await waitFor(() => expect(location()).toBe(`/deals/${code}`))
    expect((await gateway.deals.get(code)).bant.budget).toBeNull()
  })

  it('saves a changed item by name and keeps the history of the change', async () => {
    const { user, location, code } = await openEdit('대한제조 MFA 확대')
    await waitFor(() => expect(bantOf('Budget')).not.toHaveDisplayValue(''))

    await user.clear(bantOf('Timeline'))
    await user.type(bantOf('Timeline'), '내후년 구매 검토')
    await save(user)

    await waitFor(() => expect(location()).toBe(`/deals/${code}`))
    const entries = await gateway.history.list(code, { category: 'bant' })
    expect(entries[0]?.after).toContain('내후년 구매 검토')
  })

  it('disables the BANT inputs and shows an error banner when the label list cannot be read, keeping the selection on save', async () => {
    const code = await codeOf('대한제조 MFA 확대')
    const before = (await gateway.deals.get(code)).bant
    vi.spyOn(gateway.labels, 'list').mockRejectedValue(
      new ApiError(500, { type: 'https://sales.neoine.test/problems/internal', title: 'x', status: 500, detail: 'Label 목록을 불러오지 못했습니다.' }),
    )
    const { user, location } = await renderAt(`/deals/${code}/edit`)
    await screen.findByRole('heading', { name: 'Deal 수정' })
    await screen.findByLabelText('Deal Name')

    expect(await screen.findByText('Label 목록을 불러오지 못했습니다.')).toBeVisible()
    for (const category of CATEGORIES) expect(bantOf(category)).toBeDisabled()
    await save(user)

    await waitFor(() => expect(location()).toBe(`/deals/${code}`))
    expect((await gateway.deals.get(code)).bant).toEqual(before)
  })

  it('keeps the selection when saving while the label list is being re-fetched', async () => {
    const update = vi.spyOn(gateway.deals, 'update')
    const { user, location, code, client } = await openEdit('대한제조 MFA 확대')
    await waitFor(() => expect(bantOf('Budget')).not.toHaveDisplayValue(''))
    const before = (await gateway.deals.get(code)).bant
    // 이미 채워진 뒤 Label 목록 재조회가 끝나지 않은 순간을 만든다.
    const realList = gateway.labels.list.bind(gateway.labels)
    let release: () => void = () => undefined
    vi.spyOn(gateway.labels, 'list').mockImplementation(async () => {
      await new Promise<void>((resolve) => (release = resolve))
      return realList()
    })
    void client.invalidateQueries({ queryKey: keys.labels })
    await waitFor(() => expect(client.isFetching({ queryKey: keys.labels })).toBe(1))

    await save(user)

    release()
    await waitFor(() => expect(location()).toBe(`/deals/${code}`))
    const sent = update.mock.calls[0]?.[1].bant
    if (sent !== undefined) {
      expect(sent).toEqual({
        budget: before.budget ? { id: before.budget } : null,
        authority: before.authority ? { id: before.authority } : null,
        need: before.need ? { id: before.need } : null,
        timeline: before.timeline ? { id: before.timeline } : null,
      })
    }
    expect((await gateway.deals.get(code)).bant).toEqual(before)
  })
})
