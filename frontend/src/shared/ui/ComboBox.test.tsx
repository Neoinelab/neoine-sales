import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { createRef, useState } from 'react'
import { describe, expect, it, vi } from 'vitest'
import { ComboBox, type ComboOption } from './ComboBox'

const OPTIONS: ComboOption[] = [
  { value: '한빛상사', label: '한빛상사' },
  { value: '하나솔루션', label: '하나솔루션' },
  { value: '대한소프트', label: '대한소프트', description: '3명' },
]

function Host({ onSelect, transform }: { onSelect?: (o: ComboOption) => void; transform?: (raw: string) => string }) {
  const [value, setValue] = useState('')
  return (
    <ComboBox label="회사명" name="company" value={value} onChange={setValue} options={OPTIONS} onSelectOption={onSelect} transform={transform} />
  )
}

describe('ComboBox', () => {
  it('exposes an accessible combobox and lists options on focus', async () => {
    render(<Host />)

    await userEvent.click(screen.getByRole('combobox', { name: '회사명' }))

    expect(screen.getByRole('listbox')).toBeInTheDocument()
    expect(screen.getAllByRole('option')).toHaveLength(3)
  })

  it('selects an option with the mouse', async () => {
    const onSelect = vi.fn()
    render(<Host onSelect={onSelect} />)
    await userEvent.click(screen.getByRole('combobox', { name: '회사명' }))

    await userEvent.click(screen.getByRole('option', { name: /대한소프트/ }))

    expect(screen.getByRole('combobox', { name: '회사명' })).toHaveValue('대한소프트')
    expect(onSelect).toHaveBeenCalledWith(OPTIONS[2])
    expect(screen.queryByRole('listbox')).not.toBeInTheDocument()
  })

  it('accepts free text that is not in the list', async () => {
    const onSelect = vi.fn()
    render(<Host onSelect={onSelect} />)

    await userEvent.type(screen.getByRole('combobox', { name: '회사명' }), '새회사')

    expect(screen.getByRole('combobox', { name: '회사명' })).toHaveValue('새회사')
    expect(onSelect).not.toHaveBeenCalled()
  })

  it('filters options by what was typed', async () => {
    render(<Host />)

    await userEvent.type(screen.getByRole('combobox', { name: '회사명' }), '하')

    expect(screen.getAllByRole('option').map((o) => o.textContent)).toEqual(['하나솔루션'])
  })

  it('supports the keyboard: arrows move, Enter selects, Escape closes', async () => {
    const onSelect = vi.fn()
    render(<Host onSelect={onSelect} />)
    const input = screen.getByRole('combobox', { name: '회사명' })
    await userEvent.click(input)

    await userEvent.keyboard('{ArrowDown}{ArrowDown}')
    expect(input).toHaveAttribute('aria-activedescendant', screen.getAllByRole('option')[1]?.id)
    await userEvent.keyboard('{Enter}')
    expect(onSelect).toHaveBeenCalledWith(OPTIONS[1])
    expect(input).toHaveValue('하나솔루션')

    await userEvent.keyboard('{ArrowDown}')
    expect(screen.getByRole('listbox')).toBeInTheDocument()
    await userEvent.keyboard('{Escape}')
    expect(screen.queryByRole('listbox')).not.toBeInTheDocument()
  })

  it('applies the transform to typed text', async () => {
    render(<Host transform={(raw) => raw.replace(/\s/g, '')} />)

    await userEvent.type(screen.getByRole('combobox', { name: '회사명' }), 'a b c')

    expect(screen.getByRole('combobox', { name: '회사명' })).toHaveValue('abc')
  })

  it('shows an error message under the input', () => {
    render(<ComboBox label="회사명" name="c" value="" onChange={() => {}} options={[]} error="회사명을 입력하세요." />)

    expect(screen.getByRole('alert')).toHaveTextContent('회사명을 입력하세요.')
    expect(screen.getByRole('combobox', { name: '회사명' })).toBeInvalid()
  })

  it('shows the visible label while keeping the full accessible name', async () => {
    render(<ComboBox label="고객 회사명" visibleLabel="회사" name="c" value="" onChange={() => {}} options={OPTIONS} />)

    const input = screen.getByRole('combobox', { name: '고객 회사명' })
    expect(Array.from((input as HTMLInputElement).labels ?? []).map((l) => l.textContent)).toEqual(['회사'])
    await userEvent.click(input)
    expect(screen.getByRole('listbox', { name: '고객 회사명' })).toBeInTheDocument()
  })

  it('renders the label text and no aria-label without a visible label', () => {
    render(<ComboBox label="회사명" name="c" value="" onChange={() => {}} options={OPTIONS} />)

    const input = screen.getByRole('combobox', { name: '회사명' })
    expect(Array.from((input as HTMLInputElement).labels ?? []).map((l) => l.textContent)).toEqual(['회사명'])
    expect(input).not.toHaveAttribute('aria-label')
  })

  it('forwards inputRef to the text input so a form can move focus to it (AC-27)', () => {
    const ref = createRef<HTMLInputElement>()
    render(<ComboBox label="회사명" name="c" value="" onChange={() => {}} options={OPTIONS} inputRef={ref} />)

    expect(ref.current).toBe(screen.getByRole('combobox', { name: '회사명' }))
    ref.current?.focus()
    expect(screen.getByRole('combobox', { name: '회사명' })).toHaveFocus()
  })
})
