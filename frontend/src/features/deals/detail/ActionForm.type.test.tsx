import { fireEvent, screen, waitFor, within } from '@testing-library/react'
import { afterEach, describe, expect, it, vi } from 'vitest'
import { gateway } from '../../../gateway'
import { ApiError } from '../../../shared/api/problem'
import { seedActionTypeId } from '../../../test/fake/seed/actionTypes'
import { detailPath } from '../../../test/detailTestUtils'
import { renderAt } from '../../../test/mockApp'

/**
 * Action 등록·수정 폼의 유형 자동완성(AC-24~27)과 표·검색 바의 유형(AC-28).
 * 유형은 텍스트 입력(role combobox) 하나이고, 클릭하면 후보, 타이핑하면 부분 일치 필터, 없으면 직접 입력이다.
 */
afterEach(() => vi.restoreAllMocks())

const HINT = '목록에 없는 유형입니다. 저장하면 새 유형으로 추가됩니다.'
const DEFAULTS = ['통화', '미팅', '이메일', '데모', '제안', '협상', '계약', '기타'] as const

type View = Awaited<ReturnType<typeof renderAt>>

async function openForm(role: 'sales' | 'admin' = 'sales') {
  const view = await renderAt(await detailPath(1), { role })
  await screen.findByRole('heading', { level: 1, name: '한빛은행 ITDR 도입' })
  const table = await screen.findByRole('table', { name: 'Action 목록' })
  await view.user.click(screen.getByRole('button', { name: 'Next Action 업데이트' }))
  const form = screen.getByRole('form', { name: 'Next Action 업데이트' })
  return { ...view, table, form, type: within(form).getByLabelText('유형') }
}

function bodyRows(table: HTMLElement) {
  return within(table).getAllByRole('row').slice(1)
}

/** 유형 후보 목록 안의 항목(검색 바의 유형 select에도 같은 이름의 option이 있어 목록으로 좁힌다). */
const typeOption = async (name: string) => within(await screen.findByRole('listbox', { name: '유형' })).getByRole('option', { name })

const optionNames = () => within(screen.getByRole('listbox', { name: '유형' })).getAllByRole('option').map((o) => o.textContent)

/** 진행사항·Next Action·Due Date를 채운다(유형은 호출자가 정한다). */
async function fillRest(view: View, form: HTMLElement) {
  await view.user.type(within(form).getByLabelText('진행사항'), '후속 연락')
  await view.user.type(within(form).getByLabelText('Next Action'), '견적 재전달')
  fireEvent.change(within(form).getByLabelText('Due Date'), { target: { value: '2026-12-20' } })
}

/** 서버(Fake)에 직접 유형을 만들고 화면의 유형 목록을 다시 읽게 한다. */
async function addTypeBehindTheScenes(view: View, name: string) {
  await gateway.actionTypes.create(name)
  await view.client.invalidateQueries()
}

describe('유형 입력의 모양 (AC-24)', () => {
  it('is one text input with the combobox role and has no select, add button or new-type option', async () => {
    const { form, type } = await openForm()

    expect(type.tagName).toBe('INPUT')
    expect(type).toHaveAttribute('role', 'combobox')
    expect(within(form).getAllByLabelText('유형')).toHaveLength(1)
    expect(within(form).queryByRole('button', { name: /유형.*(추가|만들기)|새 유형/ })).not.toBeInTheDocument()
    expect(within(form).queryByRole('option', { name: /새 유형 만들기/ })).not.toBeInTheDocument()
  })

  it('starts empty on registration and is not required to pick from a list', async () => {
    const { type } = await openForm()

    expect(type).toHaveDisplayValue('')
  })
})

describe('후보 목록과 필터 (AC-25)', () => {
  it('shows every type in the server order when the input is focused', async () => {
    const { user, type } = await openForm()

    await user.click(type)

    await waitFor(() => expect(optionNames()).toEqual(DEFAULTS))
  })

  it('keeps only the types whose name contains the typed text', async () => {
    const { user, type } = await openForm()

    await user.type(type, '데')

    await waitFor(() => expect(optionNames()).toEqual(['데모']))
  })

  it('ignores letter case when filtering and lists custom types after the defaults', async () => {
    const view = await openForm()
    await addTypeBehindTheScenes(view, 'Webinar Live')

    await view.user.click(view.type)
    await waitFor(() => expect(optionNames()).toEqual([...DEFAULTS, 'Webinar Live']))
    await view.user.type(view.type, 'LIVE')

    await waitFor(() => expect(optionNames()).toEqual(['Webinar Live']))
  })

  it('closes the list when nothing matches', async () => {
    const { user, type } = await openForm()

    await user.type(type, '없는유형')

    expect(screen.queryByRole('listbox', { name: '유형' })).not.toBeInTheDocument()
  })

  it('shows the whole list when the typed text equals a type exactly', async () => {
    const { user, type } = await openForm()

    await user.type(type, '미팅')

    await waitFor(() => expect(optionNames()).toEqual(DEFAULTS))
  })

  it('picks with the mouse and fills the name', async () => {
    const { user, type } = await openForm()
    await user.click(type)

    await user.click(await typeOption('데모'))

    expect(type).toHaveDisplayValue('데모')
    expect(screen.queryByRole('listbox', { name: '유형' })).not.toBeInTheDocument()
  })

  it('picks with the arrow keys and Enter without submitting the form', async () => {
    const { user, type } = await openForm()
    await user.click(type)
    await screen.findByRole('listbox', { name: '유형' })

    await user.keyboard('{ArrowDown}{ArrowDown}{Enter}')

    expect(type).toHaveDisplayValue('미팅')
    expect(screen.getByRole('form', { name: 'Next Action 업데이트' })).toBeVisible()
    expect(screen.queryByText('진행사항을 입력하세요.')).not.toBeInTheDocument()
  })

  it('closes the list with Escape', async () => {
    const { user, type } = await openForm()
    await user.click(type)
    await screen.findByRole('listbox', { name: '유형' })

    await user.keyboard('{Escape}')

    expect(screen.queryByRole('listbox', { name: '유형' })).not.toBeInTheDocument()
  })
})

describe('없는 유형 안내와 저장 (AC-26)', () => {
  it('hints that an unknown type will be added, and not for a listed one', async () => {
    const { user, form, type } = await openForm()

    await user.type(type, '웨비나')
    expect(within(form).getByText(HINT)).toBeVisible()

    await user.clear(type)
    await user.type(type, '미팅')
    expect(within(form).queryByText(HINT)).not.toBeInTheDocument()
  })

  it('shows no hint for a blank input', async () => {
    const { user, form, type } = await openForm()

    await user.type(type, '   ')

    expect(within(form).queryByText(HINT)).not.toBeInTheDocument()
  })

  it('sends the name of a new type, registers the action and offers the type next time', async () => {
    const create = vi.spyOn(gateway.actions, 'create')
    const view = await openForm()
    await view.user.type(view.type, '  웨비나  ')
    await fillRest(view, view.form)

    await view.user.click(within(view.form).getByRole('button', { name: '등록' }))

    await waitFor(() => expect(bodyRows(view.table)[0]).toHaveTextContent('웨비나'))
    expect(create.mock.calls[0]?.[1].type).toEqual({ name: '웨비나' })
    await view.user.click(screen.getByRole('button', { name: 'Next Action 업데이트' }))
    await view.user.click(within(screen.getByRole('form', { name: 'Next Action 업데이트' })).getByLabelText('유형'))
    await waitFor(() => expect(optionNames()).toContain('웨비나'))
  })

  it('sends the id of the listed type, also when the case differs', async () => {
    const create = vi.spyOn(gateway.actions, 'create')
    const view = await openForm()
    await addTypeBehindTheScenes(view, 'Webinar')
    const types = await gateway.actionTypes.list()
    await view.user.type(view.type, 'webinar')
    await fillRest(view, view.form)

    await view.user.click(within(view.form).getByRole('button', { name: '등록' }))

    await waitFor(() => expect(bodyRows(view.table)[0]).toHaveTextContent('Webinar'))
    expect(create.mock.calls[0]?.[1].type).toEqual({ id: types.find((t) => t.name === 'Webinar')?.id })
  })

  it('sends the id when a type is picked from the list', async () => {
    const create = vi.spyOn(gateway.actions, 'create')
    const view = await openForm()
    await view.user.click(view.type)
    await view.user.click(await typeOption('데모'))
    await fillRest(view, view.form)

    await view.user.click(within(view.form).getByRole('button', { name: '등록' }))

    await waitFor(() => expect(bodyRows(view.table)[0]).toHaveTextContent('데모'))
    expect(create.mock.calls[0]?.[1].type).toEqual({ id: seedActionTypeId('데모') })
  })

  it('shows the server message and keeps the form when the server refuses the type', async () => {
    const view = await openForm()
    vi.spyOn(gateway.actions, 'create').mockRejectedValue(
      new ApiError(422, {
        type: 'https://sales.neoine.test/problems/validation',
        title: 'x',
        status: 422,
        detail: '선택한 유형이 없습니다. 목록에서 다시 선택하세요.',
      }),
    )
    await view.user.type(view.type, '미팅')
    await fillRest(view, view.form)

    await view.user.click(within(view.form).getByRole('button', { name: '등록' }))

    expect(await within(view.form).findByRole('alert')).toHaveTextContent('선택한 유형이 없습니다. 목록에서 다시 선택하세요.')
    expect(screen.getByRole('form', { name: 'Next Action 업데이트' })).toBeVisible()
  })
})

describe('유형 검증과 수정 폼 (AC-27)', () => {
  it('requires a type before anything else and moves the focus to it', async () => {
    const create = vi.spyOn(gateway.actions, 'create')
    const view = await openForm()

    await view.user.click(within(view.form).getByRole('button', { name: '등록' }))

    expect(within(view.form).getByText('유형을 입력하세요.')).toBeVisible()
    expect(view.type).toHaveFocus()
    expect(view.type).toBeInvalid()
    expect(create).not.toHaveBeenCalled()
  })

  it('treats a blank-only type as empty', async () => {
    const view = await openForm()
    await view.user.type(view.type, '   ')
    await fillRest(view, view.form)

    await view.user.click(within(view.form).getByRole('button', { name: '등록' }))

    expect(within(view.form).getByText('유형을 입력하세요.')).toBeVisible()
  })

  it('rejects a type longer than 50 characters and accepts exactly 50', async () => {
    const create = vi.spyOn(gateway.actions, 'create')
    const view = await openForm()
    await fillRest(view, view.form)

    fireEvent.change(view.type, { target: { value: 'x'.repeat(51) } })
    await view.user.click(within(view.form).getByRole('button', { name: '등록' }))
    expect(within(view.form).getByText('유형은 50자 이내로 입력하세요.')).toBeVisible()
    expect(create).not.toHaveBeenCalled()

    fireEvent.change(view.type, { target: { value: 'y'.repeat(50) } })
    await view.user.click(within(view.form).getByRole('button', { name: '등록' }))
    await waitFor(() => expect(create).toHaveBeenCalledTimes(1))
  })

  it('prefills the current type name when editing and saves a changed one with history', async () => {
    const view = await renderAt(await detailPath(1), { role: 'sales' })
    const table = await screen.findByRole('table', { name: 'Action 목록' })
    await view.user.click(within(bodyRows(table)[0]!).getByRole('button', { name: '수정' }))
    const form = screen.getByRole('form', { name: 'Action 수정' })
    const type = within(form).getByLabelText('유형')
    expect(type).toHaveDisplayValue('협상')

    await view.user.clear(type)
    await view.user.type(type, '현장 점검')
    expect(within(form).getByText(HINT)).toBeVisible()
    await view.user.click(within(form).getByRole('button', { name: '저장' }))

    await waitFor(() => expect(bodyRows(table)[0]).toHaveTextContent('현장 점검'))
    await view.user.click(screen.getByRole('tab', { name: 'Deal History' }))
    expect((await screen.findAllByText(/수정: 현장 점검 · /)).length).toBeGreaterThan(0)
  })

  it('does not ask for a type again when editing and leaving it as it is', async () => {
    const view = await renderAt(await detailPath(1), { role: 'sales' })
    const table = await screen.findByRole('table', { name: 'Action 목록' })
    await view.user.click(within(bodyRows(table)[1]!).getByRole('button', { name: '수정' }))
    const form = screen.getByRole('form', { name: 'Action 수정' })

    await view.user.click(within(form).getByRole('button', { name: '저장' }))

    await waitFor(() => expect(screen.queryByRole('form', { name: 'Action 수정' })).not.toBeInTheDocument())
    expect(screen.getByText('Action이 수정되었습니다.')).toBeVisible()
  })
})

describe('표와 검색 바의 유형 (AC-28)', () => {
  async function openSearch(role: 'sales' | 'admin' = 'sales') {
    const view = await renderAt(await detailPath(1), { role })
    const table = await screen.findByRole('table', { name: 'Action 목록' })
    const search = screen.getByRole('search', { name: 'Action 검색' })
    return { ...view, table, search, select: within(search).getByLabelText('유형') }
  }

  it('lists 전체 and every catalog type as a select whose values are the type ids', async () => {
    const { select } = await openSearch()

    await waitFor(() => expect(within(select).getAllByRole('option')).toHaveLength(9))
    const options = within(select).getAllByRole('option') as HTMLOptionElement[]
    expect(options.map((o) => o.textContent)).toEqual(['전체', ...DEFAULTS])
    expect(options.map((o) => o.value)).toEqual(['', ...DEFAULTS.map((n) => seedActionTypeId(n))])
  })

  it('searches by the chosen type and only its actions remain', async () => {
    const { user, table, search, select } = await openSearch()
    await within(search).findByRole('option', { name: '협상' })

    await user.selectOptions(select, '협상')
    await user.click(within(search).getByRole('button', { name: '검색' }))

    await waitFor(() => expect(bodyRows(table).length).toBeGreaterThan(0))
    for (const row of bodyRows(table)) expect(row).toHaveTextContent('협상')
    expect(bodyRows(table).length).toBeLessThan(4)
  })

  it('offers a type created after the page was opened', async () => {
    const view = await openSearch()
    await addTypeBehindTheScenes(view, '웨비나')

    expect(await within(view.search).findByRole('option', { name: '웨비나' })).toBeInTheDocument()
  })

  it('shows the renamed type in the table and the search after loading again', async () => {
    const view = await openSearch('admin')
    expect(bodyRows(view.table)[0]).toHaveTextContent('협상')

    await gateway.actionTypes.rename(seedActionTypeId('협상'), '가격 협상')
    await view.client.invalidateQueries()

    await waitFor(() => expect(bodyRows(view.table)[0]).toHaveTextContent('가격 협상'))
    expect(await within(view.search).findByRole('option', { name: '가격 협상' })).toBeInTheDocument()
    expect(within(view.search).queryByRole('option', { name: '협상' })).not.toBeInTheDocument()
  })
})
