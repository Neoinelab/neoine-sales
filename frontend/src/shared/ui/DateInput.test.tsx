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

describe('typing', () => {
  // 테스트 코드: UI-001
  it('20261120을 치면 yyyy.mm.dd로 보이고 부모에게 ISO 값을 넘긴다', async () => {
    // given: 빈 "견적일" 칸
    const spy = vi.fn()
    render(<Harness spy={spy} />)
    // when: 20261120을 친다
    await userEvent.type(textBox(), '20261120')
    // then: 칸은 2026.11.20이고 부모가 마지막으로 받은 값은 ISO다
    expect(textBox()).toHaveValue('2026.11.20')
    expect(spy).toHaveBeenLastCalledWith('2026-11-20')
  })

  // 테스트 코드: UI-004
  it('덜 친 날짜는 친 글자 그대로 부모에게 넘긴다', async () => {
    // given: 빈 "견적일" 칸
    const spy = vi.fn()
    render(<Harness spy={spy} />)
    // when: 202611을 친다
    await userEvent.type(textBox(), '202611')
    // then: 칸과 부모가 받은 값이 모두 2026.11이다
    expect(textBox()).toHaveValue('2026.11')
    expect(spy).toHaveBeenLastCalledWith('2026.11')
  })

  // 테스트 코드: UI-004
  it('없는 날짜는 친 글자 그대로 부모에게 넘긴다', async () => {
    // given: 빈 "견적일" 칸
    const spy = vi.fn()
    render(<Harness spy={spy} />)
    // when: 20261304를 친다
    await userEvent.type(textBox(), '20261304')
    // then: 칸과 부모가 받은 값이 모두 2026.13.04다
    expect(textBox()).toHaveValue('2026.13.04')
    expect(spy).toHaveBeenLastCalledWith('2026.13.04')
  })

  // 테스트 코드: UI-002
  it.each(['2026-11-20', '2026/11/20', '2026.11.20'])('붙여넣은 %s는 2026.11.20으로 정리되고 ISO 값을 넘긴다', async (pasted) => {
    // given: 빈 "견적일" 칸
    const spy = vi.fn()
    render(<Harness spy={spy} />)
    // when: 날짜를 붙여넣는다
    fireEvent.change(textBox(), { target: { value: pasted } })
    // then: 같은 표기이고 부모는 ISO 값을 받는다
    expect(textBox()).toHaveValue('2026.11.20')
    expect(spy).toHaveBeenLastCalledWith('2026-11-20')
  })

  // 테스트 코드: UI-005
  it('칸을 벗어나면 한 자리 월·일을 두 자리로 채운다', async () => {
    // given: 빈 "견적일" 칸
    const spy = vi.fn()
    render(<Harness spy={spy} />)
    // when: 2026.1.5를 친다
    await userEvent.type(textBox(), '2026.1.5')
    // then: 치는 동안은 그대로 보인다
    expect(textBox()).toHaveValue('2026.1.5')
    // when: Tab으로 칸을 벗어난다
    await userEvent.tab()
    // then: 2026.01.05로 채워지고 부모는 ISO 값을 받는다
    expect(textBox()).toHaveValue('2026.01.05')
    expect(spy).toHaveBeenLastCalledWith('2026-01-05')
  })

  // 테스트 코드: UI-004
  it('칸을 지우면 부모에게 빈 값을 넘긴다', async () => {
    // given: 값이 2026-11-20인 칸
    const spy = vi.fn()
    render(<Harness initial="2026-11-20" spy={spy} />)
    // when: 칸을 모두 지운다
    await userEvent.clear(textBox())
    // then: 칸이 비고 부모는 ''을 받는다
    expect(textBox()).toHaveValue('')
    expect(spy).toHaveBeenLastCalledWith('')
  })

  // 테스트 코드: UI-021
  it('텍스트 칸은 숫자 입력 힌트와 placeholder를 가지고 maxlength가 없다', () => {
    // when: 칸을 그린다
    render(<Harness />)
    // then: type text·inputmode numeric·placeholder yyyymmdd·autocomplete off이고 maxlength가 없다
    expect(textBox()).toHaveAttribute('type', 'text')
    expect(textBox()).toHaveAttribute('inputmode', 'numeric')
    expect(textBox()).toHaveAttribute('placeholder', 'yyyymmdd')
    // 붙여넣기를 브라우저가 먼저 자르지 않게 maxlength를 두지 않는다(글자 정리는 formatDateTyping이 한다).
    expect(textBox()).not.toHaveAttribute('maxlength')
    expect(textBox()).toHaveAttribute('autocomplete', 'off')
  })
})

describe('paste', () => {
  // 테스트 코드: UI-002
  it.each([
    [' 2026-11-20', '2026.11.20'],
    ['2026. 11. 20.', '2026.11.20'],
    ['2026/11/20', '2026.11.20'],
  ])('붙여넣은 %j는 공백·끝 점을 버린 %j로 정리되고 ISO 값을 넘긴다', async (pasted, shown) => {
    // given: 포커스가 있는 빈 "견적일" 칸
    const spy = vi.fn()
    render(<Harness spy={spy} />)
    textBox().focus()
    // when: 글자를 붙여넣는다
    await userEvent.paste(pasted)
    // then: 정리된 표기이고 부모는 ISO 값을 받는다
    expect(textBox()).toHaveValue(shown)
    expect(spy).toHaveBeenLastCalledWith('2026-11-20')
  })
})

describe('caret', () => {
  // 테스트 코드: UI-020
  it('점을 Backspace로 지워도 캐럿이 끝으로 튀지 않는다', async () => {
    // given: 값이 2026-11-20인 칸의 점 뒤(위치 5)에 캐럿이 있다
    render(<Harness initial="2026-11-20" />)
    const input = textBox()
    input.focus()
    input.setSelectionRange(5, 5)
    // when: Backspace를 누른다
    await userEvent.keyboard('{Backspace}')
    // then: 캐럿이 3~5 사이이고 선택 범위가 없다
    // 앞 숫자 4개 뒤(또는 그 앞 숫자를 지운 경우 3개 뒤)에 있어야 하고 끝으로 튀면 안 된다.
    expect(input.selectionStart).toBeGreaterThanOrEqual(3)
    expect(input.selectionStart).toBeLessThanOrEqual(5)
    expect(input.selectionStart).toBe(input.selectionEnd)
  })

  // 테스트 코드: UI-020
  it('가운데에 숫자를 넣고 글자를 다시 만들어도 캐럿이 넣은 숫자 뒤에 남는다', async () => {
    // given: 값이 2026-11-02인 칸의 위치 6에 캐럿이 있다
    render(<Harness initial="2026-11-02" />)
    const input = textBox()
    input.focus()
    input.setSelectionRange(6, 6)
    // when: 2를 친다
    await userEvent.keyboard('2')
    // then: 캐럿 앞 숫자는 2026 1 2 = 6개이므로 다시 만든 글자에서 6번째 숫자 뒤(위치 7)다
    expect(input.selectionStart).toBe(7)
    expect(input.selectionEnd).toBe(7)
  })

  // 테스트 코드: UI-020
  it('이미 정리된 글자의 숫자를 바꿔도 캐럿이 그 자리에 남는다', async () => {
    // given: 값이 2026-11-20인 칸의 위치 2에 캐럿이 있다
    render(<Harness initial="2026-11-20" />)
    const input = textBox()
    input.focus()
    input.setSelectionRange(2, 2)
    // when: 9를 친다
    await userEvent.keyboard('9')
    // then: 캐럿은 위치 3이다
    expect(input.selectionStart).toBe(3)
  })
})

describe('own error message', () => {
  // 테스트 코드: UI-007
  it('입력하는 동안에는 문구도 aria-invalid도 없다', async () => {
    // given: 빈 칸
    render(<Harness />)
    // when: 2026.1을 친다
    await userEvent.type(textBox(), '2026.1')
    // then: alert와 aria-invalid가 없다
    expect(screen.queryByRole('alert')).not.toBeInTheDocument()
    expect(textBox()).not.toHaveAttribute('aria-invalid')
  })

  // 테스트 코드: UI-007
  it('덜 친 날짜로 칸을 벗어나면 형식 문구와 aria-invalid가 보인다', async () => {
    // given: 2026.1을 친 칸
    render(<Harness />)
    await userEvent.type(textBox(), '2026.1')
    // when: Tab으로 벗어난다
    await userEvent.tab()
    // then: 형식 문구와 aria-invalid="true"가 보인다
    expect(screen.getByRole('alert')).toHaveTextContent('날짜를 yyyymmdd 형식으로 입력하세요.')
    expect(textBox()).toHaveAttribute('aria-invalid', 'true')
  })

  // 테스트 코드: UI-008
  it('없는 날짜로 칸을 벗어나면 없는 날짜 문구가 보인다', async () => {
    // given: 20261304를 친 칸
    render(<Harness />)
    await userEvent.type(textBox(), '20261304')
    // when: Tab으로 벗어난다
    await userEvent.tab()
    // then: "없는 날짜입니다."가 보인다
    expect(screen.getByRole('alert')).toHaveTextContent('없는 날짜입니다.')
  })

  // 테스트 코드: UI-008
  it('1900년 전 날짜로 칸을 벗어나면 범위 문구가 보인다', async () => {
    // given: 18991231을 친 칸
    render(<Harness />)
    await userEvent.type(textBox(), '18991231')
    // when: Tab으로 벗어난다
    await userEvent.tab()
    // then: 범위 문구가 보인다
    expect(screen.getByRole('alert')).toHaveTextContent('1900.01.01부터 2999.12.31 사이로 입력하세요.')
  })

  // 테스트 코드: UI-008
  it('틀린 날짜에서 Enter를 눌러도 문구가 보인다', async () => {
    // given: 빈 칸
    render(<Harness />)
    // when: 20260230을 치고 Enter를 누른다
    await userEvent.type(textBox(), '20260230{Enter}')
    // then: "없는 날짜입니다."가 보인다
    expect(screen.getByRole('alert')).toHaveTextContent('없는 날짜입니다.')
  })

  // 테스트 코드: UI-009
  it('날짜를 고치면 문구와 aria-invalid가 사라진다', async () => {
    // given: 20260230을 치고 벗어나 문구가 보이는 칸
    render(<Harness />)
    await userEvent.type(textBox(), '20260230')
    await userEvent.tab()
    expect(screen.getByRole('alert')).toBeVisible()
    // when: 칸을 지우고 20260228을 친 뒤 벗어난다
    await userEvent.clear(textBox())
    await userEvent.type(textBox(), '20260228')
    await userEvent.tab()
    // then: 문구와 aria-invalid가 없다
    expect(screen.queryByRole('alert')).not.toBeInTheDocument()
    expect(textBox()).not.toHaveAttribute('aria-invalid')
  })

  // 테스트 코드: UI-009
  it('빈 칸을 벗어나도 문구가 없다', async () => {
    // given: 포커스를 준 빈 칸
    render(<Harness />)
    textBox().focus()
    // when: Tab으로 벗어난다
    await userEvent.tab()
    // then: 문구가 없다
    expect(screen.queryByRole('alert')).not.toBeInTheDocument()
  })

  // 테스트 코드: UI-010
  it('날짜는 올바른데 부모 오류가 있으면 부모 문구를 보인다', () => {
    // given: 부모 error "견적 제출일을 입력하세요."를 받은 칸
    // when: 그린다
    render(<Harness error="견적 제출일을 입력하세요." />)
    // then: 부모 문구와 aria-invalid="true"가 보인다
    expect(screen.getByRole('alert')).toHaveTextContent('견적 제출일을 입력하세요.')
    expect(textBox()).toHaveAttribute('aria-invalid', 'true')
  })

  // 테스트 코드: UI-010
  it('자체 문구가 있으면 부모 오류보다 자체 문구를 보인다', async () => {
    // given: 부모 error "부모 오류"를 받은 칸
    render(<Harness error="부모 오류" />)
    // when: 2026.1을 치고 벗어난다
    await userEvent.type(textBox(), '2026.1')
    await userEvent.tab()
    // then: 자체 형식 문구만 보이고 "부모 오류"는 없다
    expect(screen.getByRole('alert')).toHaveTextContent('날짜를 yyyymmdd 형식으로 입력하세요.')
    expect(screen.queryByText('부모 오류')).not.toBeInTheDocument()
  })

  // 테스트 코드: UI-010
  it('문구를 칸에 연결하면서 부모 설명도 함께 가리킨다', async () => {
    // given: 부모 설명 id hint를 받은 칸
    render(
      <>
        <p id="hint">안내</p>
        <Harness aria-describedby="hint" />
      </>,
    )
    // when: 2026.1을 치고 벗어난다
    await userEvent.type(textBox(), '2026.1')
    await userEvent.tab()
    // then: aria-describedby에 hint와 문구 요소 id가 모두 있다
    const alert = screen.getByRole('alert')
    const described = (textBox().getAttribute('aria-describedby') ?? '').split(/\s+/)
    expect(described).toContain('hint')
    expect(described).toContain(alert.id)
    expect(alert.id).not.toBe('')
  })

  // 테스트 코드: UI-011
  it('quiet이면 자체 문구를 내지 않고 부모 invalid로만 aria-invalid가 켜진다', async () => {
    // given: quiet인 칸과 quiet이면서 invalid인 칸
    render(
      <>
        <Harness aria-label="칸 A" quiet />
        <Harness quiet invalid />
      </>,
    )
    const quietBox = screen.getByRole<HTMLInputElement>('textbox', { name: '칸 A' })
    // when: 칸 A에 2026.1을 치고 벗어난다
    await userEvent.type(quietBox, '2026.1')
    await userEvent.tab()
    // when: 칸 B에도 2026.1을 치고 벗어난다
    await userEvent.type(textBox(), '2026.1')
    await userEvent.tab()
    // then: 두 칸 모두 alert 문구가 없다
    expect(screen.queryByRole('alert')).not.toBeInTheDocument()
    // then: A는 aria-invalid가 없고 B는 부모 invalid로 aria-invalid="true"다
    expect(quietBox).not.toHaveAttribute('aria-invalid')
    expect(textBox()).toHaveAttribute('aria-invalid', 'true')
  })
})

describe('Enter', () => {
  // 테스트 코드: UI-013
  it('Enter는 글자를 확정해 값을 onEnter로 넘기고 폼을 제출하지 않는다', async () => {
    // given: 폼 안의 onEnter가 있는 칸
    const onEnter = vi.fn()
    const onSubmit = vi.fn((e: { preventDefault: () => void }) => e.preventDefault())
    render(
      <form onSubmit={onSubmit}>
        <Harness onEnter={onEnter} />
        <button type="submit">제출</button>
      </form>,
    )
    // when: 2026.1.5를 치고 Enter를 누른다
    await userEvent.type(textBox(), '2026.1.5{Enter}')
    // then: 2026.01.05로 확정되고 onEnter는 ISO 값으로 한 번 불리며 제출은 없다
    expect(textBox()).toHaveValue('2026.01.05')
    expect(onEnter).toHaveBeenCalledTimes(1)
    expect(onEnter).toHaveBeenCalledWith('2026-01-05')
    expect(onSubmit).not.toHaveBeenCalled()
  })

  // 테스트 코드: UI-013
  it('틀린 날짜는 친 글자 그대로 onEnter로 넘겨 부모가 거절할 수 있다', async () => {
    // given: onEnter가 있는 칸
    const onEnter = vi.fn()
    render(<Harness onEnter={onEnter} />)
    // when: 2026.13.04를 치고 Enter를 누른다
    await userEvent.type(textBox(), '2026.13.04{Enter}')
    // then: onEnter가 글자 그대로 불린다
    expect(onEnter).toHaveBeenCalledWith('2026.13.04')
  })

  // 테스트 코드: UI-013
  it('빈 칸의 Enter는 빈 값을 onEnter로 넘긴다', async () => {
    // given: 포커스가 있는 빈 칸
    const onEnter = vi.fn()
    render(<Harness onEnter={onEnter} />)
    textBox().focus()
    // when: Enter를 누른다
    await userEvent.keyboard('{Enter}')
    // then: onEnter('')이다
    expect(onEnter).toHaveBeenCalledWith('')
  })

  // 테스트 코드: UI-013
  it('onEnter가 없으면 폼 기본 동작대로 제출된다', async () => {
    // given: 폼 안의 onEnter가 없는 칸
    const onSubmit = vi.fn((e: { preventDefault: () => void }) => e.preventDefault())
    render(
      <form onSubmit={onSubmit}>
        <Harness />
        <button type="submit">제출</button>
      </form>,
    )
    // when: 20261120을 치고 Enter를 누른다
    await userEvent.type(textBox(), '20261120{Enter}')
    // then: 폼이 한 번 제출된다
    expect(onSubmit).toHaveBeenCalledTimes(1)
  })

  // 테스트 코드: UI-014
  it('입력 조합 중의 Enter는 확정도 onEnter도 하지 않는다', () => {
    // given: onEnter가 있고 2026.1.5를 친 칸
    const onEnter = vi.fn()
    render(<Harness onEnter={onEnter} initial="2026.1.5" />)
    // when: 입력 조합 중(isComposing) Enter 키 이벤트가 온다
    fireEvent.keyDown(textBox(), { key: 'Enter', isComposing: true })
    // then: 칸은 그대로이고 onEnter는 불리지 않는다
    expect(textBox()).toHaveValue('2026.1.5')
    expect(onEnter).not.toHaveBeenCalled()
  })
})

describe('calendar', () => {
  // 테스트 코드: UI-015
  it('달력 버튼은 숨은 칸의 달력(showPicker)을 연다', async () => {
    // given: showPicker가 있는 브라우저
    const showPicker = stubShowPicker()
    const { container } = render(<Harness />)
    // when: 달력 버튼을 누른다
    await userEvent.click(calendarButton())
    // then: 숨은 날짜 칸의 showPicker가 한 번 불린다
    expect(showPicker).toHaveBeenCalledTimes(1)
    expect(showPicker.mock.contexts[0]).toBe(nativeOf(container))
  })

  // 테스트 코드: UI-015
  it('showPicker가 없으면 숨은 칸에 포커스를 주고 클릭한다', async () => {
    // given: showPicker가 없는 브라우저
    const { container } = render(<Harness />)
    const native = nativeOf(container)
    const onClick = vi.fn()
    native.addEventListener('click', onClick)
    // when: 달력 버튼을 누른다
    await userEvent.click(calendarButton())
    // then: 숨은 칸이 포커스를 받고 클릭이 한 번 일어난다
    expect(document.activeElement).toBe(native)
    expect(onClick).toHaveBeenCalledTimes(1)
  })

  // 테스트 코드: UI-015
  it('showPicker가 거부되면 같은 방식으로 숨은 칸을 클릭한다', async () => {
    // given: showPicker가 NotAllowedError를 던지는 브라우저
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
    // when: 달력 버튼을 누른다
    await userEvent.click(calendarButton())
    // then: 숨은 칸 클릭이 한 번 일어난다
    expect(onClick).toHaveBeenCalledTimes(1)
  })

  // 테스트 코드: UI-018
  it('숨은 칸은 Tab 순서와 접근성 트리 밖이지만 display none은 아니다', () => {
    // when: 칸을 그린다
    const { container } = render(<Harness />)
    // then: 숨은 날짜 칸의 속성이 계약대로다
    const native = nativeOf(container)
    expect(native).toHaveAttribute('tabindex', '-1')
    expect(native).toHaveAttribute('aria-hidden', 'true')
    expect(native).toHaveAttribute('min', '1900-01-01')
    expect(native).toHaveAttribute('max', '2999-12-31')
    expect(native.className).toContain('date-input-native')
    expect(native.style.display).not.toBe('none')
  })

  // 테스트 코드: UI-016
  it('달력에서 고른 날짜는 칸에 보이고 값·포커스·onPicked로 이어진다', () => {
    // given: onPicked가 있는 빈 칸
    const spy = vi.fn()
    const onPicked = vi.fn()
    const { container } = render(<Harness spy={spy} onPicked={onPicked} />)
    // when: 숨은 칸에서 2026-12-01을 고른다
    fireEvent.change(nativeOf(container), { target: { value: '2026-12-01' } })
    // then: 칸에 보이고 부모와 onPicked가 ISO 값을 받으며 포커스는 텍스트 칸이다
    expect(textBox()).toHaveValue('2026.12.01')
    expect(spy).toHaveBeenLastCalledWith('2026-12-01')
    expect(onPicked).toHaveBeenCalledWith('2026-12-01')
    expect(document.activeElement).toBe(textBox())
  })

  // 테스트 코드: UI-016
  it('달력은 현재 값으로 열린다', () => {
    // given: 값이 2026-11-20인 칸
    // when: 그린다
    const { container } = render(<Harness initial="2026-11-20" />)
    // then: 숨은 칸의 값이 2026-11-20이다
    expect(nativeOf(container)).toHaveValue('2026-11-20')
  })

  // 테스트 코드: UI-016
  it('올바른 날짜가 아니면 달력에 값을 주지 않는다', async () => {
    // given: 빈 칸
    const { container } = render(<Harness />)
    // when: 2026.1을 친다
    await userEvent.type(textBox(), '2026.1')
    // then: 숨은 칸의 값이 비어 있다
    expect(nativeOf(container)).toHaveValue('')
  })

  // 테스트 코드: UI-017
  it('달력이 범위 밖 값을 주면 무시하고 빈 값을 주면 칸을 비운다', () => {
    // given: 값이 2026-11-20인 칸
    const spy = vi.fn()
    const { container } = render(<Harness initial="2026-11-20" spy={spy} />)
    // when: 숨은 칸 값이 3000-01-01로 바뀐다
    fireEvent.change(nativeOf(container), { target: { value: '3000-01-01' } })
    // then: 칸은 그대로이고 onChange는 불리지 않는다
    expect(textBox()).toHaveValue('2026.11.20')
    expect(spy).not.toHaveBeenCalled()
    // when: 숨은 칸 값이 빈 값으로 바뀐다
    fireEvent.change(nativeOf(container), { target: { value: '' } })
    // then: 칸이 비고 부모는 ''을 받는다
    expect(textBox()).toHaveValue('')
    expect(spy).toHaveBeenLastCalledWith('')
  })

  // 테스트 코드: UI-018
  it('달력 버튼 이름은 칸 이름을 따르고 이름이 없으면 달력 열기만이다', () => {
    // when: 이름이 있는 칸과 없는 칸을 그린다
    render(
      <>
        <DateInput aria-label="Due Date" value="" onChange={() => {}} />
        <DateInput value="" onChange={() => {}} />
      </>,
    )
    // then: "Due Date 달력 열기"와 "달력 열기" 버튼이 있다
    expect(screen.getByRole('button', { name: 'Due Date 달력 열기' })).toBeInTheDocument()
    expect(screen.getByRole('button', { name: '달력 열기' })).toBeInTheDocument()
  })

  // 테스트 코드: UI-018
  it('달력 버튼은 폼을 제출하지 않는 일반 버튼이다', async () => {
    // given: 폼 안의 칸
    const onSubmit = vi.fn((e: { preventDefault: () => void }) => e.preventDefault())
    render(
      <form onSubmit={onSubmit}>
        <Harness />
      </form>,
    )
    // then: 버튼 type은 button이다
    expect(calendarButton()).toHaveAttribute('type', 'button')
    // when: 달력 버튼을 누른다
    await userEvent.click(calendarButton())
    // then: 폼 제출이 없다
    expect(onSubmit).not.toHaveBeenCalled()
  })
})

describe('value sync', () => {
  // 테스트 코드: UI-019
  it('부모가 값을 바꾸면 새 값을 yyyy.mm.dd로 보인다', () => {
    // given: 값이 2026-11-20인 칸
    const { rerender } = render(<DateInput aria-label="견적일" value="2026-11-20" onChange={() => {}} />)
    expect(textBox()).toHaveValue('2026.11.20')
    // when: 부모가 값을 2027-01-05로 바꾼다
    rerender(<DateInput aria-label="견적일" value="2027-01-05" onChange={() => {}} />)
    // then: 칸이 2027.01.05로 바뀐다
    expect(textBox()).toHaveValue('2027.01.05')
  })

  // 테스트 코드: UI-019
  it('부모가 값을 비우면 칸도 빈다', () => {
    // given: 값이 2026-11-20인 칸
    const { rerender } = render(<DateInput aria-label="견적일" value="2026-11-20" onChange={() => {}} />)
    // when: 부모가 값을 ''로 바꾼다
    rerender(<DateInput aria-label="견적일" value="" onChange={() => {}} />)
    // then: 칸이 빈다
    expect(textBox()).toHaveValue('')
  })

  // 테스트 코드: UI-019
  it('부모가 받은 값을 되돌려 줘도 덜 친 글자는 그대로다', async () => {
    // given: 부모 상태와 연결된 빈 칸
    render(<Harness />)
    // when: 2026.1을 친다
    await userEvent.type(textBox(), '2026.1')
    // then: 2026.1 그대로다
    expect(textBox()).toHaveValue('2026.1')
  })

  // 테스트 코드: UI-019
  it('한 자리 일을 치는 동안 글자가 그대로다', async () => {
    // given: 부모 상태와 연결된 빈 칸
    render(<Harness />)
    // when: 2026.1.5를 친다
    await userEvent.type(textBox(), '2026.1.5')
    // then: 2026.1.5 그대로다
    expect(textBox()).toHaveValue('2026.1.5')
  })

  // 테스트 코드: UI-019
  it('부모가 준 틀린 글자는 그대로 보인다', () => {
    // given: 부모가 값 2026.13.4를 준 칸
    // when: 그린다
    render(<DateInput aria-label="견적일" value="2026.13.4" onChange={() => {}} />)
    // then: 2026.13.4 그대로 보인다
    expect(textBox()).toHaveValue('2026.13.4')
  })
})

describe('props', () => {
  // 테스트 코드: UI-021
  it('disabled는 텍스트 칸과 버튼에 주고 id·name은 텍스트 칸에 준다', () => {
    // given: id·name·disabled를 받은 칸
    // when: 그린다
    render(<Harness disabled id="d1" name="due" />)
    // then: 텍스트 칸과 달력 버튼이 비활성이고 id·name이 있다
    expect(textBox()).toBeDisabled()
    expect(calendarButton()).toBeDisabled()
    expect(textBox()).toHaveAttribute('id', 'd1')
    expect(textBox()).toHaveAttribute('name', 'due')
  })

  // 테스트 코드: UI-018
  it('바깥 label로 칸을 찾고 달력 버튼 이름도 그 글자를 따른다', () => {
    // given: 바깥 label "Due Date"가 연결된 칸
    // when: 그린다
    render(
      <>
        <label htmlFor="due">Due Date</label>
        <DateInput id="due" value="" onChange={() => {}} />
      </>,
    )
    // then: 라벨로 칸을 찾고 버튼 이름은 "Due Date 달력 열기"다
    expect(screen.getByLabelText('Due Date')).toHaveAttribute('inputmode', 'numeric')
    expect(screen.getByRole('button', { name: 'Due Date 달력 열기' })).toBeInTheDocument()
  })

  // 테스트 코드: UI-021
  it('inputRef는 텍스트 칸을 가리킨다', () => {
    // given: inputRef를 받은 칸
    let seen: HTMLInputElement | null = null
    // when: 그린다
    render(<DateInput aria-label="견적일" value="" onChange={() => {}} inputRef={(el) => (seen = el)} />)
    // then: ref가 텍스트 칸이다
    expect(seen).toBe(textBox())
  })

  // 테스트 코드: UI-021
  it('autoFocus면 텍스트 칸에 data-autofocus를 붙인다', () => {
    // given: autoFocus를 받은 칸
    // when: 그린다
    // eslint-disable-next-line jsx-a11y/no-autofocus -- DateInput의 autoFocus prop 계약을 검증한다
    render(<Harness autoFocus />)
    // then: data-autofocus가 붙는다
    expect(textBox()).toHaveAttribute('data-autofocus')
  })

  // 테스트 코드: UI-021
  it('텍스트 칸을 벗어나면 onBlur를 부른다', async () => {
    // given: onBlur를 받은 칸에 포커스가 있다
    const onBlur = vi.fn()
    render(<Harness onBlur={onBlur} />)
    textBox().focus()
    // when: Tab으로 벗어난다
    await userEvent.tab()
    // then: onBlur가 불린다
    expect(onBlur).toHaveBeenCalled()
  })

  // 테스트 코드: UI-021
  it('required를 텍스트 칸에 준다', () => {
    // given: required를 받은 칸
    // when: 그린다
    render(<Harness required />)
    // then: 텍스트 칸이 required다
    expect(textBox()).toBeRequired()
  })
})

describe('stateful wrapper sanity', () => {
  // 테스트 코드: UI-001
  it('실제 부모 상태로 구동하면 부모 상태에 ISO 값이 보인다', async () => {
    // given: 부모 상태를 화면에 보이는 칸
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
    // when: 20270601을 친다
    await userEvent.type(textBox(), '20270601')
    // then: 부모 상태가 2027-06-01이다
    expect(screen.getByRole('status')).toHaveTextContent('2027-06-01')
  })
})
