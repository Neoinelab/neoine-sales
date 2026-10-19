import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { useState } from 'react'
import { describe, expect, it, vi } from 'vitest'
import { AmountInput } from './AmountInput'

function Harness({ initial = '', spy }: { initial?: string; spy?: (text: string) => void }) {
  const [value, setValue] = useState(initial)
  return (
    <AmountInput
      aria-label="금액"
      value={value}
      onChange={(text) => {
        spy?.(text)
        setValue(text)
      }}
    />
  )
}

describe('AmountInput', () => {
  it('adds commas while typing', async () => {
    const spy = vi.fn()
    render(<Harness spy={spy} />)
    await userEvent.type(screen.getByLabelText('금액'), '1234567')
    expect(screen.getByLabelText('금액')).toHaveValue('1,234,567')
    expect(spy).toHaveBeenLastCalledWith('1,234,567')
  })

  it('keeps the caret where the digit was inserted', async () => {
    render(<Harness initial="1,234" />)
    const input = screen.getByLabelText<HTMLInputElement>('금액')
    input.focus()
    input.setSelectionRange(1, 1)
    await userEvent.keyboard('9')
    expect(input).toHaveValue('19,234')
    expect(input.selectionStart).toBe(2)
  })

  it('keeps only digits and commas', async () => {
    render(<Harness />)
    await userEvent.type(screen.getByLabelText('금액'), '12a3.4 5')
    expect(screen.getByLabelText('금액')).toHaveValue('12,345')
  })

  it('keeps the caret after the comma when Backspace only removes that comma', async () => {
    render(<Harness initial="1,234" />)
    const input = screen.getByLabelText<HTMLInputElement>('금액')
    input.focus()
    input.setSelectionRange(2, 2)
    await userEvent.keyboard('{Backspace}')
    expect(input).toHaveValue('1,234')
    expect(input.selectionStart).toBe(1)
  })

  it('keeps the caret in place when a discarded character is typed', async () => {
    render(<Harness initial="1,234" />)
    const input = screen.getByLabelText<HTMLInputElement>('금액')
    input.focus()
    input.setSelectionRange(1, 1)
    await userEvent.keyboard('x')
    expect(input).toHaveValue('1,234')
    expect(input.selectionStart).toBe(1)
  })

  it('renders no unit text', () => {
    const { container } = render(<Harness initial="1,234" />)
    expect(container.textContent).not.toContain('천원')
    expect(container.querySelectorAll('input')).toHaveLength(1)
  })
})
