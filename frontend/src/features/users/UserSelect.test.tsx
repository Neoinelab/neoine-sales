import { screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { describe, expect, it, vi } from 'vitest'
import { ME_SALES, userRef } from '../../test/authFixtures'
import { mockApi, renderApp } from '../../test/utils'
import { UserSelect } from './UserSelect'
import { useUserChoice } from './options'

const OPTIONS = { body: { items: [userRef('u-2', '김영업'), userRef('u-3', '박영업')], offset: 0, limit: 200 } }
const OPTIONS_WITH_RESIGNED = {
  body: { items: [userRef('u-2', '김영업'), userRef('u-7', '이퇴사', true)], offset: 0, limit: 200 },
}

function Harness({ initial, includeResigned = false }: { initial?: ReturnType<typeof userRef>; includeResigned?: boolean }) {
  const [value, setValue] = useUserChoice(initial?.id)
  return (
    <UserSelect
      label="담당자"
      name="owner"
      value={value}
      onChange={setValue}
      current={initial}
      includeResigned={includeResigned}
      required
    />
  )
}

describe('UserSelect', () => {
  it('lists active users from user-options without asking for resigned ones', async () => {
    const requests = mockApi({ 'GET /api/v1/user-options': OPTIONS })

    renderApp(<Harness />)

    expect(await screen.findByRole('option', { name: '박영업' })).toBeInTheDocument()
    const query = requests.find((r) => r.path === '/api/v1/user-options')!.query
    expect(query.get('include_resigned')).not.toBe('true')
  })

  it('preselects the signed-in user (me.user_id) on a new form', async () => {
    mockApi({ 'GET /api/v1/user-options': OPTIONS })

    renderApp(<Harness />)

    await waitFor(() => expect(screen.getByLabelText('담당자')).toHaveValue(ME_SALES.user_id))
  })

  it('fills in the signed-in user late only while the user has not chosen anyone', async () => {
    let release: () => void = () => undefined
    const gate = new Promise<void>((resolve) => (release = resolve))
    mockApi({ 'GET /api/v1/user-options': OPTIONS })
    const base = globalThis.fetch
    // /auth/me 응답만 늦게 도착시킨다.
    vi.stubGlobal('fetch', async (request: Request) => {
      if (new URL(request.url).pathname === '/api/v1/auth/me') await gate
      return base(request)
    })
    renderApp(<Harness />)
    await screen.findByRole('option', { name: '박영업' })
    expect(screen.getByLabelText('담당자')).toHaveValue('')
    await userEvent.selectOptions(screen.getByLabelText('담당자'), 'u-3')
    release()

    await new Promise((resolve) => setTimeout(resolve, 80))
    expect(screen.getByLabelText('담당자')).toHaveValue('u-3')
  })

  it('fills in the signed-in user when me arrives late and nothing was chosen yet', async () => {
    let release: () => void = () => undefined
    const gate = new Promise<void>((resolve) => (release = resolve))
    mockApi({ 'GET /api/v1/user-options': OPTIONS })
    const base = globalThis.fetch
    vi.stubGlobal('fetch', async (request: Request) => {
      if (new URL(request.url).pathname === '/api/v1/auth/me') await gate
      return base(request)
    })
    renderApp(<Harness />)
    await screen.findByRole('option', { name: '박영업' })
    expect(screen.getByLabelText('담당자')).toHaveValue('')

    release()

    await waitFor(() => expect(screen.getByLabelText('담당자')).toHaveValue(ME_SALES.user_id))
  })

  it('keeps the existing value on an edit form instead of the signed-in user', async () => {
    mockApi({ 'GET /api/v1/user-options': OPTIONS })

    renderApp(<Harness initial={userRef('u-3', '박영업')} />)

    await screen.findByRole('option', { name: '박영업' })
    await new Promise((resolve) => setTimeout(resolve, 80))
    expect(screen.getByLabelText('담당자')).toHaveValue('u-3')
  })

  it('shows a resigned existing value as 이름(퇴사) but does not let you pick it again', async () => {
    mockApi({ 'GET /api/v1/user-options': OPTIONS })

    renderApp(<Harness initial={userRef('u-7', '이퇴사', true)} />)

    const option = await screen.findByRole('option', { name: '이퇴사(퇴사)' })
    expect(screen.getByLabelText('담당자')).toHaveValue('u-7')
    expect(option).toBeDisabled()
    await screen.findByRole('option', { name: '김영업' })
    await userEvent.selectOptions(screen.getByLabelText('담당자'), 'u-2')
    expect(screen.getByLabelText('담당자')).toHaveValue('u-2')
    expect(screen.getByRole('option', { name: '이퇴사(퇴사)' })).toBeDisabled()
  })

  it('asks for resigned users too in a filter and shows them by label', async () => {
    const requests = mockApi({ 'GET /api/v1/user-options': OPTIONS_WITH_RESIGNED })

    renderApp(<Harness includeResigned />)

    expect(await screen.findByRole('option', { name: '이퇴사(퇴사)' })).toBeEnabled()
    expect(requests.find((r) => r.path === '/api/v1/user-options')!.query.get('include_resigned')).toBe('true')
  })
})
