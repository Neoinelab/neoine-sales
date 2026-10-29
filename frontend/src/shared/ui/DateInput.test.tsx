import { fireEvent, render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { useState } from 'react'
import { afterEach, describe, expect, it, vi } from 'vitest'
import { DateInput, type DateInputProps } from './DateInput'

afterEach(() => {
  vi.restoreAllMocks()
  Reflect.deleteProperty(HTMLInputElement.prototype, 'showPicker')
})

type HarnessProps = Partial<Omit<DateInputProps, 'value' | 'onChange'>> & { initial?: string; spy?: (next: string) => void }

function Harness({ initial = '', spy, ...rest }: HarnessProps) {
  const [value, setValue] = useState(initial)
  return (
    <DateInput
      aria-label="견적일"
      {...rest}
      value={value}
      onChange={(next) => {
        spy?.(next)
        setValue(next)
      }}
    />
  )
}

const textBox = () => screen.getByRole<HTMLInputElement>('textbox', { name: '견적일' })
const calendarButton = () => screen.getByRole('button', { name: '견적일 달력 열기' })
const nativeOf = (container: HTMLElement) => container.querySelector<HTMLInputElement>('input[type="date"]') as HTMLInputElement

function stubShowPicker() {
  const showPicker = vi.fn()
  Object.defineProperty(HTMLInputElement.prototype, 'showPicker', { configurable: true, writable: true, value: showPicker })
  return showPicker
}

describe('typing (AC-D1, AC-D2)', () => {
  it('shows yyyy.mm.dd and passes the ISO value while 20261120 is typed', async () => {
    const spy = vi.fn()
    render(<Harness spy={spy} />)
    await userEvent.type(textBox(), '20261120')
    expect(textBox()).toHaveValue('2026.11.20')
    expect(spy).toHaveBeenLastCalledWith('2026-11-20')
  })

  it('passes the typed text itself while the date is incomplete', async () => {
    const spy = vi.fn()
    render(<Harness spy={spy} />)
    await userEvent.type(textBox(), '202611')
    expect(textBox()).toHaveValue('2026.11')
    expect(spy).toHaveBeenLastCalledWith('2026.11')
  })

  it('passes the typed text itself when the date does not exist', async () => {
    const spy = vi.fn()
    render(<Harness spy={spy} />)
    await userEvent.type(textBox(), '20261304')
    expect(textBox()).toHaveValue('2026.13.04')
    expect(spy).toHaveBeenLastCalledWith('2026.13.04')
  })

  it.each(['2026-11-20', '2026/11/20', '2026.11.20'])('turns a pasted %s into 2026.11.20 with the ISO value', async (pasted) => {
    const spy = vi.fn()
    render(<Harness spy={spy} />)
    fireEvent.change(textBox(), { target: { value: pasted } })
    expect(textBox()).toHaveValue('2026.11.20')
    expect(spy).toHaveBeenLastCalledWith('2026-11-20')
  })

  it('pads a one-digit month and day when the field is left', async () => {
    const spy = vi.fn()
    render(<Harness spy={spy} />)
    await userEvent.type(textBox(), '2026.1.5')
    expect(textBox()).toHaveValue('2026.1.5')
    await userEvent.tab()
    expect(textBox()).toHaveValue('2026.01.05')
    expect(spy).toHaveBeenLastCalledWith('2026-01-05')
  })

  it('passes an empty string when the field is cleared', async () => {
    const spy = vi.fn()
    render(<Harness initial="2026-11-20" spy={spy} />)
    await userEvent.clear(textBox())
    expect(textBox()).toHaveValue('')
    expect(spy).toHaveBeenLastCalledWith('')
  })

  it('is a text input with the numeric hint and placeholder', () => {
    render(<Harness />)
    expect(textBox()).toHaveAttribute('type', 'text')
    expect(textBox()).toHaveAttribute('inputmode', 'numeric')
    expect(textBox()).toHaveAttribute('placeholder', 'yyyymmdd')
    // 붙여넣기를 브라우저가 먼저 자르지 않게 maxlength를 두지 않는다(글자 정리는 formatDateTyping이 한다).
    expect(textBox()).not.toHaveAttribute('maxlength')
    expect(textBox()).toHaveAttribute('autocomplete', 'off')
  })
})

describe('paste', () => {
  it.each([
    [' 2026-11-20', '2026.11.20'],
    ['2026. 11. 20.', '2026.11.20'],
    ['2026/11/20', '2026.11.20'],
  ])('turns the pasted text %j into %j with the ISO value', async (pasted, shown) => {
    const spy = vi.fn()
    render(<Harness spy={spy} />)
    textBox().focus()
    await userEvent.paste(pasted)
    expect(textBox()).toHaveValue(shown)
    expect(spy).toHaveBeenLastCalledWith('2026-11-20')
  })
})

describe('caret', () => {
  it('stays after the same number of digits when a dot is removed with Backspace', async () => {
    render(<Harness initial="2026-11-20" />)
    const input = textBox()
    input.focus()
    input.setSelectionRange(5, 5)
    await userEvent.keyboard('{Backspace}')
    // 앞 숫자 4개 뒤(또는 그 앞 숫자를 지운 경우 3개 뒤)에 있어야 하고 끝으로 튀면 안 된다.
    expect(input.selectionStart).toBeGreaterThanOrEqual(3)
    expect(input.selectionStart).toBeLessThanOrEqual(5)
    expect(input.selectionStart).toBe(input.selectionEnd)
  })

  it('stays after the typed digit when a digit is inserted in the middle and the text is rebuilt', async () => {
    render(<Harness initial="2026-11-02" />)
    const input = textBox()
    input.focus()
    input.setSelectionRange(6, 6)
    await userEvent.keyboard('2')
    // 캐럿 앞 숫자는 2026 1 2 = 6개 -> 다시 만든 글자에서 6번째 숫자 뒤(위치 7)
    expect(input.selectionStart).toBe(7)
    expect(input.selectionEnd).toBe(7)
  })

  it('keeps the caret where a digit was replaced in an already formatted text', async () => {
    render(<Harness initial="2026-11-20" />)
    const input = textBox()
    input.focus()
    input.setSelectionRange(2, 2)
    await userEvent.keyboard('9')
    expect(input.selectionStart).toBe(3)
  })
})

describe('own error message (AC-D3)', () => {
  it('shows no message while typing', async () => {
    render(<Harness />)
    await userEvent.type(textBox(), '2026.1')
    expect(screen.queryByRole('alert')).not.toBeInTheDocument()
    expect(textBox()).not.toHaveAttribute('aria-invalid')
  })

  it('asks for yyyymmdd after leaving an incomplete date', async () => {
    render(<Harness />)
    await userEvent.type(textBox(), '2026.1')
    await userEvent.tab()
    expect(screen.getByRole('alert')).toHaveTextContent('날짜를 yyyymmdd 형식으로 입력하세요.')
    expect(textBox()).toHaveAttribute('aria-invalid', 'true')
  })

  it('says the date does not exist after leaving 2026.13.04', async () => {
    render(<Harness />)
    await userEvent.type(textBox(), '20261304')
    await userEvent.tab()
    expect(screen.getByRole('alert')).toHaveTextContent('없는 날짜입니다.')
  })

  it('names the range after leaving a date before 1900', async () => {
    render(<Harness />)
    await userEvent.type(textBox(), '18991231')
    await userEvent.tab()
    expect(screen.getByRole('alert')).toHaveTextContent('1900.01.01부터 2999.12.31 사이로 입력하세요.')
  })

  it('shows the message after Enter on a wrong date', async () => {
    render(<Harness />)
    await userEvent.type(textBox(), '20260230{Enter}')
    expect(screen.getByRole('alert')).toHaveTextContent('없는 날짜입니다.')
  })

  it('hides the message again once the date is corrected', async () => {
    render(<Harness />)
    await userEvent.type(textBox(), '20260230')
    await userEvent.tab()
    expect(screen.getByRole('alert')).toBeVisible()
    await userEvent.clear(textBox())
    await userEvent.type(textBox(), '20260228')
    await userEvent.tab()
    expect(screen.queryByRole('alert')).not.toBeInTheDocument()
    expect(textBox()).not.toHaveAttribute('aria-invalid')
  })

  it('shows no message after leaving an empty field', async () => {
    render(<Harness />)
    textBox().focus()
    await userEvent.tab()
    expect(screen.queryByRole('alert')).not.toBeInTheDocument()
  })

  it('shows the parent error when the text itself is fine', () => {
    render(<Harness error="견적 제출일을 입력하세요." />)
    expect(screen.getByRole('alert')).toHaveTextContent('견적 제출일을 입력하세요.')
    expect(textBox()).toHaveAttribute('aria-invalid', 'true')
  })

  it('prefers its own message over the parent error', async () => {
    render(<Harness error="부모 오류" />)
    await userEvent.type(textBox(), '2026.1')
    await userEvent.tab()
    expect(screen.getByRole('alert')).toHaveTextContent('날짜를 yyyymmdd 형식으로 입력하세요.')
    expect(screen.queryByText('부모 오류')).not.toBeInTheDocument()
  })

  it('links the message to the input and keeps the parent description', async () => {
    render(
      <>
        <p id="hint">안내</p>
        <Harness aria-describedby="hint" />
      </>,
    )
    await userEvent.type(textBox(), '2026.1')
    await userEvent.tab()
    const alert = screen.getByRole('alert')
    const described = (textBox().getAttribute('aria-describedby') ?? '').split(/\s+/)
    expect(described).toContain('hint')
    expect(described).toContain(alert.id)
    expect(alert.id).not.toBe('')
  })
})

describe('Enter (E6)', () => {
  it('finalizes the text, calls onEnter with the value and does not submit the form', async () => {
    const onEnter = vi.fn()
    const onSubmit = vi.fn((e: { preventDefault: () => void }) => e.preventDefault())
    render(
      <form onSubmit={onSubmit}>
        <Harness onEnter={onEnter} />
        <button type="submit">제출</button>
      </form>,
    )
    await userEvent.type(textBox(), '2026.1.5{Enter}')
    expect(textBox()).toHaveValue('2026.01.05')
    expect(onEnter).toHaveBeenCalledTimes(1)
    expect(onEnter).toHaveBeenCalledWith('2026-01-05')
    expect(onSubmit).not.toHaveBeenCalled()
  })

  it('calls onEnter with the typed text when the date is wrong so the parent can refuse', async () => {
    const onEnter = vi.fn()
    render(<Harness onEnter={onEnter} />)
    await userEvent.type(textBox(), '2026.13.04{Enter}')
    expect(onEnter).toHaveBeenCalledWith('2026.13.04')
  })

  it('calls onEnter with an empty string for an empty field', async () => {
    const onEnter = vi.fn()
    render(<Harness onEnter={onEnter} />)
    textBox().focus()
    await userEvent.keyboard('{Enter}')
    expect(onEnter).toHaveBeenCalledWith('')
  })

  it('leaves the default form behaviour when onEnter is not given', async () => {
    const onSubmit = vi.fn((e: { preventDefault: () => void }) => e.preventDefault())
    render(
      <form onSubmit={onSubmit}>
        <Harness />
        <button type="submit">제출</button>
      </form>,
    )
    await userEvent.type(textBox(), '20261120{Enter}')
    expect(onSubmit).toHaveBeenCalledTimes(1)
  })
})

describe('calendar (AC-D5, E2, E7)', () => {
  it('opens the native picker from the calendar button', async () => {
    const showPicker = stubShowPicker()
    render(<Harness />)
    await userEvent.click(calendarButton())
    expect(showPicker).toHaveBeenCalledTimes(1)
  })

  it('opens the picker of the hidden native date input', async () => {
    const showPicker = stubShowPicker()
    const { container } = render(<Harness />)
    await userEvent.click(calendarButton())
    expect(showPicker.mock.contexts[0]).toBe(nativeOf(container))
  })

  it('falls back to focus and click on the native input when showPicker is missing', async () => {
    const { container } = render(<Harness />)
    const native = nativeOf(container)
    const onClick = vi.fn()
    native.addEventListener('click', onClick)
    await userEvent.click(calendarButton())
    expect(document.activeElement).toBe(native)
    expect(onClick).toHaveBeenCalledTimes(1)
  })

  it('falls back the same way when showPicker throws', async () => {
    Object.defineProperty(HTMLInputElement.prototype, 'showPicker', {
      configurable: true,
      writable: true,
      value: () => {
        throw new DOMException('not allowed', 'NotAllowedError')
      },
    })
    const { container } = render(<Harness />)
    const native = nativeOf(container)
    const onClick = vi.fn()
    native.addEventListener('click', onClick)
    await userEvent.click(calendarButton())
    expect(onClick).toHaveBeenCalledTimes(1)
  })

  it('keeps the native input out of the tab order and the accessibility tree, but not display none', () => {
    const { container } = render(<Harness />)
    const native = nativeOf(container)
    expect(native).toHaveAttribute('tabindex', '-1')
    expect(native).toHaveAttribute('aria-hidden', 'true')
    expect(native).toHaveAttribute('min', '1900-01-01')
    expect(native).toHaveAttribute('max', '2999-12-31')
    expect(native.className).toContain('date-input-native')
    expect(native.style.display).not.toBe('none')
  })

  it('puts the chosen date into the field, returns focus to the text box and calls onPicked', () => {
    const spy = vi.fn()
    const onPicked = vi.fn()
    const { container } = render(<Harness spy={spy} onPicked={onPicked} />)
    fireEvent.change(nativeOf(container), { target: { value: '2026-12-01' } })
    expect(textBox()).toHaveValue('2026.12.01')
    expect(spy).toHaveBeenLastCalledWith('2026-12-01')
    expect(onPicked).toHaveBeenCalledWith('2026-12-01')
    expect(document.activeElement).toBe(textBox())
  })

  it('opens the calendar on the current value', () => {
    const { container } = render(<Harness initial="2026-11-20" />)
    expect(nativeOf(container)).toHaveValue('2026-11-20')
  })

  it('gives the calendar no value while the text is not a valid date', async () => {
    const { container } = render(<Harness />)
    await userEvent.type(textBox(), '2026.1')
    expect(nativeOf(container)).toHaveValue('')
  })

  it('names the button after the field, or just 달력 열기 without a name', () => {
    render(
      <>
        <DateInput aria-label="Due Date" value="" onChange={() => {}} />
        <DateInput value="" onChange={() => {}} />
      </>,
    )
    expect(screen.getByRole('button', { name: 'Due Date 달력 열기' })).toBeInTheDocument()
    expect(screen.getByRole('button', { name: '달력 열기' })).toBeInTheDocument()
  })

  it('is a plain button that never submits a form', async () => {
    const onSubmit = vi.fn((e: { preventDefault: () => void }) => e.preventDefault())
    render(
      <form onSubmit={onSubmit}>
        <Harness />
      </form>,
    )
    expect(calendarButton()).toHaveAttribute('type', 'button')
    await userEvent.click(calendarButton())
    expect(onSubmit).not.toHaveBeenCalled()
  })
})

describe('value sync (AC-D6, E4)', () => {
  it('shows the new value in yyyy.mm.dd when the parent changes it', () => {
    const { rerender } = render(<DateInput aria-label="견적일" value="2026-11-20" onChange={() => {}} />)
    expect(textBox()).toHaveValue('2026.11.20')
    rerender(<DateInput aria-label="견적일" value="2027-01-05" onChange={() => {}} />)
    expect(textBox()).toHaveValue('2027.01.05')
  })

  it('clears the text when the parent resets the value', () => {
    const { rerender } = render(<DateInput aria-label="견적일" value="2026-11-20" onChange={() => {}} />)
    rerender(<DateInput aria-label="견적일" value="" onChange={() => {}} />)
    expect(textBox()).toHaveValue('')
  })

  it('keeps a partly typed text when the parent echoes it back', async () => {
    render(<Harness />)
    await userEvent.type(textBox(), '2026.1')
    expect(textBox()).toHaveValue('2026.1')
  })

  it('keeps a one-digit day text while it is typed', async () => {
    render(<Harness />)
    await userEvent.type(textBox(), '2026.1.5')
    expect(textBox()).toHaveValue('2026.1.5')
  })

  it('shows a wrong text that the parent sends back as it is', () => {
    render(<DateInput aria-label="견적일" value="2026.13.4" onChange={() => {}} />)
    expect(textBox()).toHaveValue('2026.13.4')
  })
})

describe('props', () => {
  it('disables the text input, the button and gives the id and name', () => {
    render(<Harness disabled id="d1" name="due" />)
    expect(textBox()).toBeDisabled()
    expect(calendarButton()).toBeDisabled()
    expect(textBox()).toHaveAttribute('id', 'd1')
    expect(textBox()).toHaveAttribute('name', 'due')
  })

  it('is found by an outside label', () => {
    render(
      <>
        <label htmlFor="due">Due Date</label>
        <DateInput id="due" value="" onChange={() => {}} />
      </>,
    )
    expect(screen.getByLabelText('Due Date')).toHaveAttribute('inputmode', 'numeric')
    expect(screen.getByRole('button', { name: 'Due Date 달력 열기' })).toBeInTheDocument()
  })

  it('hands the text input to inputRef', () => {
    let seen: HTMLInputElement | null = null
    render(<DateInput aria-label="견적일" value="" onChange={() => {}} inputRef={(el) => (seen = el)} />)
    expect(seen).toBe(textBox())
  })

  it('marks the text input with data-autofocus when autoFocus is set', () => {
    // eslint-disable-next-line jsx-a11y/no-autofocus -- DateInput의 autoFocus prop 계약을 검증한다
    render(<Harness autoFocus />)
    expect(textBox()).toHaveAttribute('data-autofocus')
  })

  it('calls onBlur when the text input is left', async () => {
    const onBlur = vi.fn()
    render(<Harness onBlur={onBlur} />)
    textBox().focus()
    await userEvent.tab()
    expect(onBlur).toHaveBeenCalled()
  })

  it('marks the text input required', () => {
    render(<Harness required />)
    expect(textBox()).toBeRequired()
  })
})

describe('stateful wrapper sanity', () => {
  it('can be driven by a real parent state', async () => {
    function Parent() {
      const [v, setV] = useState('')
      return (
        <>
          <DateInput aria-label="견적일" value={v} onChange={setV} />
          <output>{v}</output>
        </>
      )
    }
    render(<Parent />)
    await userEvent.type(textBox(), '20270601')
    expect(screen.getByRole('status')).toHaveTextContent('2027-06-01')
  })
})
