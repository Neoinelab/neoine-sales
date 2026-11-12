import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { describe, expect, it, vi } from 'vitest'
import { CheckboxField, SelectField, TextArea, TextField } from './fields'

describe('기본 입력 필드', () => {
  // 테스트 코드: UI-061
  it('TextField는 라벨로 찾고 치면 새 값을 알리며 invalid면 aria-invalid를 켠다', async () => {
    // given: invalid인 "이름" 칸
    const onChange = vi.fn()
    render(<TextField label="이름" name="name" value="" onChange={onChange} invalid />)
    const input = screen.getByLabelText('이름')
    // then: aria-invalid가 켜져 있다
    expect(input).toHaveAttribute('aria-invalid', 'true')
    // when: 글자를 친다
    await userEvent.type(input, '김')
    // then: onChange가 새 값으로 불린다
    expect(onChange).toHaveBeenCalledWith('김')
  })

  // 테스트 코드: UI-061
  it('TextField는 invalid가 아니면 aria-invalid가 없다', () => {
    // when: invalid 없이 그린다
    render(<TextField label="이름" name="name" value="" onChange={() => {}} />)
    // then: aria-invalid가 없다
    expect(screen.getByLabelText('이름')).not.toHaveAttribute('aria-invalid')
  })

  // 테스트 코드: UI-061
  it('TextArea는 라벨로 찾고 3줄이며 치면 새 값을 알린다', async () => {
    // given: "메모" 여러 줄 칸
    const onChange = vi.fn()
    render(<TextArea label="메모" name="memo" value="" onChange={onChange} />)
    const area = screen.getByLabelText('메모')
    // then: 3줄이다
    expect(area).toHaveAttribute('rows', '3')
    // when: 글자를 친다
    await userEvent.type(area, '가')
    // then: onChange가 새 값으로 불린다
    expect(onChange).toHaveBeenCalledWith('가')
  })

  // 테스트 코드: UI-061
  it('SelectField는 라벨로 찾고 고르면 새 값을 알린다', async () => {
    // given: "역할" 선택 칸
    const onChange = vi.fn()
    render(
      <SelectField label="역할" name="role" value="user" onChange={onChange}>
        <option value="user">user</option>
        <option value="admin">admin</option>
      </SelectField>,
    )
    // when: admin을 고른다
    await userEvent.selectOptions(screen.getByLabelText('역할'), 'admin')
    // then: onChange('admin')이다
    expect(onChange).toHaveBeenCalledWith('admin')
  })

  // 테스트 코드: UI-061
  it('CheckboxField는 라벨로 찾고 체크하면 참을 알린다', async () => {
    // given: 체크 안 된 "내 딜만" 칸
    const onChange = vi.fn()
    render(<CheckboxField label="내 딜만" name="mine" checked={false} onChange={onChange} />)
    // when: 체크한다
    await userEvent.click(screen.getByLabelText('내 딜만'))
    // then: onChange(true)이다
    expect(onChange).toHaveBeenCalledWith(true)
  })

  // 테스트 코드: UI-061
  it('type이 date인 TextField는 native 날짜 칸이 아니라 DateInput이다', () => {
    // given: 라벨 "시작일"·name "from"·type date인 TextField
    // when: 그린다
    render(<TextField label="시작일" name="from" type="date" value="" onChange={() => {}} />)
    // then: id from-date의 숫자 입력 텍스트 칸과 "시작일 달력 열기" 버튼이 있고 type은 text다
    const input = screen.getByLabelText('시작일')
    expect(input).toHaveAttribute('id', 'from-date')
    expect(input).toHaveAttribute('inputmode', 'numeric')
    expect(input).toHaveAttribute('type', 'text')
    expect(screen.getByRole('button', { name: '시작일 달력 열기' })).toBeInTheDocument()
  })
})
