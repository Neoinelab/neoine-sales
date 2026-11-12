import { screen, waitFor, within } from '@testing-library/react'
import { describe, expect, it } from 'vitest'
import { gateway } from '../../../gateway'
import { renderAt } from '../../../test/mockApp'
import { NO_SUCH_ID } from '../../../test/fake/seed/ids'

const GUIDE = '같은 이름은 만들 수 없습니다(대소문자 구분 없음). 사용 중인 유형은 이름을 바꿀 수 있지만 삭제할 수 없습니다.'
const DEFAULTS = ['통화', '미팅', '이메일', '데모', '제안', '협상', '계약', '기타']

type View = Awaited<ReturnType<typeof renderAt>>

async function openTypes(role: 'admin' | 'sales' = 'admin') {
  const view = await renderAt('/admin/deal?tab=action-type', { role })
  await screen.findByRole('table', { name: 'Action 유형 목록' })
  await screen.findByText('협상')
  return view
}

const table = () => screen.getByRole('table', { name: 'Action 유형 목록' })
const typeRow = (name: string) => within(within(table()).getByRole('row', { name: new RegExp(name) }))

async function addType(user: View['user'], name: string) {
  const form = screen.getByRole('form', { name: 'Action 유형 추가' })
  await user.type(within(form).getByLabelText('새 유형 이름'), name)
  await user.click(within(form).getByRole('button', { name: '추가' }))
}

describe('Action 유형 탭 위치', () => {
  // Action 유형 탭은 BANT Label 탭 바로 뒤에 놓이고 ?tab=action-type 주소로 열리면 선택된다.
  // 테스트 코드: CL-077
  it('is the tab right after BANT Label, opened by ?tab=action-type', async () => {
    // when: ?tab=action-type 주소로 연다
    await openTypes()

    // then: 유형 탭이 BANT Label 바로 뒤이고 선택되어 있다
    const tabs = screen.getAllByRole('tab').map((t) => t.textContent)
    expect(tabs.indexOf('Action 유형')).toBe(tabs.indexOf('BANT Label') + 1)
    expect(screen.getByRole('tab', { name: 'Action 유형' })).toHaveAttribute('aria-selected', 'true')
  })

  // 탭을 누르면 유형 탭이 열리고 주소가 ?tab=action-type으로 바뀐다.
  // 테스트 코드: CL-077
  it('switches to the tab by clicking it and keeps ?tab=action-type in the address', async () => {
    // given: 탭 없이 Deal 관리 화면을 연다
    const { user, location } = await renderAt('/admin/deal', { role: 'admin' })

    // when: Action 유형 탭을 누른다
    await user.click(await screen.findByRole('tab', { name: 'Action 유형' }))

    // then: 유형 표가 보이고 주소가 ?tab=action-type이다
    await screen.findByRole('table', { name: 'Action 유형 목록' })
    expect(location()).toBe('/admin/deal?tab=action-type')
  })

  // 유형 탭은 이름 규칙과 삭제 제한을 안내한다.
  // 테스트 코드: CL-083
  it('shows the guide sentence', async () => {
    // when: 유형 탭을 연다
    await openTypes()

    // then: 안내 문구가 보인다
    expect(screen.getByText(GUIDE)).toBeVisible()
  })
})

describe('Action 유형 목록', () => {
  // 기본 유형이 시드 순서로 '기본' 배지와 사용 Action 수와 함께 나온다.
  // 테스트 코드: CL-083
  it('lists the default types in order, marked as default, with the usage count', async () => {
    // when: 유형 탭을 연다
    await openTypes()

    // then: 기본 8개가 순서대로 있고 배지와 'Action n건'이 보인다
    const names = within(table())
      .getAllByRole('row')
      .slice(1)
      .map((r) => r.textContent ?? '')
    expect(DEFAULTS.every((name, i) => names[i]?.includes(name))).toBe(true)
    expect(typeRow('협상').getByText('기본')).toBeInTheDocument()
    expect(typeRow('협상').getByText(/Action [1-9]\d*건/)).toBeInTheDocument()
    expect(typeRow('계약').getByText(/Action \d+건/)).toBeInTheDocument()
  })

  // 사용자가 만든 유형은 배지 없이 만든 사람과 'Action 0건'을 보인다.
  // 테스트 코드: CL-083
  it('shows the creator of a type made by a user', async () => {
    // given: 유형 탭이 열려 있다
    const { user } = await openTypes()

    // when: '웨비나'를 추가한다
    await addType(user, '웨비나')

    // then: 배지 없이 만든 사람과 'Action 0건'이 보인다
    expect(await within(table()).findByText('웨비나')).toBeInTheDocument()
    const row = typeRow('웨비나')
    expect(row.queryByText('기본')).not.toBeInTheDocument()
    expect(row.getByText(/최관리/)).toBeInTheDocument()
    expect(row.getByText('Action 0건')).toBeInTheDocument()
  })
})

describe('Action 유형 추가', () => {
  // 유형을 추가하면 기본 유형 뒤에 나타나고 입력이 비워진다.
  // 테스트 코드: CL-084
  it('adds a type, shows it after the defaults and clears the input', async () => {
    // given: 유형 탭이 열려 있다
    const { user } = await openTypes()

    // when: '웨비나'를 추가한다
    await addType(user, '웨비나')

    // then: 표 끝에 나타나고 입력은 비어 있다
    expect(await within(table()).findByText('웨비나')).toBeInTheDocument()
    expect(screen.getByLabelText('새 유형 이름')).toHaveValue('')
    const rows = within(table()).getAllByRole('row').slice(1)
    expect(rows[rows.length - 1]).toHaveTextContent('웨비나')
  })

  // 대소문자만 다른 중복 이름은 서버 문구가 배너에 보인다.
  // 테스트 코드: CL-084
  it('rejects a duplicate ignoring case with the server message in the error banner', async () => {
    // given: 'Webinar' 유형이 있다
    const { user } = await openTypes()
    await addType(user, 'Webinar')
    await within(table()).findByText('Webinar')

    // when: 'webinar'를 추가한다
    await addType(user, 'webinar')

    // then: 중복 문구가 배너에 보인다
    expect(await screen.findByRole('alert')).toHaveTextContent('이미 있는 유형 이름입니다.')
  })

  // 빈 이름과 51자 이름의 추가는 서버 문구를 배너에 보인다.
  // 테스트 코드: CL-084
  it('shows the server messages for an empty name and a name over 50 characters', async () => {
    // given: 유형 탭이 열려 있다
    const { user } = await openTypes()

    // when: 빈 이름으로, 이어 51자 이름으로 추가한다
    await user.click(within(screen.getByRole('form', { name: 'Action 유형 추가' })).getByRole('button', { name: '추가' }))
    // then: 필수 문구, 이어 길이 문구가 배너에 보인다
    expect(await screen.findByRole('alert')).toHaveTextContent('유형을 입력하세요.')

    await addType(user, 'x'.repeat(51))
    await waitFor(() => expect(screen.getByRole('alert')).toHaveTextContent('유형은 50자 이내로 입력하세요.'))
  })
})

describe('Action 유형 이름 수정', () => {
  // Action이 쓰는 기본 유형도 이름을 바꿔 저장하면 표에 새 이름이 보인다.
  // 테스트 코드: CL-085
  it('renames a default type that actions use', async () => {
    // given: 유형 탭이 열려 있다
    const { user } = await openTypes()

    // when: '협상'의 이름 수정에서 '가격 협상'으로 저장한다
    await user.click(typeRow('협상').getByRole('button', { name: '이름 수정' }))
    const input = screen.getByLabelText('유형 이름')
    await user.clear(input)
    await user.type(input, '가격 협상')
    await user.click(screen.getByRole('button', { name: '저장' }))

    // then: 새 이름이 보이고 옛 이름은 없다
    expect(await within(table()).findByText('가격 협상')).toBeInTheDocument()
    expect(within(table()).queryByText('협상')).not.toBeInTheDocument()
  })

  // 자기 이름의 대소문자만 바꾸는 것은 저장된다.
  // 테스트 코드: CL-085
  it('allows changing only the case of its own name', async () => {
    // given: 'Webinar' 유형이 있다
    const { user } = await openTypes()
    await addType(user, 'Webinar')
    await within(table()).findByText('Webinar')

    // when: 'WEBINAR'로 바꿔 저장한다
    await user.click(typeRow('Webinar').getByRole('button', { name: '이름 수정' }))
    const input = screen.getByLabelText('유형 이름')
    await user.clear(input)
    await user.type(input, 'WEBINAR')
    await user.click(screen.getByRole('button', { name: '저장' }))

    // then: 'WEBINAR'가 보인다
    expect(await within(table()).findByText('WEBINAR')).toBeInTheDocument()
  })

  // 다른 유형의 이름으로 바꾸면 서버 문구가 배너에 보인다.
  // 테스트 코드: CL-085
  it('refuses a name that another type has and shows the server message', async () => {
    // given: 유형 탭이 열려 있다
    const { user } = await openTypes()

    // when: '협상'을 '미팅'으로 바꿔 저장한다
    await user.click(typeRow('협상').getByRole('button', { name: '이름 수정' }))
    const input = screen.getByLabelText('유형 이름')
    await user.clear(input)
    await user.type(input, '미팅')
    await user.click(screen.getByRole('button', { name: '저장' }))

    // then: 중복 문구가 배너에 보인다
    expect(await screen.findByRole('alert')).toHaveTextContent('이미 있는 유형 이름입니다.')
  })

  // 이름 수정을 취소하면 이름이 바뀌지 않고 입력이 닫힌다.
  // 테스트 코드: CL-085
  it('cancels the rename without changing the name', async () => {
    // given: 유형 탭이 열려 있다
    const { user } = await openTypes()

    // when: 이름 수정에서 글자를 더 입력하고 취소한다
    await user.click(typeRow('협상').getByRole('button', { name: '이름 수정' }))
    await user.type(screen.getByLabelText('유형 이름'), ' 변경')
    await user.click(screen.getByRole('button', { name: '취소' }))

    // then: 이름은 그대로이고 입력 칸이 없다
    expect(within(table()).getByText('협상')).toBeInTheDocument()
    expect(screen.queryByLabelText('유형 이름')).not.toBeInTheDocument()
  })
})

describe('Action 유형 삭제', () => {
  // 삭제 확인 창에 유형 이름이 보이고 확인하면 쓰이지 않는 유형이 사라진다.
  // 테스트 코드: CL-086
  it('asks with the type name and deletes an unused type', async () => {
    // given: 쓰이지 않는 '임시 유형'을 추가했다
    const { user } = await openTypes()
    await addType(user, '임시 유형')
    await within(table()).findByText('임시 유형')

    // when: 삭제 버튼을 눌러 확인 창에서 삭제한다
    await user.click(typeRow('임시 유형').getByRole('button', { name: '삭제' }))
    // then: 확인 창 문구가 맞고 유형이 사라진다
    const dialog = await screen.findByRole('dialog', { name: '유형 삭제' })
    expect(dialog).toHaveTextContent("'임시 유형' 유형을 삭제할까요? 사용 중인 유형은 삭제할 수 없습니다.")
    await user.click(within(dialog).getByRole('button', { name: '삭제' }))

    await waitFor(() => expect(within(table()).queryByText('임시 유형')).not.toBeInTheDocument())
  })

  // 삭제 확인에서 취소하면 유형이 남는다.
  // 테스트 코드: CL-086
  it('keeps the type when the confirmation is declined', async () => {
    // given: '임시 유형'을 추가했다
    const { user } = await openTypes()
    await addType(user, '임시 유형')
    await within(table()).findByText('임시 유형')

    // when: 삭제 버튼을 누르고 확인 창에서 취소한다
    await user.click(typeRow('임시 유형').getByRole('button', { name: '삭제' }))
    await user.click(within(await screen.findByRole('dialog')).getByRole('button', { name: '취소' }))

    // then: 유형이 그대로 있다
    expect(within(table()).getByText('임시 유형')).toBeInTheDocument()
  })

  // Action이 쓰는 유형을 지우면 건수가 든 서버 문구가 배너에 보이고 유형은 남는다.
  // 테스트 코드: CL-086
  it('shows the 409 message with the count when the type is in use and keeps the type', async () => {
    // given: 유형 탭이 열려 있다
    const { user } = await openTypes()

    // when: 사용 중인 '협상'을 삭제 확인한다
    await user.click(typeRow('협상').getByRole('button', { name: '삭제' }))
    await user.click(within(await screen.findByRole('dialog')).getByRole('button', { name: '삭제' }))

    // then: '(Action n건)' 문구가 배너에 보이고 유형이 남는다
    expect(await screen.findByRole('alert')).toHaveTextContent(/사용 중인 유형은 삭제할 수 없습니다\. \(Action \d+건\)/)
    expect(within(table()).getByText('협상')).toBeInTheDocument()
  })

  // 쓰던 Action이 모두 지워지면 기본 유형도 삭제된다.
  // 테스트 코드: CL-086
  it('can delete a default type once no action uses it', async () => {
    // given: '기타'를 쓰던 Action을 모두 지웠다
    const { user, client } = await openTypes()
    const target = (await gateway.actionTypes.list()).find((t) => t.name === '기타')
    const deals = await gateway.deals.list({ limit: 100 })
    for (const deal of deals.items) {
      for (const action of await gateway.actions.list(deal.code, { typeId: target?.id ?? NO_SUCH_ID })) await gateway.actions.remove(action.id)
    }
    await client.invalidateQueries()
    await waitFor(() => expect(typeRow('기타').getByText('Action 0건')).toBeInTheDocument())

    // when: '기타'를 삭제 확인한다
    await user.click(typeRow('기타').getByRole('button', { name: '삭제' }))
    await user.click(within(await screen.findByRole('dialog')).getByRole('button', { name: '삭제' }))

    // then: 표에서 사라진다
    await waitFor(() => expect(within(table()).queryByText('기타')).not.toBeInTheDocument())
  })
})

describe('Action 유형 권한', () => {
  // sales는 유형을 만들 수 있지만 이름 변경·삭제는 403이다.
  // 테스트 코드: CL-090
  it('lets only the admin reach the admin page, so sales cannot rename or delete (403 at the gateway)', async () => {
    // given: sales로 로그인한다
    await renderAt('/deals', { role: 'sales' })
    // when: 유형을 만든 뒤 이름 변경·삭제를 요청한다
    const created = await gateway.actionTypes.create('영업이 만든 유형')

    // then: 이름 변경·삭제는 403으로 거절된다
    await expect(gateway.actionTypes.rename(created.id, '바꾼 이름')).rejects.toMatchObject({ status: 403 })
    await expect(gateway.actionTypes.remove(created.id)).rejects.toMatchObject({ status: 403 })
  })
})
