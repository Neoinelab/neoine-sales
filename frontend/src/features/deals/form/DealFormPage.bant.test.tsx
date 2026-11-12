import { fireEvent, screen, waitFor, within } from '@testing-library/react'
import type { UserEvent } from '@testing-library/user-event'
import { afterEach, describe, expect, it, vi } from 'vitest'
import { keys } from '../../../data/queryKeys'
import { gateway } from '../../../gateway'
import { ApiError } from '../../../shared/api/problem'
import { renderAt } from '../../../test/mockApp'
import { codeOf, DETAIL_URL, openEdit, save } from './testHelpers'

/**
 * Deal 폼의 BANT 4항목: 버튼 없이 텍스트 자동완성 입력이다.
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
  await user.type(screen.getByLabelText('금액(단위:원)'), '50000000')
  await user.type(screen.getByLabelText('Solution'), 'ITDR')
  await user.type(screen.getByLabelText('Users count'), '10')
  fireEvent.change(screen.getByLabelText('Expected Close'), { target: { value: '2027-06-01' } })
}

const bantOf = (category: string) => within(screen.getByRole('group', { name: 'BANT' })).getByRole('combobox', { name: category })
const optionNames = (category: string) => within(screen.getByRole('listbox', { name: category })).getAllByRole('option').map((o) => o.textContent)

describe('BANT 입력의 모양', () => {
  // BANT는 구분별 텍스트 콤보박스 4개이고 순서가 정해져 있다.
  // 테스트 코드: DE-092
  it('renders each item as a text combobox named by its category, in order', async () => {
    // when: Deal 등록 화면을 연다.
    await openNew()

    const names = within(screen.getByRole('group', { name: 'BANT' }))
      .getAllByRole('combobox')
      .map((c) => c.getAttribute('aria-label') ?? (c as HTMLInputElement).labels?.[0]?.textContent)

    // then: Budget·Authority·Need·Timeline 콤보박스가 순서대로 있다.
    expect(names).toEqual([...CATEGORIES])
    for (const category of CATEGORIES) expect(bantOf(category).tagName).toBe('INPUT')
  })

  // 새 Label 버튼·이름 입력·선택 상자가 없다.
  // 테스트 코드: DE-092
  it('has no new-label button or new-label name input, and no select for the items', async () => {
    // when: Deal 등록 화면을 연다.
    await openNew()
    const bant = screen.getByRole('group', { name: 'BANT' })

    // then: 새 Label 버튼과 선택 상자가 없다.
    expect(within(bant).queryByRole('button', { name: /새 Label/ })).not.toBeInTheDocument()
    expect(within(bant).queryByLabelText(/새 Label 이름/)).not.toBeInTheDocument()
    expect(within(bant).queryByRole('button', { name: '만들기' })).not.toBeInTheDocument()
    expect(bant.querySelector('select')).toBeNull()
  })

  // 등록 시작 때 비어 있고 자리표시 문구가 없다.
  // 테스트 코드: DE-092
  it('starts empty on registration with no placeholder text', async () => {
    // when: Deal 등록 화면을 연다.
    await openNew()

    // then: BANT 칸이 비어 있고 placeholder가 없다.
    for (const category of CATEGORIES) {
      expect(bantOf(category)).toHaveDisplayValue('')
      expect(bantOf(category)).not.toHaveAttribute('placeholder')
    }
  })

  // 기존 Label을 수정·삭제하는 기능이 없다.
  // 테스트 코드: DE-092
  it('has no way to rename or delete an existing label', async () => {
    // when: Deal 등록 화면을 연다.
    await openNew()
    const bant = screen.getByRole('group', { name: 'BANT' })

    // then: 이름 수정·삭제 버튼이 없다.
    expect(within(bant).queryByRole('button', { name: /수정|삭제|이름 변경/ })).not.toBeInTheDocument()
  })
})

describe('후보와 필터', () => {
  // 포커스하면 그 구분 Label만 후보로 보인다.
  // 테스트 코드: DE-093
  it('shows only the labels of that category when focused', async () => {
    // when: Budget 칸을 포커스한다.
    const { user } = await openNew()

    await user.click(bantOf('Budget'))

    // then: Budget Label만 후보다.
    await waitFor(() => expect(optionNames('Budget')).toEqual(['단독 예산 확보', '풀 예산 확보', '잔여 예산 활용', '예산 작업중', '내년 예산', '예산 없음', '미확인']))
    expect(screen.queryByRole('option', { name: 'CEO 보고 완료' })).not.toBeInTheDocument()
  })

  // 입력하면 입력을 포함하는 Label만 후보로 남는다.
  // 테스트 코드: DE-093
  it('keeps the labels that contain the typed text', async () => {
    // when: 텍스트를 입력한다.
    const { user } = await openNew()

    await user.type(bantOf('Authority'), '보고')

    // then: 그 텍스트를 포함하는 Label만 후보다.
    await waitFor(() => expect(optionNames('Authority')).toEqual(['CEO 보고 완료', 'CISO 보고 완료', '팀장 보고 완료']))
  })

  // 후보를 고르면 칸에 이름이 채워진다.
  // 테스트 코드: DE-093
  it('fills the item with a picked label', async () => {
    // when: 후보를 고른다.
    const { user } = await openNew()
    await user.click(bantOf('Need'))

    await user.click(await screen.findByRole('option', { name: '컴플라이언스' }))

    // then: 칸에 그 Label 이름이 채워진다.
    expect(bantOf('Need')).toHaveDisplayValue('컴플라이언스')
  })

  // Deal 관리에서 만든 Label도 후보로 보인다.
  // 테스트 코드: DE-093
  it('shows a label made in Deal management in the candidates', async () => {
    // given: Deal 관리에서 Label을 만들었다.
    const view = await openNew()
    await gateway.labels.create('budget', '분기 예산')
    await view.client.invalidateQueries()

    // when: 해당 구분 칸을 포커스한다.
    await view.user.click(bantOf('Budget'))

    // then: 새로 만든 Label이 후보에 있다.
    await waitFor(() => expect(optionNames('Budget')).toContain('분기 예산'))
  })
})

describe('안내와 검증', () => {
  // 목록에 없는 이름이면 새 Label 안내를 보이고 목록 이름·빈 칸에는 안 보인다.
  // 테스트 코드: DE-094
  it('hints that an unknown label will be added, and not for a listed one or a blank', async () => {
    const { user } = await openNew()
    const row = () => bantOf('Budget').closest('.kv-row') as HTMLElement

    // when: 목록에 없는 이름을 입력한다.
    await user.type(bantOf('Budget'), '분기 예산')
    // then: 새 Label 안내가 보인다.
    expect(within(row()).getByText(HINT)).toBeVisible()

    // when: 목록에 있는 이름을 입력한다.
    await user.clear(bantOf('Budget'))
    await user.type(bantOf('Budget'), '풀 예산 확보')
    // then: 안내가 없다.
    expect(within(row()).queryByText(HINT)).not.toBeInTheDocument()

    // when: 칸을 비운다.
    await user.clear(bantOf('Budget'))
    // then: 안내가 없다.
    expect(within(row()).queryByText(HINT)).not.toBeInTheDocument()
  })

  // 다른 구분에만 있는 이름은 일치로 보지 않고 안내를 보인다.
  // 테스트 코드: DE-094
  it('does not take a label of another category as a match for the hint', async () => {
    // when: 다른 구분의 Label 이름을 입력한다.
    const { user } = await openNew()

    await user.type(bantOf('Budget'), 'CEO 보고 완료')

    // then: 새 Label 안내가 보인다.
    expect(within(bantOf('Budget').closest('.kv-row') as HTMLElement).getByText(HINT)).toBeVisible()
  })

  // 50자를 넘는 BANT 이름은 그 칸에만 문구를 보이고 저장을 막는다.
  // 테스트 코드: DE-095
  it('blocks saving a label over 50 characters with the message under that item only', async () => {
    // when: 51자 이름을 입력하고 저장한다.
    const create = vi.spyOn(gateway.deals, 'create')
    const { user } = await openNew()
    await fillRequired(user)
    fireEvent.change(bantOf('Need'), { target: { value: 'x'.repeat(51) } })

    await save(user)

    const row = bantOf('Need').closest('.kv-row') as HTMLElement

    // then: 그 칸 아래에만 50자 문구가 나오고 저장되지 않는다.
    expect(within(row).getByText(TOO_LONG)).toBeVisible()
    expect(bantOf('Need')).toBeInvalid()
    expect(create).not.toHaveBeenCalled()
    expect(within(bantOf('Budget').closest('.kv-row') as HTMLElement).queryByText(TOO_LONG)).not.toBeInTheDocument()
  })

  // 정확히 50자는 허용한다.
  // 테스트 코드: DE-095
  it('accepts exactly 50 characters', async () => {
    // when: 50자 이름을 입력하고 저장한다.
    const create = vi.spyOn(gateway.deals, 'create')
    const { user, location } = await openNew()
    await fillRequired(user)
    fireEvent.change(bantOf('Need'), { target: { value: 'y'.repeat(50) } })

    await save(user)

    // then: 문구 없이 저장된다.
    await waitFor(() => expect(location()).toMatch(DETAIL_URL))
    expect(create.mock.calls[0]?.[0].bant.need).toEqual({ name: 'y'.repeat(50) })
  })
})

describe('저장', () => {
  // 빈 BANT 칸은 선택 안 함으로 저장된다.
  // 테스트 코드: DE-096
  it('saves blank items as not selected', async () => {
    // when: BANT를 비운 채 저장한다.
    const create = vi.spyOn(gateway.deals, 'create')
    const { user, location } = await openNew()
    await fillRequired(user)

    await save(user)

    // then: 네 구분 모두 선택 안 함이다.
    await waitFor(() => expect(location()).toMatch(DETAIL_URL))
    expect(create.mock.calls[0]?.[0].bant).toEqual({ budget: null, authority: null, need: null, timeline: null })
    const bant = await screen.findByRole('region', { name: 'BANT' })
    expect(within(bant).getByRole('button', { name: 'Budget 수정' })).toHaveTextContent('—')
  })

  // 공백뿐인 칸도 선택 안 함이다.
  // 테스트 코드: DE-096
  it('treats a blank-only item as not selected', async () => {
    // when: 공백만 입력하고 저장한다.
    const create = vi.spyOn(gateway.deals, 'create')
    const { user, location } = await openNew()
    await fillRequired(user)
    await user.type(bantOf('Timeline'), '   ')

    await save(user)

    // then: 그 구분이 선택 안 함이다.
    await waitFor(() => expect(location()).toMatch(DETAIL_URL))
    expect(create.mock.calls[0]?.[0].bant.timeline).toBeNull()
  })

  // 고른 이름은 id로 보낸다(공백만 달라도 같은 Label).
  // 테스트 코드: DE-096
  it('sends the id of a picked label, also when the typed text differs only in spaces', async () => {
    // when: Label 이름을 앞뒤 공백과 함께 입력해 저장한다.
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

    // then: 기존 Label id로 저장되고 새 Label이 없다.
    await waitFor(() => expect(create).toHaveBeenCalledTimes(1))
    expect(create.mock.calls[0]?.[0].bant).toMatchObject({ budget: { id: budget?.id }, authority: { id: authority?.id } })
  })

  // 없는 이름은 그 구분의 새 Label로 저장된다.
  // 테스트 코드: DE-096
  it('sends the name of an unknown label and creates it in that category', async () => {
    // when: 없는 이름을 입력하고 저장한다.
    const create = vi.spyOn(gateway.deals, 'create')
    const { user, location } = await openNew()
    await fillRequired(user)
    await user.type(bantOf('Budget'), '  즉석 예산 라벨  ')

    await save(user)

    // then: 그 구분에 새 Label이 만들어져 Deal이 가리킨다.
    await waitFor(() => expect(location()).toMatch(DETAIL_URL))
    expect(create.mock.calls[0]?.[0].bant.budget).toEqual({ name: '즉석 예산 라벨' })
    const created = (await gateway.labels.list()).find((l) => l.name === '즉석 예산 라벨')
    expect(created).toMatchObject({ category: 'budget', isDefault: false })
    const bant = await screen.findByRole('region', { name: 'BANT' })
    expect(within(bant).getByRole('button', { name: 'Budget 수정' })).toHaveTextContent('즉석 예산 라벨')
  })

  // 같은 새 이름을 다른 구분에도 쓰면 구분마다 Label이 하나씩 생긴다.
  // 테스트 코드: DE-096
  it('allows the same new name in another category and creates one label for each', async () => {
    // when: 두 구분에 같은 새 이름을 입력해 저장한다.
    const { user, location } = await openNew()
    await fillRequired(user)
    await user.type(bantOf('Budget'), '공통 이름')
    await user.type(bantOf('Authority'), '공통 이름')

    await save(user)

    // then: 구분마다 새 Label이 하나씩 생긴다.
    await waitFor(() => expect(location()).toMatch(DETAIL_URL))
    const made = (await gateway.labels.list()).filter((l) => l.name === '공통 이름')
    expect(made.map((l) => l.category).sort()).toEqual(['authority', 'budget'])
  })

  // 뒤의 검증이 실패하면 서버 문구를 보이고 새 Label은 생기지 않는다.
  // 테스트 코드: DE-097
  it('shows the server message and creates no label when a later validation fails', async () => {
    // given: 새 BANT 이름과 서버에서 틀릴 값을 입력했다.
    const { user } = await openNew()
    const before = (await gateway.labels.list()).length
    await fillRequired(user)
    await user.type(bantOf('Need'), '실패할 라벨')
    fireEvent.change(screen.getByLabelText('구매절차'), { target: { value: 'a'.repeat(501) } })

    // when: 저장한다.
    await save(user)

    // then: 서버 문구가 나오고 Label이 늘지 않는다.
    expect(await screen.findByText('구매절차는 500자 이내로 입력하세요.')).toBeVisible()
    expect(await gateway.labels.list()).toHaveLength(before)
    expect(bantOf('Need')).toHaveDisplayValue('실패할 라벨')
  })
})

describe('수정 폼 (R2)', () => {
  // 수정 폼 BANT는 현재 이름으로 채워지고 선택 안 함은 빈 칸이다.
  // 테스트 코드: DE-098
  it('prefills the current label names, and empty for an unselected item', async () => {
    // given: 일부 BANT를 고른 Deal이다.
    const { code } = await openEdit('대한제조 MFA 확대')
    const bant = (await gateway.deals.get(code)).bant
    const labels = await gateway.labels.list()

    // when: 수정 화면을 연다.
    const nameOf = (id: number | null) => (id === null ? '' : (labels.find((l) => l.id === id)?.name ?? '?'))

    // then: 고른 구분은 현재 Label 이름, 나머지는 빈 칸이다.
    await waitFor(() => expect(bantOf('Budget')).toHaveDisplayValue(nameOf(bant.budget)))

    expect(bantOf('Authority')).toHaveDisplayValue(nameOf(bant.authority))
    expect(bantOf('Need')).toHaveDisplayValue(nameOf(bant.need))
    expect(bantOf('Timeline')).toHaveDisplayValue(nameOf(bant.timeline))
    expect([bant.budget, bant.authority, bant.need, bant.timeline].some((id) => id !== null)).toBe(true)
  })

  // 건드리지 않은 칸은 원래 id로 저장된다.
  // 테스트 코드: DE-098
  it('saves untouched items as their current ids', async () => {
    // given: 수정 화면이 열려 있다.
    const update = vi.spyOn(gateway.deals, 'update')

    // when: BANT를 건드리지 않고 저장한다.
    const { user, location, code } = await openEdit('대한제조 MFA 확대')

    // then: BANT 선택과 이력이 그대로다.
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

  // 칸을 비우면 선택 안 함으로 저장된다.
  // 테스트 코드: DE-098
  it('clears an item to not selected when the text is emptied', async () => {
    const { user, location, code } = await openEdit('대한제조 MFA 확대')
    await waitFor(() => expect(bantOf('Budget')).not.toHaveDisplayValue(''))

    // when: BANT 칸을 비우고 저장한다 (전제: 수정 화면이 열려 있다)
    await user.clear(bantOf('Budget'))
    await save(user)

    // then: 그 구분이 선택 안 함이다.
    await waitFor(() => expect(location()).toBe(`/deals/${code}`))
    expect((await gateway.deals.get(code)).bant.budget).toBeNull()
  })

  // 바꾼 칸은 이름으로 저장되고 변경 이력이 남는다.
  // 테스트 코드: DE-098
  it('saves a changed item by name and keeps the history of the change', async () => {
    const { user, location, code } = await openEdit('대한제조 MFA 확대')
    await waitFor(() => expect(bantOf('Budget')).not.toHaveDisplayValue(''))

    // when: BANT 칸을 새 이름으로 바꿔 저장한다 (전제: 수정 화면이 열려 있다)
    await user.clear(bantOf('Timeline'))
    await user.type(bantOf('Timeline'), '내후년 구매 검토')
    await save(user)

    // then: 바뀐 선택이 저장되고 BANT 이력이 남는다.
    await waitFor(() => expect(location()).toBe(`/deals/${code}`))
    const entries = await gateway.history.list(code, { category: 'bant' })
    expect(entries[0]?.after).toContain('내후년 구매 검토')
  })

  // Label 목록을 못 읽으면 BANT를 비활성으로 두고 저장해도 기존 선택을 지킨다.
  // 테스트 코드: DE-099
  it('disables the BANT inputs and shows an error banner when the label list cannot be read, keeping the selection on save', async () => {
    // given: Label 목록 조회가 실패한다.
    const code = await codeOf('대한제조 MFA 확대')
    const before = (await gateway.deals.get(code)).bant
    vi.spyOn(gateway.labels, 'list').mockRejectedValue(
      new ApiError(500, { type: 'https://sales.neoine.test/problems/internal', title: 'x', status: 500, detail: 'Label 목록을 불러오지 못했습니다.' }),
    )
    const { user, location } = await renderAt(`/deals/${code}/edit`)
    await screen.findByRole('heading', { name: 'Deal 수정' })

    // when: 수정 화면에서 다른 필드를 고쳐 저장한다.
    await screen.findByLabelText('Deal Name')

    // then: BANT 칸이 비활성이고 오류 배너가 있으며 기존 선택이 그대로다.
    expect(await screen.findByText('Label 목록을 불러오지 못했습니다.')).toBeVisible()
    for (const category of CATEGORIES) expect(bantOf(category)).toBeDisabled()
    await save(user)

    await waitFor(() => expect(location()).toBe(`/deals/${code}`))
    expect((await gateway.deals.get(code)).bant).toEqual(before)
  })

  // Label 목록을 다시 읽는 중에 저장해도 기존 선택을 지킨다.
  // 테스트 코드: DE-099
  it('keeps the selection when saving while the label list is being re-fetched', async () => {
    // given: Label 목록을 다시 읽는 중이다.
    const update = vi.spyOn(gateway.deals, 'update')

    // when: 다른 필드를 고쳐 저장한다.
    const { user, location, code, client } = await openEdit('대한제조 MFA 확대')

    // then: 기존 BANT 선택이 그대로다.
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
