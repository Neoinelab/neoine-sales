import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { useState } from 'react'
import { describe, expect, it } from 'vitest'
import { Tabs } from './Tabs'

const TABS = [
  { id: 'actions', label: 'Actions' },
  { id: 'history', label: 'Deal History' },
]

function Host() {
  const [active, setActive] = useState('actions')
  return (
    <Tabs label="Deal 하단" tabs={TABS} active={active} onChange={setActive}>
      <p>{active} 내용</p>
    </Tabs>
  )
}

describe('Tabs', () => {
  it('renders a tablist with the active tab selected and a labelled panel', () => {
    render(<Host />)

    expect(screen.getByRole('tablist', { name: 'Deal 하단' })).toBeInTheDocument()
    expect(screen.getByRole('tab', { name: 'Actions' })).toHaveAttribute('aria-selected', 'true')
    expect(screen.getByRole('tab', { name: 'Deal History' })).toHaveAttribute('aria-selected', 'false')
    expect(screen.getByRole('tabpanel', { name: 'Actions' })).toHaveTextContent('actions 내용')
  })

  it('switches on click', async () => {
    render(<Host />)

    await userEvent.click(screen.getByRole('tab', { name: 'Deal History' }))

    expect(screen.getByRole('tab', { name: 'Deal History' })).toHaveAttribute('aria-selected', 'true')
    expect(screen.getByRole('tabpanel', { name: 'Deal History' })).toHaveTextContent('history 내용')
  })

  it('moves with arrow keys and only the active tab is tabbable', async () => {
    render(<Host />)
    screen.getByRole('tab', { name: 'Actions' }).focus()

    await userEvent.keyboard('{ArrowRight}')

    expect(screen.getByRole('tab', { name: 'Deal History' })).toHaveFocus()
    expect(screen.getByRole('tab', { name: 'Deal History' })).toHaveAttribute('aria-selected', 'true')
    expect(screen.getByRole('tab', { name: 'Actions' })).toHaveAttribute('tabindex', '-1')
    await userEvent.keyboard('{ArrowRight}')
    expect(screen.getByRole('tab', { name: 'Actions' })).toHaveFocus()
  })
})
