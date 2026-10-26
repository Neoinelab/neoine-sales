import { render, screen, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { describe, expect, it, vi } from 'vitest'
import { MultiCheckSelect } from './MultiCheckSelect'

/** 체크박스 드롭다운(Forecast 다중 조건 AC-07): 접근 이름, 열기·닫기, 포커스, 콜백. */

const OPTIONS = [
  { value: 'pipeline', label: 'Pipeline' },
  { value: 'best', label: 'Best' },
  { value: 'commit', label: 'Commit' },
]

function setup(over: Partial<React.ComponentProps<typeof MultiCheckSelect>> = {}) {
  const onToggle = vi.fn()
  const onClear = vi.fn()
  const user = userEvent.setup()
  render(
    <div>
      <button type="button">바깥</button>
      <MultiCheckSelect
        label="Forecast"
        name="forecast"
        options={OPTIONS}
        selected={[]}
        summary="전체"
        onToggle={onToggle}
        onClear={onClear}
        {...over}
      />
    </div>,
  )
  return { user, onToggle, onClear }
}

const button = () => screen.getByRole('button', { name: /^Forecast / })

describe('MultiCheckSelect', () => {
  it('shows a button named by the label and the summary, closed at first', () => {
    setup({ summary: '2개 선택' })

    expect(screen.getByRole('button', { name: 'Forecast 2개 선택' })).toHaveAttribute('aria-expanded', 'false')
    expect(screen.queryByRole('group', { name: 'Forecast' })).not.toBeInTheDocument()
  })

  it('can be found by its label text', () => {
    setup()

    expect(screen.getByLabelText('Forecast')).toBe(button())
  })

  it('opens a group of checkboxes in the order of the options', async () => {
    const { user } = setup()

    await user.click(button())

    expect(button()).toHaveAttribute('aria-expanded', 'true')
    const panel = within(screen.getByRole('group', { name: 'Forecast' }))
    expect(panel.getAllByRole('checkbox').map((c) => c.getAttribute('value'))).toEqual(['pipeline', 'best', 'commit'])
    expect(panel.getAllByRole('checkbox').map((c) => (c as HTMLInputElement).name)).toEqual(['forecast', 'forecast', 'forecast'])
    expect(panel.getByRole('checkbox', { name: 'Pipeline' })).toBeInTheDocument()
    expect(panel.getByRole('button', { name: '전체' })).toBeInTheDocument()
  })

  it('checks the selected options only', async () => {
    const { user } = setup({ selected: ['best'] })

    await user.click(button())

    expect(screen.getByRole('checkbox', { name: 'Best' })).toBeChecked()
    expect(screen.getByRole('checkbox', { name: 'Pipeline' })).not.toBeChecked()
    expect(screen.getByRole('checkbox', { name: 'Commit' })).not.toBeChecked()
  })

  it('reports onToggle(value, true) when an unchecked box is clicked', async () => {
    const { user, onToggle } = setup()
    await user.click(button())

    await user.click(screen.getByRole('checkbox', { name: 'Best' }))

    expect(onToggle).toHaveBeenCalledWith('best', true)
    expect(onToggle).toHaveBeenCalledTimes(1)
  })

  it('reports onToggle(value, false) when a checked box is clicked', async () => {
    const { user, onToggle } = setup({ selected: ['best'] })
    await user.click(button())

    await user.click(screen.getByRole('checkbox', { name: 'Best' }))

    expect(onToggle).toHaveBeenCalledWith('best', false)
  })

  it('keeps the panel open after a toggle', async () => {
    const { user } = setup()
    await user.click(button())

    await user.click(screen.getByRole('checkbox', { name: 'Best' }))

    expect(screen.getByRole('group', { name: 'Forecast' })).toBeInTheDocument()
  })

  it('calls onClear for the 전체 button', async () => {
    const { user, onClear, onToggle } = setup({ selected: ['best'] })
    await user.click(button())

    await user.click(within(screen.getByRole('group', { name: 'Forecast' })).getByRole('button', { name: '전체' }))

    expect(onClear).toHaveBeenCalledTimes(1)
    expect(onToggle).not.toHaveBeenCalled()
  })

  it('closes with Escape and returns the focus to the button', async () => {
    const { user } = setup()
    await user.click(button())
    await user.click(screen.getByRole('checkbox', { name: 'Best' }))

    await user.keyboard('{Escape}')

    expect(screen.queryByRole('group', { name: 'Forecast' })).not.toBeInTheDocument()
    expect(button()).toHaveAttribute('aria-expanded', 'false')
    expect(button()).toHaveFocus()
  })

  it('closes when the pointer goes down outside', async () => {
    const { user } = setup()
    await user.click(button())

    await user.click(screen.getByRole('button', { name: '바깥' }))

    expect(screen.queryByRole('group', { name: 'Forecast' })).not.toBeInTheDocument()
  })

  it('stays open when the pointer goes down inside the panel', async () => {
    const { user } = setup()
    await user.click(button())

    await user.click(within(screen.getByRole('group', { name: 'Forecast' })).getByText('Pipeline'))

    expect(screen.getByRole('group', { name: 'Forecast' })).toBeInTheDocument()
  })

  it('closes again when the button is clicked while open', async () => {
    const { user } = setup()
    await user.click(button())

    await user.click(button())

    expect(screen.queryByRole('group', { name: 'Forecast' })).not.toBeInTheDocument()
  })

  it('shows no checkboxes while the options are not loaded', async () => {
    const { user } = setup({ options: [] })

    await user.click(button())

    expect(screen.queryAllByRole('checkbox')).toHaveLength(0)
  })

  it('closes when the focus tabs out of the component, leaving the focus where it went', async () => {
    const user = userEvent.setup()
    // 패널 마지막 요소 다음에 포커스를 받을 요소가 있어야 Tab 이탈 뒤 포커스 위치를 확인할 수 있다.
    render(
      <div>
        <MultiCheckSelect label="Forecast" name="forecast" options={OPTIONS} selected={[]} summary="전체" onToggle={vi.fn()} onClear={vi.fn()} />
        <button type="button">다음 입력란</button>
      </div>,
    )
    await user.click(button())
    const panel = within(screen.getByRole('group', { name: 'Forecast' }))
    panel.getByRole('button', { name: '전체' }).focus()

    await user.tab()

    expect(screen.queryByRole('group', { name: 'Forecast' })).not.toBeInTheDocument()
    expect(screen.getByRole('button', { name: '다음 입력란' })).toHaveFocus()
  })

  it('stays open while the focus moves between the checkboxes', async () => {
    const { user } = setup()
    await user.click(button())
    screen.getByRole('checkbox', { name: 'Pipeline' }).focus()

    await user.tab()

    expect(screen.getByRole('checkbox', { name: 'Best' })).toHaveFocus()
    expect(screen.getByRole('group', { name: 'Forecast' })).toBeInTheDocument()
  })

  it('has no aria-haspopup, and aria-expanded follows the open state', async () => {
    const { user } = setup()

    expect(button()).not.toHaveAttribute('aria-haspopup')
    expect(button()).toHaveAttribute('aria-expanded', 'false')
    await user.click(button())
    expect(button()).not.toHaveAttribute('aria-haspopup')
    expect(button()).toHaveAttribute('aria-expanded', 'true')
  })

  it('has aria-controls only while open, pointing at the real panel', async () => {
    const { user } = setup()
    expect(button()).not.toHaveAttribute('aria-controls')

    await user.click(button())
    const id = button().getAttribute('aria-controls')
    expect(id).toBeTruthy()
    expect(document.getElementById(id ?? '')).toBe(screen.getByRole('group', { name: 'Forecast' }))

    await user.click(button())
    expect(button()).not.toHaveAttribute('aria-controls')
  })
})
