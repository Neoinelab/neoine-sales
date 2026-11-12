import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { createRef, useState } from 'react'
import { describe, expect, it, vi } from 'vitest'
import { ComboBox, type ComboOption } from './ComboBox'
import { Modal } from './Modal'

const OPTIONS: ComboOption[] = [
  { value: '한빛상사', label: '한빛상사' },
  { value: '하나솔루션', label: '하나솔루션' },
  { value: '대한소프트', label: '대한소프트', description: '3명' },
]

const LATIN: ComboOption[] = [{ value: 'Alpha' }, { value: 'alphabet' }, { value: 'Beta' }]

function Host({
  onSelect,
  transform,
  openOnFocus,
  options = OPTIONS,
  initial = '',
  label = '회사명',
}: {
  onSelect?: (o: ComboOption) => void
  transform?: (raw: string) => string
  openOnFocus?: boolean
  options?: ComboOption[]
  initial?: string
  label?: string
}) {
  const [value, setValue] = useState(initial)
  return (
    <ComboBox label={label} name="company" value={value} onChange={setValue} options={options} onSelectOption={onSelect} transform={transform} openOnFocus={openOnFocus} />
  )
}

describe('ComboBox', () => {
  // 테스트 코드: UI-032
  it('접근 이름이 있는 콤보박스를 누르면 후보 목록이 열린다', async () => {
    // given: 라벨 "회사명"에 후보 3개인 콤보박스
    render(<Host />)
    // when: 칸을 누른다
    await userEvent.click(screen.getByRole('combobox', { name: '회사명' }))
    // then: 목록에 항목 3개가 보인다
    expect(screen.getByRole('listbox')).toBeInTheDocument()
    expect(screen.getAllByRole('option')).toHaveLength(3)
  })

  // 테스트 코드: UI-035
  it('마우스로 항목을 누르면 값을 채우고 선택을 알리며 목록이 닫힌다', async () => {
    // given: 목록을 연 콤보박스(onSelectOption 연결)
    const onSelect = vi.fn()
    render(<Host onSelect={onSelect} />)
    await userEvent.click(screen.getByRole('combobox', { name: '회사명' }))
    // when: 대한소프트 항목을 누른다
    await userEvent.click(screen.getByRole('option', { name: /대한소프트/ }))
    // then: 값이 채워지고 선택이 알려지며 목록이 닫힌다
    expect(screen.getByRole('combobox', { name: '회사명' })).toHaveValue('대한소프트')
    expect(onSelect).toHaveBeenCalledWith(OPTIONS[2])
    expect(screen.queryByRole('listbox')).not.toBeInTheDocument()
  })

  // 테스트 코드: UI-035
  it('목록에 없는 글자를 직접 쳐도 입력되고 선택 알림은 없다', async () => {
    // given: onSelectOption이 연결된 콤보박스
    const onSelect = vi.fn()
    render(<Host onSelect={onSelect} />)
    // when: 목록에 없는 새회사를 친다
    await userEvent.type(screen.getByRole('combobox', { name: '회사명' }), '새회사')
    // then: 값이 그대로 들어가고 onSelectOption은 불리지 않는다
    expect(screen.getByRole('combobox', { name: '회사명' })).toHaveValue('새회사')
    expect(onSelect).not.toHaveBeenCalled()
  })

  // 테스트 코드: UI-034
  it('친 글자로 후보를 거른다', async () => {
    // given: 후보 3개인 콤보박스
    render(<Host />)
    // when: 하를 친다
    await userEvent.type(screen.getByRole('combobox', { name: '회사명' }), '하')
    // then: 하나솔루션만 남는다
    expect(screen.getAllByRole('option').map((o) => o.textContent)).toEqual(['하나솔루션'])
  })

  // 테스트 코드: UI-034
  it('대소문자를 가리지 않고 부분 일치하는 후보만 보인다', async () => {
    // given: 후보 Alpha·alphabet·Beta인 콤보박스
    render(<Host options={LATIN} />)
    // when: ALP를 친다
    await userEvent.type(screen.getByRole('combobox', { name: '회사명' }), 'ALP')
    // then: Alpha와 alphabet만 보인다
    expect(screen.getAllByRole('option').map((o) => o.textContent)).toEqual(['Alpha', 'alphabet'])
  })

  // 테스트 코드: UI-034
  it('입력이 후보 값과 대소문자 무시로 같으면 후보 전체를 보인다', async () => {
    // given: 값이 alpha(후보 Alpha와 대소문자만 다름)인 콤보박스
    render(<Host options={LATIN} initial="alpha" />)
    // when: 칸을 연다
    await userEvent.click(screen.getByRole('combobox', { name: '회사명' }))
    // then: 후보 3개 전부 보인다
    expect(screen.getAllByRole('option').map((o) => o.textContent)).toEqual(['Alpha', 'alphabet', 'Beta'])
  })

  // 테스트 코드: UI-035
  it('방향키로 항목을 옮기고 Enter로 고르며 Esc로 목록을 닫는다', async () => {
    // given: 목록을 연 콤보박스
    const onSelect = vi.fn()
    render(<Host onSelect={onSelect} />)
    const input = screen.getByRole('combobox', { name: '회사명' })
    await userEvent.click(input)
    // when: ↓ 두 번을 누른다
    await userEvent.keyboard('{ArrowDown}{ArrowDown}')
    // then: 둘째 항목이 활성이다
    expect(input).toHaveAttribute('aria-activedescendant', screen.getAllByRole('option')[1]?.id)
    // when: Enter를 누른다
    await userEvent.keyboard('{Enter}')
    // then: 하나솔루션이 선택된다
    expect(onSelect).toHaveBeenCalledWith(OPTIONS[1])
    expect(input).toHaveValue('하나솔루션')
    // when: 다시 ↓를 누른다
    await userEvent.keyboard('{ArrowDown}')
    // then: 목록이 열린다
    expect(screen.getByRole('listbox')).toBeInTheDocument()
    // when: Esc를 누른다
    await userEvent.keyboard('{Escape}')
    // then: 목록이 닫힌다
    expect(screen.queryByRole('listbox')).not.toBeInTheDocument()
  })

  // 테스트 코드: UI-036
  it('모달 안 콤보박스의 Esc는 열린 목록만 닫고 모달은 남는다', async () => {
    // given: 모달 "Action 추가" 안에서 목록이 열린 콤보박스
    const onClose = vi.fn()
    render(
      <Modal title="Action 추가" onClose={onClose}>
        <Host />
      </Modal>,
    )
    await userEvent.click(screen.getByRole('combobox', { name: '회사명' }))
    expect(screen.getByRole('listbox')).toBeInTheDocument()
    // when: Esc를 누른다
    await userEvent.keyboard('{Escape}')
    // then: 목록만 닫히고 모달 onClose는 불리지 않는다
    expect(screen.queryByRole('listbox')).not.toBeInTheDocument()
    expect(onClose).not.toHaveBeenCalled()
    // when: 목록이 닫힌 채 Esc를 한 번 더 누른다
    await userEvent.keyboard('{Escape}')
    // then: 모달 onClose가 한 번 불린다
    expect(onClose).toHaveBeenCalledTimes(1)
  })

  // 테스트 코드: UI-037
  it('transform을 거친 글자가 값이 된다', async () => {
    // given: 공백을 지우는 transform을 단 콤보박스
    render(<Host transform={(raw) => raw.replace(/\s/g, '')} />)
    // when: a b c를 친다
    await userEvent.type(screen.getByRole('combobox', { name: '회사명' }), 'a b c')
    // then: 값은 abc다
    expect(screen.getByRole('combobox', { name: '회사명' })).toHaveValue('abc')
  })

  // 테스트 코드: UI-037
  it('오류 문구를 칸 아래에 보이고 칸을 invalid로 표시한다', () => {
    // given: error "회사명을 입력하세요."를 받은 콤보박스
    // when: 그린다
    render(<ComboBox label="회사명" name="c" value="" onChange={() => {}} options={[]} error="회사명을 입력하세요." />)
    // then: alert 문구가 보이고 칸이 invalid다
    expect(screen.getByRole('alert')).toHaveTextContent('회사명을 입력하세요.')
    expect(screen.getByRole('combobox', { name: '회사명' })).toBeInvalid()
  })

  // 테스트 코드: UI-037
  it('hint는 칸 아래 안내 문구로 보이고 오류 표시는 없다', () => {
    // given: hint를 받은 콤보박스
    // when: 그린다
    render(<ComboBox label="회사명" name="c" value="" onChange={() => {}} options={OPTIONS} hint="목록에 없어도 직접 입력할 수 있습니다." />)
    // then: 안내 문구가 보이고 alert와 invalid는 없다
    expect(screen.getByText('목록에 없어도 직접 입력할 수 있습니다.')).toBeVisible()
    expect(screen.queryByRole('alert')).not.toBeInTheDocument()
    expect(screen.getByRole('combobox', { name: '회사명' })).toBeValid()
  })

  // 테스트 코드: UI-037
  it('보이는 라벨을 따로 두어도 접근 이름은 전체 라벨이다', async () => {
    // given: label "고객 회사명", visibleLabel "회사"인 콤보박스
    render(<ComboBox label="고객 회사명" visibleLabel="회사" name="c" value="" onChange={() => {}} options={OPTIONS} />)
    const input = screen.getByRole('combobox', { name: '고객 회사명' })
    // then: 보이는 라벨은 "회사"다
    expect(Array.from((input as HTMLInputElement).labels ?? []).map((l) => l.textContent)).toEqual(['회사'])
    // when: 칸을 누른다
    await userEvent.click(input)
    // then: 목록 이름도 "고객 회사명"이다
    expect(screen.getByRole('listbox', { name: '고객 회사명' })).toBeInTheDocument()
  })

  // 테스트 코드: UI-037
  it('보이는 라벨이 없으면 라벨 글자를 보이고 aria-label을 두지 않는다', () => {
    // given: visibleLabel 없는 콤보박스
    // when: 그린다
    render(<ComboBox label="회사명" name="c" value="" onChange={() => {}} options={OPTIONS} />)
    // then: 라벨 "회사명"이 보이고 aria-label은 없다
    const input = screen.getByRole('combobox', { name: '회사명' })
    expect(Array.from((input as HTMLInputElement).labels ?? []).map((l) => l.textContent)).toEqual(['회사명'])
    expect(input).not.toHaveAttribute('aria-label')
  })

  // 테스트 코드: UI-037
  it('inputRef로 입력 칸에 포커스를 옮길 수 있다', () => {
    // given: inputRef를 넘긴 콤보박스
    const ref = createRef<HTMLInputElement>()
    render(<ComboBox label="회사명" name="c" value="" onChange={() => {}} options={OPTIONS} inputRef={ref} />)
    // when: ref로 포커스를 준다
    ref.current?.focus()
    // then: ref가 입력 칸이고 포커스를 받는다
    expect(ref.current).toBe(screen.getByRole('combobox', { name: '회사명' }))
    expect(screen.getByRole('combobox', { name: '회사명' })).toHaveFocus()
  })
})

describe('ComboBox openOnFocus', () => {
  const box = () => screen.getByRole('combobox', { name: '회사명' })

  // 테스트 코드: UI-032
  it('기본값에서는 포커스만으로 목록이 열린다', async () => {
    // given: openOnFocus 기본값인 콤보박스
    render(<Host />)
    // when: Tab으로 포커스만 준다
    await userEvent.tab()
    // then: 칸이 포커스를 받고 목록이 열린다
    expect(box()).toHaveFocus()
    expect(screen.getByRole('listbox')).toBeInTheDocument()
  })

  // 테스트 코드: UI-032
  it('openOnFocus가 참이면 포커스만으로 목록이 열린다', async () => {
    // given: openOnFocus가 참인 콤보박스
    render(<Host openOnFocus />)
    // when: Tab으로 포커스만 준다
    await userEvent.tab()
    // then: 목록이 열린다
    expect(screen.getByRole('listbox')).toBeInTheDocument()
  })

  // 테스트 코드: UI-033
  it('openOnFocus가 거짓이면 포커스만으로는 목록이 열리지 않는다', async () => {
    // given: openOnFocus가 거짓인 콤보박스
    render(<Host openOnFocus={false} />)
    // when: Tab으로 포커스만 준다
    await userEvent.tab()
    // then: 칸은 포커스를 받지만 목록은 없다
    expect(box()).toHaveFocus()
    expect(screen.queryByRole('listbox')).not.toBeInTheDocument()
  })

  // 테스트 코드: UI-033
  it('openOnFocus가 거짓이어도 클릭·↓·입력으로 목록이 열린다', async () => {
    // given: openOnFocus가 거짓이고 포커스만 가진 콤보박스
    render(<Host openOnFocus={false} />)
    await userEvent.tab()
    // when: 칸을 누른다
    await userEvent.click(box())
    // then: 목록이 열린다
    expect(screen.getByRole('listbox')).toBeInTheDocument()
    // when: Esc로 닫는다
    await userEvent.keyboard('{Escape}')
    // then: 목록이 없다
    expect(screen.queryByRole('listbox')).not.toBeInTheDocument()
    // when: ↓를 누른다
    await userEvent.keyboard('{ArrowDown}')
    // then: 목록이 열린다
    expect(screen.getByRole('listbox')).toBeInTheDocument()
    // when: 닫고 글자를 친다
    await userEvent.keyboard('{Escape}')
    await userEvent.type(box(), '하')
    // then: 목록이 열린다
    expect(screen.getByRole('listbox')).toBeInTheDocument()
  })

  // 테스트 코드: UI-032
  it('포커스가 있는 칸을 다시 누르면 닫힌 목록이 다시 열린다', async () => {
    // given: 목록을 열었다가 Esc로 닫은 콤보박스
    render(<Host />)
    await userEvent.click(box())
    await userEvent.keyboard('{Escape}')
    expect(screen.queryByRole('listbox')).not.toBeInTheDocument()
    // when: 포커스가 있는 칸을 다시 누른다
    await userEvent.click(box())
    // then: 목록이 다시 열린다
    expect(screen.getByRole('listbox')).toBeInTheDocument()
  })
})
