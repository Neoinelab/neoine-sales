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

describe('Action 유형 탭 위치 (AC-29)', () => {
  it('is the tab right after BANT Label, opened by ?tab=action-type', async () => {
    await openTypes()

    const tabs = screen.getAllByRole('tab').map((t) => t.textContent)
    expect(tabs.indexOf('Action 유형')).toBe(tabs.indexOf('BANT Label') + 1)
    expect(screen.getByRole('tab', { name: 'Action 유형' })).toHaveAttribute('aria-selected', 'true')
  })

  it('switches to the tab by clicking it and keeps ?tab=action-type in the address', async () => {
    const { user, location } = await renderAt('/admin/deal', { role: 'admin' })

    await user.click(await screen.findByRole('tab', { name: 'Action 유형' }))

    await screen.findByRole('table', { name: 'Action 유형 목록' })
    expect(location()).toBe('/admin/deal?tab=action-type')
  })

  it('shows the guide sentence', async () => {
    await openTypes()

    expect(screen.getByText(GUIDE)).toBeVisible()
  })
})

describe('Action 유형 목록 (AC-29)', () => {
  it('lists the default types in order, marked as default, with the usage count', async () => {
    await openTypes()

    const names = within(table())
      .getAllByRole('row')
      .slice(1)
      .map((r) => r.textContent ?? '')
    expect(DEFAULTS.every((name, i) => names[i]?.includes(name))).toBe(true)
    expect(typeRow('협상').getByText('기본')).toBeInTheDocument()
    expect(typeRow('협상').getByText(/Action [1-9]\d*건/)).toBeInTheDocument()
    expect(typeRow('계약').getByText(/Action \d+건/)).toBeInTheDocument()
  })

  it('shows the creator of a type made by a user', async () => {
    const { user } = await openTypes()

    await addType(user, '웨비나')

    expect(await within(table()).findByText('웨비나')).toBeInTheDocument()
    const row = typeRow('웨비나')
    expect(row.queryByText('기본')).not.toBeInTheDocument()
    expect(row.getByText(/최관리/)).toBeInTheDocument()
    expect(row.getByText('Action 0건')).toBeInTheDocument()
  })
})

describe('Action 유형 추가 (AC-29)', () => {
  it('adds a type, shows it after the defaults and clears the input', async () => {
    const { user } = await openTypes()

    await addType(user, '웨비나')

    expect(await within(table()).findByText('웨비나')).toBeInTheDocument()
    expect(screen.getByLabelText('새 유형 이름')).toHaveValue('')
    const rows = within(table()).getAllByRole('row').slice(1)
    expect(rows[rows.length - 1]).toHaveTextContent('웨비나')
  })

  it('rejects a duplicate ignoring case with the server message in the error banner', async () => {
    const { user } = await openTypes()
    await addType(user, 'Webinar')
    await within(table()).findByText('Webinar')

    await addType(user, 'webinar')

    expect(await screen.findByRole('alert')).toHaveTextContent('이미 있는 유형 이름입니다.')
  })

  it('shows the server messages for an empty name and a name over 50 characters', async () => {
    const { user } = await openTypes()

    await user.click(within(screen.getByRole('form', { name: 'Action 유형 추가' })).getByRole('button', { name: '추가' }))
    expect(await screen.findByRole('alert')).toHaveTextContent('유형을 입력하세요.')

    await addType(user, 'x'.repeat(51))
    await waitFor(() => expect(screen.getByRole('alert')).toHaveTextContent('유형은 50자 이내로 입력하세요.'))
  })
})

describe('Action 유형 이름 수정 (AC-29)', () => {
  it('renames a default type that actions use', async () => {
    const { user } = await openTypes()

    await user.click(typeRow('협상').getByRole('button', { name: '이름 수정' }))
    const input = screen.getByLabelText('유형 이름')
    await user.clear(input)
    await user.type(input, '가격 협상')
    await user.click(screen.getByRole('button', { name: '저장' }))

    expect(await within(table()).findByText('가격 협상')).toBeInTheDocument()
    expect(within(table()).queryByText('협상')).not.toBeInTheDocument()
  })

  it('allows changing only the case of its own name', async () => {
    const { user } = await openTypes()
    await addType(user, 'Webinar')
    await within(table()).findByText('Webinar')

    await user.click(typeRow('Webinar').getByRole('button', { name: '이름 수정' }))
    const input = screen.getByLabelText('유형 이름')
    await user.clear(input)
    await user.type(input, 'WEBINAR')
    await user.click(screen.getByRole('button', { name: '저장' }))

    expect(await within(table()).findByText('WEBINAR')).toBeInTheDocument()
  })

  it('refuses a name that another type has and shows the server message', async () => {
    const { user } = await openTypes()

    await user.click(typeRow('협상').getByRole('button', { name: '이름 수정' }))
    const input = screen.getByLabelText('유형 이름')
    await user.clear(input)
    await user.type(input, '미팅')
    await user.click(screen.getByRole('button', { name: '저장' }))

    expect(await screen.findByRole('alert')).toHaveTextContent('이미 있는 유형 이름입니다.')
  })

  it('cancels the rename without changing the name', async () => {
    const { user } = await openTypes()

    await user.click(typeRow('협상').getByRole('button', { name: '이름 수정' }))
    await user.type(screen.getByLabelText('유형 이름'), ' 변경')
    await user.click(screen.getByRole('button', { name: '취소' }))

    expect(within(table()).getByText('협상')).toBeInTheDocument()
    expect(screen.queryByLabelText('유형 이름')).not.toBeInTheDocument()
  })
})

describe('Action 유형 삭제 (AC-29)', () => {
  it('asks with the type name and deletes an unused type', async () => {
    const { user } = await openTypes()
    await addType(user, '임시 유형')
    await within(table()).findByText('임시 유형')

    await user.click(typeRow('임시 유형').getByRole('button', { name: '삭제' }))
    const dialog = await screen.findByRole('dialog', { name: '유형 삭제' })
    expect(dialog).toHaveTextContent("'임시 유형' 유형을 삭제할까요? 사용 중인 유형은 삭제할 수 없습니다.")
    await user.click(within(dialog).getByRole('button', { name: '삭제' }))

    await waitFor(() => expect(within(table()).queryByText('임시 유형')).not.toBeInTheDocument())
  })

  it('keeps the type when the confirmation is declined', async () => {
    const { user } = await openTypes()
    await addType(user, '임시 유형')
    await within(table()).findByText('임시 유형')

    await user.click(typeRow('임시 유형').getByRole('button', { name: '삭제' }))
    await user.click(within(await screen.findByRole('dialog')).getByRole('button', { name: '취소' }))

    expect(within(table()).getByText('임시 유형')).toBeInTheDocument()
  })

  it('shows the 409 message with the count when the type is in use and keeps the type', async () => {
    const { user } = await openTypes()

    await user.click(typeRow('협상').getByRole('button', { name: '삭제' }))
    await user.click(within(await screen.findByRole('dialog')).getByRole('button', { name: '삭제' }))

    expect(await screen.findByRole('alert')).toHaveTextContent(/사용 중인 유형은 삭제할 수 없습니다\. \(Action \d+건\)/)
    expect(within(table()).getByText('협상')).toBeInTheDocument()
  })

  it('can delete a default type once no action uses it', async () => {
    const { user, client } = await openTypes()
    const target = (await gateway.actionTypes.list()).find((t) => t.name === '기타')
    const deals = await gateway.deals.list({ limit: 100 })
    for (const deal of deals.items) {
      for (const action of await gateway.actions.list(deal.code, { typeId: target?.id ?? NO_SUCH_ID })) await gateway.actions.remove(action.id)
    }
    await client.invalidateQueries()
    await waitFor(() => expect(typeRow('기타').getByText('Action 0건')).toBeInTheDocument())

    await user.click(typeRow('기타').getByRole('button', { name: '삭제' }))
    await user.click(within(await screen.findByRole('dialog')).getByRole('button', { name: '삭제' }))

    await waitFor(() => expect(within(table()).queryByText('기타')).not.toBeInTheDocument())
  })
})

describe('Action 유형 권한', () => {
  it('lets only the admin reach the admin page, so sales cannot rename or delete (403 at the gateway)', async () => {
    await renderAt('/deals', { role: 'sales' })
    const created = await gateway.actionTypes.create('영업이 만든 유형')

    await expect(gateway.actionTypes.rename(created.id, '바꾼 이름')).rejects.toMatchObject({ status: 403 })
    await expect(gateway.actionTypes.remove(created.id)).rejects.toMatchObject({ status: 403 })
  })
})
