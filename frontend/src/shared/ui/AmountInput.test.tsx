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
  // 테스트 코드: UI-023
  it('치는 동안 세 자리마다 콤마를 넣는다', async () => {
    // given: 빈 금액 칸
    const spy = vi.fn()
    render(<Harness spy={spy} />)
    // when: 1234567을 친다
    await userEvent.type(screen.getByLabelText('금액'), '1234567')
    // then: 칸과 부모가 받은 글자가 모두 콤마 숫자다
    expect(screen.getByLabelText('금액')).toHaveValue('1,234,567')
    expect(spy).toHaveBeenLastCalledWith('1,234,567')
  })

  // 테스트 코드: UI-024
  it('숫자를 끼워 넣어도 캐럿이 넣은 숫자 뒤에 남는다', async () => {
    // given: 1,234가 든 칸의 첫 숫자 뒤에 캐럿이 있다
    render(<Harness initial="1,234" />)
    const input = screen.getByLabelText<HTMLInputElement>('금액')
    input.focus()
    input.setSelectionRange(1, 1)
    // when: 9를 친다
    await userEvent.keyboard('9')
    // then: 19,234이고 캐럿은 숫자 2개 뒤다
    expect(input).toHaveValue('19,234')
    expect(input.selectionStart).toBe(2)
  })

  // 테스트 코드: UI-023
  it('숫자가 아닌 글자는 버리고 숫자만 남긴다', async () => {
    // given: 빈 금액 칸
    render(<Harness />)
    // when: 12a3.4 5를 친다
    await userEvent.type(screen.getByLabelText('금액'), '12a3.4 5')
    // then: 숫자만 남아 12,345다
    expect(screen.getByLabelText('금액')).toHaveValue('12,345')
  })

  // 테스트 코드: UI-024
  it('콤마만 Backspace로 지우면 글자는 그대로이고 캐럿은 콤마 앞에 남는다', async () => {
    // given: 1,234가 든 칸의 콤마 뒤에 캐럿이 있다
    render(<Harness initial="1,234" />)
    const input = screen.getByLabelText<HTMLInputElement>('금액')
    input.focus()
    input.setSelectionRange(2, 2)
    // when: Backspace를 누른다
    await userEvent.keyboard('{Backspace}')
    // then: 글자는 1,234 그대로이고 캐럿은 숫자 1개 뒤다
    expect(input).toHaveValue('1,234')
    expect(input.selectionStart).toBe(1)
  })

  // 테스트 코드: UI-024
  it('버려지는 글자를 치면 글자와 캐럿이 그대로다', async () => {
    // given: 1,234가 든 칸의 첫 숫자 뒤에 캐럿이 있다
    render(<Harness initial="1,234" />)
    const input = screen.getByLabelText<HTMLInputElement>('금액')
    input.focus()
    input.setSelectionRange(1, 1)
    // when: x를 친다
    await userEvent.keyboard('x')
    // then: 글자와 캐럿이 그대로다
    expect(input).toHaveValue('1,234')
    expect(input.selectionStart).toBe(1)
  })

  // 테스트 코드: UI-025
  it('붙여넣은 소수점 금액은 숫자만 남는다', async () => {
    // given: 빈 금액 칸
    render(<Harness />)
    const input = screen.getByLabelText<HTMLInputElement>('금액')
    input.focus()
    // when: 1,500,000.50을 붙여넣는다
    await userEvent.paste('1,500,000.50')
    // then: 점이 버려져 150,000,050이다
    expect(input).toHaveValue('150,000,050')
  })

  // 테스트 코드: UI-025
  it('앞자리 0은 지워진다', async () => {
    // given: 빈 금액 칸
    render(<Harness />)
    // when: 007을 친다
    await userEvent.type(screen.getByLabelText('금액'), '007')
    // then: 7이다
    expect(screen.getByLabelText('금액')).toHaveValue('7')
  })

  // 테스트 코드: UI-026
  it('단위 글자 없이 입력 칸 하나만 그린다', () => {
    // given: 값이 1,234인 금액 칸
    // when: 그린다
    const { container } = render(<Harness initial="1,234" />)
    // then: 천원 등 단위 글자가 없고 입력 칸이 하나다
    expect(container.textContent).not.toContain('천원')
    expect(container.querySelectorAll('input')).toHaveLength(1)
  })
})
