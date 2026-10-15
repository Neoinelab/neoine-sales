import { screen, waitFor, within } from '@testing-library/react'
import type { UserEvent } from '@testing-library/user-event'
import { describe, expect, it } from 'vitest'
import { renderAt } from '../../../test/mockApp'

async function openNew(user: UserEvent, category = 'Budget') {
  await screen.findByRole('heading', { name: 'Deal 등록' })
  await user.click(screen.getByRole('button', { name: `${category} 새 Label` }))
  return screen.getByLabelText(`${category} 새 Label 이름`)
}

describe('BANT Label (T-LABEL-03, T-LABEL-04)', () => {
  it('creates a label on the spot and selects it', async () => {
    const { user } = await renderAt('/deals/new')
    const input = await openNew(user)
    await user.type(input, '즉석 예산 라벨')
    await user.click(screen.getByRole('button', { name: '만들기' }))
    await waitFor(() => expect(screen.getByLabelText('Budget')).toHaveDisplayValue('즉석 예산 라벨'))
    expect(screen.queryByLabelText('Budget 새 Label 이름')).not.toBeInTheDocument()
  })

  it('rejects a duplicate name of the same category', async () => {
    const { user } = await renderAt('/deals/new')
    const input = await openNew(user)
    await user.type(input, '단독 예산 확보')
    await user.click(screen.getByRole('button', { name: '만들기' }))
    expect(await screen.findByText('같은 구분에 이미 있는 Label 이름입니다.')).toBeVisible()
  })

  it('rejects a name that differs only by letter case (English label)', async () => {
    const { user } = await renderAt('/deals/new')
    const first = await openNew(user, 'Need')
    await user.type(first, 'Zeta Need')
    await user.click(screen.getByRole('button', { name: '만들기' }))
    await waitFor(() => expect(screen.getByLabelText('Need')).toHaveDisplayValue('Zeta Need'))
    const second = await openNew(user, 'Need')
    await user.type(second, 'ZETA NEED')
    await user.click(screen.getByRole('button', { name: '만들기' }))
    expect(await screen.findByText('같은 구분에 이미 있는 Label 이름입니다.')).toBeVisible()
  })

  it('rejects an empty name and a name longer than 50 characters', async () => {
    const { user } = await renderAt('/deals/new')
    const input = await openNew(user, 'Need')
    await user.click(screen.getByRole('button', { name: '만들기' }))
    expect(await screen.findByText('Label 이름을 입력하세요.')).toBeVisible()
    await user.type(input, 'x'.repeat(51))
    await user.click(screen.getByRole('button', { name: '만들기' }))
    expect(await screen.findByText('Label 이름은 50자 이내로 입력하세요.')).toBeVisible()
  })

  it('allows the same name in another category', async () => {
    const { user } = await renderAt('/deals/new')
    const input = await openNew(user, 'Authority')
    await user.type(input, '단독 예산 확보')
    await user.click(screen.getByRole('button', { name: '만들기' }))
    await waitFor(() => expect(screen.getByLabelText('Authority')).toHaveDisplayValue('단독 예산 확보'))
  })

  it('creates with Enter in the name input without saving the deal', async () => {
    const { user, location } = await renderAt('/deals/new')
    const input = await openNew(user)
    await user.type(input, 'Enter로 만든 라벨{Enter}')
    await waitFor(() => expect(screen.getByLabelText('Budget')).toHaveDisplayValue('Enter로 만든 라벨'))
    expect(location()).toBe('/deals/new')
  })

  it('closes the creation input with the cancel button', async () => {
    const { user } = await renderAt('/deals/new')
    await openNew(user)
    await user.click(screen.getByRole('button', { name: '새 Label 취소' }))
    expect(screen.queryByLabelText('Budget 새 Label 이름')).not.toBeInTheDocument()
  })

  it('has no way to rename or delete an existing label', async () => {
    await renderAt('/deals/new')
    await screen.findByRole('heading', { name: 'Deal 등록' })
    const bant = screen.getByRole('group', { name: 'BANT' })
    expect(within(bant).queryByRole('button', { name: /수정|삭제|이름 변경/ })).not.toBeInTheDocument()
  })
})
