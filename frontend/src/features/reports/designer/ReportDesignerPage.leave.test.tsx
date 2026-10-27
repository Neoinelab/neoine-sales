import { screen, waitFor, within } from '@testing-library/react'
import { describe, expect, it } from 'vitest'
import { addColumn, addCondition, chipItems, openDesigner, setupReportClock } from '../../../test/reportScreen'

setupReportClock()

const menuLink = (name: string): HTMLElement => within(screen.getByRole('navigation', { name: '주 메뉴' })).getByRole('link', { name })
const LEAVE_TITLE = '리포트 설계를 떠날까요?'

/** beforeunload를 보내고 막았는지(기본 동작 취소) 돌려준다. */
function unloadIsBlocked(): boolean {
  const event = new Event('beforeunload', { cancelable: true })
  window.dispatchEvent(event)
  return event.defaultPrevented
}

describe('떠날 때 확인 (AC16)', () => {
  it('asks before leaving with changes and stays on cancel', async () => {
    const { user, location } = await openDesigner()
    await addColumn(user, 'Deal code')

    await user.click(menuLink('Deals'))

    const dialog = await screen.findByRole('dialog', { name: LEAVE_TITLE })
    expect(dialog).toHaveTextContent('작성 중인 리포트 설계가 사라집니다. 이 화면을 떠날까요?')

    await user.click(within(dialog).getByRole('button', { name: '머물기' }))

    expect(screen.queryByRole('dialog')).not.toBeInTheDocument()
    expect(location()).toBe('/reports/new')
    expect(chipItems()).toHaveLength(1)
  })

  it('leaves after the leave button', async () => {
    const { user, location } = await openDesigner()
    await addColumn(user, 'Deal code')
    await user.click(menuLink('Deals'))

    await user.click(within(await screen.findByRole('dialog', { name: LEAVE_TITLE })).getByRole('button', { name: '떠나기' }))

    await waitFor(() => expect(location()).toMatch(/^\/deals/))
    expect(screen.queryByRole('dialog', { name: LEAVE_TITLE })).not.toBeInTheDocument()
  })

  it('asks when only a condition was added', async () => {
    const { user } = await openDesigner()
    await addCondition(user, 'Vendor')

    await user.click(menuLink('Reports'))

    expect(await screen.findByRole('dialog', { name: LEAVE_TITLE })).toBeVisible()
  })

  it('leaves without asking when nothing changed', async () => {
    const { user, location } = await openDesigner()

    await user.click(menuLink('Deals'))

    await waitFor(() => expect(location()).toMatch(/^\/deals/))
    expect(screen.queryByRole('dialog')).not.toBeInTheDocument()
  })

  it('leaves without asking after the changes were undone', async () => {
    const { user, location } = await openDesigner()
    await addColumn(user, 'Deal code')
    await user.click(screen.getByRole('button', { name: 'Deal code 빼기' }))

    await user.click(menuLink('Deals'))

    await waitFor(() => expect(location()).toMatch(/^\/deals/))
    expect(screen.queryByRole('dialog')).not.toBeInTheDocument()
  })

  it('registers beforeunload only while dirty', async () => {
    const { user } = await openDesigner()
    expect(unloadIsBlocked()).toBe(false)

    await addColumn(user, 'Deal code')
    expect(unloadIsBlocked()).toBe(true)

    await user.click(screen.getByRole('button', { name: 'Deal code 빼기' }))
    expect(unloadIsBlocked()).toBe(false)
  })

  it('stops blocking the unload once the designer is left', async () => {
    const { user, location } = await openDesigner()
    await addColumn(user, 'Deal code')
    await user.click(menuLink('Deals'))
    await user.click(within(await screen.findByRole('dialog', { name: LEAVE_TITLE })).getByRole('button', { name: '떠나기' }))
    await waitFor(() => expect(location()).toMatch(/^\/deals/))

    expect(unloadIsBlocked()).toBe(false)
  })
})

describe('좁은 화면 메뉴 (리뷰 후속)', () => {
  const toggle = (): HTMLElement => screen.getByRole('button', { name: '메뉴 열기' })

  it('closes the open menu after the leave button', async () => {
    const { user, location } = await openDesigner()
    await addColumn(user, 'Deal code')
    await user.click(toggle())
    expect(toggle()).toHaveAttribute('aria-expanded', 'true')

    await user.click(menuLink('Deals'))
    await user.click(within(await screen.findByRole('dialog', { name: LEAVE_TITLE })).getByRole('button', { name: '떠나기' }))

    await waitFor(() => expect(location()).toMatch(/^\/deals/))
    expect(toggle()).toHaveAttribute('aria-expanded', 'false')
  })

  it('closes the open menu on a plain link click when nothing changed', async () => {
    const { user, location } = await openDesigner()
    await user.click(toggle())

    await user.click(menuLink('Deals'))

    await waitFor(() => expect(location()).toMatch(/^\/deals/))
    expect(toggle()).toHaveAttribute('aria-expanded', 'false')
  })
})

describe('초기화 (AC16)', () => {
  it('asks before reset with changes and keeps the design on cancel', async () => {
    const { user } = await openDesigner()
    await addColumn(user, 'Deal code')

    await user.click(screen.getByRole('button', { name: '초기화' }))

    const dialog = await screen.findByRole('dialog', { name: '설계를 모두 지울까요?' })
    await user.click(within(dialog).getByRole('button', { name: '취소' }))

    expect(screen.queryByRole('dialog')).not.toBeInTheDocument()
    expect(chipItems()).toHaveLength(1)
  })

  it('clears the whole design after the confirmation', async () => {
    const { user } = await openDesigner()
    await addColumn(user, 'Deal code')
    await addCondition(user, 'Vendor')
    await user.click(screen.getByRole('radio', { name: /OR/ }))

    await user.click(screen.getByRole('button', { name: '초기화' }))
    await user.click(within(await screen.findByRole('dialog', { name: '설계를 모두 지울까요?' })).getByRole('button', { name: '초기화' }))

    expect(chipItems()).toHaveLength(0)
    expect(screen.queryByRole('combobox', { name: '조건 1 필드' })).not.toBeInTheDocument()
    expect(screen.getByRole('radio', { name: /AND/ })).toBeChecked()
    expect(unloadIsBlocked()).toBe(false)
  })

  it('resets without asking when nothing changed', async () => {
    const { user } = await openDesigner()

    await user.click(screen.getByRole('button', { name: '초기화' }))

    expect(screen.queryByRole('dialog')).not.toBeInTheDocument()
  })
})
