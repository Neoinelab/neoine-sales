import { fireEvent, screen, waitFor, within } from '@testing-library/react'
import { afterEach, describe, expect, it, vi } from 'vitest'
import { gateway } from '../../../gateway'
import { ApiError } from '../../../shared/api/problem'
import { seedActionTypeId } from '../../../test/fake/seed/actionTypes'
import { detailPath } from '../../../test/detailTestUtils'
import { renderAt } from '../../../test/mockApp'

/**
 * Action 등록·수정 폼의 유형 자동완성과 표·검색 바의 유형.
 * 유형은 텍스트 입력(role combobox) 하나이고, 클릭하면 후보, 타이핑하면 부분 일치 필터, 없으면 직접 입력이다.
 */
afterEach(() => vi.restoreAllMocks())

const HINT = '목록에 없는 유형입니다. 저장하면 새 유형으로 추가됩니다.'
const DEFAULTS = ['통화', '미팅', '이메일', '데모', '제안', '협상', '계약', '기타'] as const

type View = Awaited<ReturnType<typeof renderAt>>

async function openForm(role: 'sales' | 'admin' = 'sales') {
  const view = await renderAt(await detailPath(1, '?tab=actions'), { role })
  await screen.findByRole('heading', { level: 1, name: '한빛은행 ITDR 도입' })
  const table = await screen.findByRole('table', { name: 'Action 목록' })
  await view.user.click(screen.getByRole('button', { name: 'Action 추가' }))
  const form = screen.getByRole('form', { name: 'Action 추가' })
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

describe('유형 입력의 모양', () => {
  // 유형은 combobox 역할의 텍스트 입력 하나이고 선택 상자·추가 버튼·새 유형 항목이 없다.
  // 테스트 코드: AC-074
  it('is one text input with the combobox role and has no select, add button or new-type option', async () => {
    // when: sales가 추가 팝업을 연다
    const { form, type } = await openForm()

    // then: 유형은 combobox 입력 하나이다
    expect(type.tagName).toBe('INPUT')
    expect(type).toHaveAttribute('role', 'combobox')
    expect(within(form).getAllByLabelText('유형')).toHaveLength(1)
    // then: 유형 추가 버튼과 새 유형 항목이 없다
    expect(within(form).queryByRole('button', { name: /유형.*(추가|만들기)|새 유형/ })).not.toBeInTheDocument()
    expect(within(form).queryByRole('option', { name: /새 유형 만들기/ })).not.toBeInTheDocument()
  })

  // 등록 때 유형 칸은 비어 있고 목록에서 고르도록 강제하지 않는다.
  // 테스트 코드: AC-074
  it('starts empty on registration and is not required to pick from a list', async () => {
    // when: sales가 추가 팝업을 연다
    const { type } = await openForm()

    // then: 유형 칸이 비어 있다
    expect(type).toHaveDisplayValue('')
  })
})

describe('후보 목록과 필터', () => {
  // 입력에 포커스를 주면 서버 순서의 모든 유형이 후보로 나온다.
  // 테스트 코드: AC-078
  it('shows every type in the server order when the input is focused', async () => {
    // given: sales가 추가 팝업을 연다
    const { user, type } = await openForm()

    // when: 유형 칸을 누른다
    await user.click(type)

    // then: 후보가 서버 순서의 기본 유형이다
    await waitFor(() => expect(optionNames()).toEqual(DEFAULTS))
  })

  // 입력한 글자를 이름에 포함하는 유형만 남는다.
  // 테스트 코드: AC-078
  it('keeps only the types whose name contains the typed text', async () => {
    // given: sales가 추가 팝업을 연다
    const { user, type } = await openForm()

    // when: "데"를 입력한다
    await user.type(type, '데')

    // then: 후보는 "데모"뿐이다
    await waitFor(() => expect(optionNames()).toEqual(['데모']))
  })

  // 대소문자를 무시하고 걸러내며 만든 유형은 기본 유형 뒤에 나온다.
  // 테스트 코드: AC-078
  it('ignores letter case when filtering and lists custom types after the defaults', async () => {
    // given: 추가 팝업을 연 뒤 서버에 "Webinar Live" 유형이 생겼다
    const view = await openForm()
    await addTypeBehindTheScenes(view, 'Webinar Live')

    // when: 유형 칸을 누른다
    await view.user.click(view.type)
    // then: 기본 유형 뒤에 새 유형이 나온다
    await waitFor(() => expect(optionNames()).toEqual([...DEFAULTS, 'Webinar Live']))
    // when: "LIVE"를 입력한다
    await view.user.type(view.type, 'LIVE')

    // then: 후보는 "Webinar Live"뿐이다
    await waitFor(() => expect(optionNames()).toEqual(['Webinar Live']))
  })

  // 맞는 후보가 없으면 목록이 닫힌다.
  // 테스트 코드: AC-078
  it('closes the list when nothing matches', async () => {
    // given: sales가 추가 팝업을 연다
    const { user, type } = await openForm()

    // when: 없는 유형을 입력한다
    await user.type(type, '없는유형')

    // then: 후보 목록이 없다
    expect(screen.queryByRole('listbox', { name: '유형' })).not.toBeInTheDocument()
  })

  // 입력이 어떤 유형과 정확히 같으면 전체 목록을 보인다.
  // 테스트 코드: AC-078
  it('shows the whole list when the typed text equals a type exactly', async () => {
    // given: sales가 추가 팝업을 연다
    const { user, type } = await openForm()

    // when: "미팅"을 입력한다
    await user.type(type, '미팅')

    // then: 후보는 전체 유형이다
    await waitFor(() => expect(optionNames()).toEqual(DEFAULTS))
  })

  // 마우스로 고르면 이름이 채워지고 목록이 닫힌다.
  // 테스트 코드: AC-078
  it('picks with the mouse and fills the name', async () => {
    // given: sales가 추가 팝업에서 후보 목록을 연다
    const { user, type } = await openForm()
    await user.click(type)

    // when: "데모"를 누른다
    await user.click(await typeOption('데모'))

    // then: 입력에 "데모"가 채워지고 목록이 닫힌다
    expect(type).toHaveDisplayValue('데모')
    expect(screen.queryByRole('listbox', { name: '유형' })).not.toBeInTheDocument()
  })

  // 방향키와 Enter로 고르면 폼이 제출되지 않는다.
  // 테스트 코드: AC-078
  it('picks with the arrow keys and Enter without submitting the form', async () => {
    // given: sales가 추가 팝업에서 후보 목록을 연다
    const { user, type } = await openForm()
    await user.click(type)
    await screen.findByRole('listbox', { name: '유형' })

    // when: 아래 방향키 두 번과 Enter를 누른다
    await user.keyboard('{ArrowDown}{ArrowDown}{Enter}')

    // then: 입력에 "미팅"이 채워진다
    expect(type).toHaveDisplayValue('미팅')
    // then: 폼은 그대로이고 검증 문구가 없다
    expect(screen.getByRole('form', { name: 'Action 추가' })).toBeVisible()
    expect(screen.queryByText('진행사항을 입력하세요.')).not.toBeInTheDocument()
  })

  // Esc는 후보 목록을 닫는다.
  // 테스트 코드: AC-085
  it('closes the list with Escape', async () => {
    // given: sales가 추가 팝업에서 후보 목록을 연다
    const { user, type } = await openForm()
    await user.click(type)
    await screen.findByRole('listbox', { name: '유형' })

    // when: Esc를 누른다
    await user.keyboard('{Escape}')

    // then: 후보 목록이 닫힌다
    expect(screen.queryByRole('listbox', { name: '유형' })).not.toBeInTheDocument()
  })

  // Esc는 후보만 닫고 Action 팝업은 닫지 않는다.
  // 테스트 코드: AC-085
  it('escape closes the type suggestions but not the dialog', async () => {
    // given: sales가 추가 팝업에서 "미"를 입력해 후보 목록이 열렸다
    const { user, type } = await openForm()
    await user.type(type, '미')
    await screen.findByRole('listbox', { name: '유형' })

    // when: Esc를 누른다
    await user.keyboard('{Escape}')

    // then: 후보 목록만 닫히고 팝업과 입력은 남는다
    expect(screen.queryByRole('listbox', { name: '유형' })).not.toBeInTheDocument()
    expect(screen.getByRole('dialog', { name: 'Action 추가' })).toBeVisible()
    expect(type).toHaveDisplayValue('미')
  })
})

describe('없는 유형 안내와 저장', () => {
  // 목록에 없는 유형에만 새 유형 안내가 나온다.
  // 테스트 코드: AC-078
  it('hints that an unknown type will be added, and not for a listed one', async () => {
    // given: sales가 추가 팝업을 연다
    const { user, form, type } = await openForm()

    // when: 목록에 없는 "웨비나"를 입력한다
    await user.type(type, '웨비나')
    // then: 새 유형 안내가 보인다
    expect(within(form).getByText(HINT)).toBeVisible()

    // when: 목록에 있는 "미팅"으로 바꾼다
    await user.clear(type)
    await user.type(type, '미팅')
    // then: 안내가 사라진다
    expect(within(form).queryByText(HINT)).not.toBeInTheDocument()
  })

  // 공백뿐인 입력에는 안내가 없다.
  // 테스트 코드: AC-078
  it('shows no hint for a blank input', async () => {
    // given: sales가 추가 팝업을 연다
    const { user, form, type } = await openForm()

    // when: 공백만 입력한다
    await user.type(type, '   ')

    // then: 새 유형 안내가 없다
    expect(within(form).queryByText(HINT)).not.toBeInTheDocument()
  })

  // 새 유형은 이름으로 보내 등록하고 다음 팝업 후보에 나온다.
  // 테스트 코드: AC-078
  it('sends the name of a new type, registers the action and offers the type next time', async () => {
    // given: sales가 추가 팝업을 열고 새 유형 이름과 나머지를 입력한다(요청 감시)
    const create = vi.spyOn(gateway.actions, 'create')
    const view = await openForm()
    await view.user.type(view.type, '  웨비나  ')
    await fillRest(view, view.form)

    // when: 등록을 누른다
    await view.user.click(within(view.form).getByRole('button', { name: '등록' }))

    // then: 새 Action 행에 "웨비나"가 보인다
    await waitFor(() => expect(bodyRows(view.table)[0]).toHaveTextContent('웨비나'))
    // then: 요청의 유형은 이름 객체(공백 제거)다
    expect(create.mock.calls[0]?.[1].type).toEqual({ name: '웨비나' })
    // when: 추가 팝업을 다시 열어 유형 칸을 누른다
    await view.user.click(screen.getByRole('button', { name: 'Action 추가' }))
    await view.user.click(within(screen.getByRole('form', { name: 'Action 추가' })).getByLabelText('유형'))
    // then: 후보에 "웨비나"가 있다
    await waitFor(() => expect(optionNames()).toContain('웨비나'))
  })

  // 목록의 유형은 대소문자가 달라도 id로 보낸다.
  // 테스트 코드: AC-078
  it('sends the id of the listed type, also when the case differs', async () => {
    // given: 서버에 "Webinar"가 있고 추가 팝업에 소문자로 입력했다(요청 감시)
    const create = vi.spyOn(gateway.actions, 'create')
    const view = await openForm()
    await addTypeBehindTheScenes(view, 'Webinar')
    const types = await gateway.actionTypes.list()
    await view.user.type(view.type, 'webinar')
    await fillRest(view, view.form)

    // when: 등록을 누른다
    await view.user.click(within(view.form).getByRole('button', { name: '등록' }))

    // then: 행에 "Webinar"가 보인다
    await waitFor(() => expect(bodyRows(view.table)[0]).toHaveTextContent('Webinar'))
    // then: 요청의 유형은 그 유형의 id 객체다
    expect(create.mock.calls[0]?.[1].type).toEqual({ id: types.find((t) => t.name === 'Webinar')?.id })
  })

  // 후보에서 고르면 id로 보낸다.
  // 테스트 코드: AC-078
  it('sends the id when a type is picked from the list', async () => {
    // given: sales가 추가 팝업을 열고(요청 감시)
    const create = vi.spyOn(gateway.actions, 'create')
    const view = await openForm()
    // when: 후보에서 "데모"를 골라 나머지를 입력하고 등록한다
    await view.user.click(view.type)
    await view.user.click(await typeOption('데모'))
    await fillRest(view, view.form)

    await view.user.click(within(view.form).getByRole('button', { name: '등록' }))

    // then: 행에 "데모"가 보인다
    await waitFor(() => expect(bodyRows(view.table)[0]).toHaveTextContent('데모'))
    // then: 요청의 유형은 데모의 id 객체다
    expect(create.mock.calls[0]?.[1].type).toEqual({ id: seedActionTypeId('데모') })
  })

  // 서버가 유형을 거절하면 그 문구를 폼 안에 보이고 폼을 유지한다.
  // 테스트 코드: AC-078
  it('shows the server message and keeps the form when the server refuses the type', async () => {
    // given: 서버가 유형을 거절하도록 한 추가 팝업과 입력
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

    // when: 등록을 누른다
    await view.user.click(within(view.form).getByRole('button', { name: '등록' }))

    // then: 폼 안 배너에 서버 문구가 보인다
    expect(await within(view.form).findByRole('alert')).toHaveTextContent('선택한 유형이 없습니다. 목록에서 다시 선택하세요.')
    // then: 폼이 그대로 열려 있다
    expect(screen.getByRole('form', { name: 'Action 추가' })).toBeVisible()
  })
})

describe('유형 검증과 수정 폼', () => {
  // 유형이 비어 있으면 무엇보다 먼저 막고 유형 칸에 포커스한다.
  // 테스트 코드: AC-075
  it('requires a type before anything else and moves the focus to it', async () => {
    // given: sales가 추가 팝업을 연다(요청 감시)
    const create = vi.spyOn(gateway.actions, 'create')
    const view = await openForm()

    // when: 모든 칸을 비우고 등록을 누른다
    await view.user.click(within(view.form).getByRole('button', { name: '등록' }))

    // then: 유형 문구가 보이고 유형 칸에 포커스·오류 표시가 있다
    expect(within(view.form).getByText('유형을 입력하세요.')).toBeVisible()
    expect(view.type).toHaveFocus()
    expect(view.type).toBeInvalid()
    // then: 등록 요청이 없다
    expect(create).not.toHaveBeenCalled()
  })

  // 공백뿐인 유형은 빈 값으로 본다.
  // 테스트 코드: AC-075
  it('treats a blank-only type as empty', async () => {
    // given: sales가 추가 팝업에서 유형에 공백만 넣고 나머지를 채운다
    const view = await openForm()
    await view.user.type(view.type, '   ')
    await fillRest(view, view.form)

    // when: 등록을 누른다
    await view.user.click(within(view.form).getByRole('button', { name: '등록' }))

    // then: 유형 문구가 보인다
    expect(within(view.form).getByText('유형을 입력하세요.')).toBeVisible()
  })

  // 유형은 51자부터 거절하고 50자는 받는다.
  // 테스트 코드: AC-075
  it('rejects a type longer than 50 characters and accepts exactly 50', async () => {
    // given: sales가 추가 팝업에서 나머지를 채운다(요청 감시)
    const create = vi.spyOn(gateway.actions, 'create')
    const view = await openForm()
    await fillRest(view, view.form)

    // when: 유형을 51자로 하고 등록을 누른다
    fireEvent.change(view.type, { target: { value: 'x'.repeat(51) } })
    await view.user.click(within(view.form).getByRole('button', { name: '등록' }))
    // then: 길이 문구가 보이고 요청이 없다
    expect(within(view.form).getByText('유형은 50자 이내로 입력하세요.')).toBeVisible()
    expect(create).not.toHaveBeenCalled()

    // when: 유형을 50자로 하고 등록을 누른다
    fireEvent.change(view.type, { target: { value: 'y'.repeat(50) } })
    await view.user.click(within(view.form).getByRole('button', { name: '등록' }))
    // then: 등록 요청이 한 번 간다
    await waitFor(() => expect(create).toHaveBeenCalledTimes(1))
  })

  // 수정 폼은 현재 유형 이름을 채우고 바꾼 이름은 이력과 함께 저장한다.
  // 테스트 코드: AC-086
  it('prefills the current type name when editing and saves a changed one with history', async () => {
    // given: sales가 Actions 탭에서 첫 행의 수정 팝업을 연다
    const view = await renderAt(await detailPath(1, '?tab=actions'), { role: 'sales' })
    const table = await screen.findByRole('table', { name: 'Action 목록' })
    await view.user.click(within(bodyRows(table)[0]!).getByRole('button', { name: '수정' }))
    const form = screen.getByRole('form', { name: 'Action 수정' })
    const type = within(form).getByLabelText('유형')
    // then: 유형 칸에 현재 이름이 채워져 있다
    expect(type).toHaveDisplayValue('협상')

    // when: 새 유형 이름으로 바꾸고 저장한다
    await view.user.clear(type)
    await view.user.type(type, '현장 점검')
    // then: 새 유형 안내가 보인다
    expect(within(form).getByText(HINT)).toBeVisible()
    await view.user.click(within(form).getByRole('button', { name: '저장' }))

    // then: 행의 유형이 바뀐다
    await waitFor(() => expect(bodyRows(table)[0]).toHaveTextContent('현장 점검'))
    // when: Deal History 탭으로 간다
    await view.user.click(screen.getByRole('tab', { name: 'Deal History' }))
    // then: "수정: 현장 점검 · " 이력이 있다
    expect((await screen.findAllByText(/수정: 현장 점검 · /)).length).toBeGreaterThan(0)
  })

  // 수정 폼에서 유형을 그대로 두면 다시 묻지 않고 저장된다.
  // 테스트 코드: AC-086
  it('does not ask for a type again when editing and leaving it as it is', async () => {
    // given: sales가 Actions 탭에서 둘째 행의 수정 팝업을 연다
    const view = await renderAt(await detailPath(1, '?tab=actions'), { role: 'sales' })
    const table = await screen.findByRole('table', { name: 'Action 목록' })
    await view.user.click(within(bodyRows(table)[1]!).getByRole('button', { name: '수정' }))
    const form = screen.getByRole('form', { name: 'Action 수정' })

    // when: 아무것도 고치지 않고 저장한다
    await view.user.click(within(form).getByRole('button', { name: '저장' }))

    // then: 팝업이 닫히고 수정 알림이 보인다
    await waitFor(() => expect(screen.queryByRole('dialog', { name: 'Action 수정' })).not.toBeInTheDocument())
    expect(screen.getByText('Action이 수정되었습니다.')).toBeVisible()
  })
})

describe('표와 검색 바의 유형', () => {
  async function openSearch(role: 'sales' | 'admin' = 'sales') {
    const view = await renderAt(await detailPath(1, '?tab=actions'), { role })
    const table = await screen.findByRole('table', { name: 'Action 목록' })
    const search = screen.getByRole('search', { name: 'Action 검색' })
    return { ...view, table, search, select: within(search).getByLabelText('유형') }
  }

  // 검색 바의 유형 선택 상자는 전체와 카탈로그 유형을 id 값으로 가진다.
  it('lists 전체 and every catalog type as a select whose values are the type ids', async () => {
    // when: sales가 Actions 탭을 연다
    const { select } = await openSearch()

    // then: 전체와 모든 유형이 option으로 있다
    await waitFor(() => expect(within(select).getAllByRole('option')).toHaveLength(9))
    // then: option 값이 유형 id다
    const options = within(select).getAllByRole('option') as HTMLOptionElement[]
    expect(options.map((o) => o.textContent)).toEqual(['전체', ...DEFAULTS])
    expect(options.map((o) => o.value)).toEqual(['', ...DEFAULTS.map((n) => String(seedActionTypeId(n)))])
  })

  // 고른 유형으로 검색하면 그 유형의 Action만 남는다.
  // 테스트 코드: NA-053
  it('searches by the chosen type and only its actions remain', async () => {
    // given: sales가 Actions 탭을 연다
    const { user, table, search, select } = await openSearch()
    await within(search).findByRole('option', { name: '협상' })

    // when: 유형 "협상"으로 검색한다
    await user.selectOptions(select, '협상')
    await user.click(within(search).getByRole('button', { name: '검색' }))

    // then: 협상 행만 남는다
    await waitFor(() => expect(bodyRows(table).length).toBeGreaterThan(0))
    for (const row of bodyRows(table)) expect(row).toHaveTextContent('협상')
    expect(bodyRows(table).length).toBeLessThan(4)
  })

  // 화면을 연 뒤 만든 유형도 검색 바에 나온다.
  // 테스트 코드: CL-093
  it('offers a type created after the page was opened', async () => {
    // given: sales가 Actions 탭을 연다
    const view = await openSearch()
    // when: 서버에 "웨비나" 유형이 생겨 목록이 다시 읽힌다
    await addTypeBehindTheScenes(view, '웨비나')

    // then: 검색 바에 "웨비나" option이 있다
    expect(await within(view.search).findByRole('option', { name: '웨비나' })).toBeInTheDocument()
  })

  // 이름이 바뀐 유형은 다시 읽은 뒤 표와 검색 바에 새 이름으로 나온다.
  // 테스트 코드: CL-093
  it('shows the renamed type in the table and the search after loading again', async () => {
    // given: admin이 Actions 탭을 연다
    const view = await openSearch('admin')
    expect(bodyRows(view.table)[0]).toHaveTextContent('협상')

    // when: 유형 이름을 바꾸고 목록을 다시 읽는다
    await gateway.actionTypes.rename(seedActionTypeId('협상'), '가격 협상')
    await view.client.invalidateQueries()

    // then: 표 행에 새 이름이 보인다
    await waitFor(() => expect(bodyRows(view.table)[0]).toHaveTextContent('가격 협상'))
    // then: 검색 바에 새 이름이 있고 옛 이름은 없다
    expect(await within(view.search).findByRole('option', { name: '가격 협상' })).toBeInTheDocument()
    expect(within(view.search).queryByRole('option', { name: '협상' })).not.toBeInTheDocument()
  })
})
