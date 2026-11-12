import { render, screen, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { describe, expect, it, vi } from 'vitest'
import { MultiCheckSelect } from './MultiCheckSelect'

/** 체크박스 드롭다운(Forecast 다중 조건): 접근 이름, 열기·닫기, 포커스, 콜백. */

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
  // 테스트 코드: UI-038
  it('라벨과 요약을 이름으로 가진 버튼이 처음엔 닫혀 있다', () => {
    // given: 요약 "2개 선택"을 받은 다중 선택
    // when: 그린다 (전제: 호출자가 요약 글자를 정함)
    setup({ summary: '2개 선택' })
    // then: 버튼 이름은 "Forecast 2개 선택"이고 닫혀 있다
    expect(screen.getByRole('button', { name: 'Forecast 2개 선택' })).toHaveAttribute('aria-expanded', 'false')
    expect(screen.queryByRole('group', { name: 'Forecast' })).not.toBeInTheDocument()
  })

  // 테스트 코드: UI-038
  it('라벨 글자로 버튼을 찾을 수 있다', () => {
    // when: 다중 선택을 그린다
    setup()
    // then: 라벨 "Forecast"로 찾은 요소가 버튼이다
    expect(screen.getByLabelText('Forecast')).toBe(button())
  })

  // 테스트 코드: UI-038
  it('열면 후보 순서의 체크박스와 지우기 버튼이 있는 그룹이 보인다', async () => {
    // given: 닫힌 다중 선택
    const { user } = setup()
    // when: 버튼을 누른다
    await user.click(button())
    // then: 그룹 안에 후보 순서의 체크박스와 "전체" 버튼이 있다
    expect(button()).toHaveAttribute('aria-expanded', 'true')
    const panel = within(screen.getByRole('group', { name: 'Forecast' }))
    expect(panel.getAllByRole('checkbox').map((c) => c.getAttribute('value'))).toEqual(['pipeline', 'best', 'commit'])
    expect(panel.getAllByRole('checkbox').map((c) => (c as HTMLInputElement).name)).toEqual(['forecast', 'forecast', 'forecast'])
    expect(panel.getByRole('checkbox', { name: 'Pipeline' })).toBeInTheDocument()
    expect(panel.getByRole('button', { name: '전체' })).toBeInTheDocument()
  })

  // 테스트 코드: UI-038
  it('선택된 후보만 체크되어 있다', async () => {
    // given: best가 선택된 다중 선택
    const { user } = setup({ selected: ['best'] })
    // when: 연다
    await user.click(button())
    // then: Best만 체크되어 있다
    expect(screen.getByRole('checkbox', { name: 'Best' })).toBeChecked()
    expect(screen.getByRole('checkbox', { name: 'Pipeline' })).not.toBeChecked()
    expect(screen.getByRole('checkbox', { name: 'Commit' })).not.toBeChecked()
  })

  // 테스트 코드: UI-039
  it('체크하지 않은 상자를 누르면 onToggle(값, true)를 알린다', async () => {
    // given: 연 다중 선택(선택 없음)
    const { user, onToggle } = setup()
    await user.click(button())
    // when: Best를 체크한다
    await user.click(screen.getByRole('checkbox', { name: 'Best' }))
    // then: onToggle('best', true)가 한 번 불린다
    expect(onToggle).toHaveBeenCalledWith('best', true)
    expect(onToggle).toHaveBeenCalledTimes(1)
  })

  // 테스트 코드: UI-039
  it('체크한 상자를 누르면 onToggle(값, false)를 알린다', async () => {
    // given: best가 선택된 연 다중 선택
    const { user, onToggle } = setup({ selected: ['best'] })
    await user.click(button())
    // when: Best를 해제한다
    await user.click(screen.getByRole('checkbox', { name: 'Best' }))
    // then: onToggle('best', false)가 불린다
    expect(onToggle).toHaveBeenCalledWith('best', false)
  })

  // 테스트 코드: UI-039
  it('체크해도 패널은 열린 채다', async () => {
    // given: 연 다중 선택
    const { user } = setup()
    await user.click(button())
    // when: Best를 체크한다
    await user.click(screen.getByRole('checkbox', { name: 'Best' }))
    // then: 패널이 남아 있다
    expect(screen.getByRole('group', { name: 'Forecast' })).toBeInTheDocument()
  })

  // 테스트 코드: UI-039
  it('"전체" 버튼은 onClear만 부른다', async () => {
    // given: best가 선택된 연 다중 선택
    const { user, onClear, onToggle } = setup({ selected: ['best'] })
    await user.click(button())
    // when: "전체"를 누른다
    await user.click(within(screen.getByRole('group', { name: 'Forecast' })).getByRole('button', { name: '전체' }))
    // then: onClear가 한 번이고 onToggle은 없다
    expect(onClear).toHaveBeenCalledTimes(1)
    expect(onToggle).not.toHaveBeenCalled()
  })

  // 테스트 코드: UI-039
  it('clearLabel로 지우기 버튼 글자를 바꿀 수 있다', async () => {
    // given: clearLabel "선택 해제"를 받은 다중 선택
    const { user } = setup({ clearLabel: '선택 해제' })
    // when: 연다
    await user.click(button())
    // then: 지우기 버튼 글자가 "선택 해제"이고 "전체" 버튼은 없다
    const panel = within(screen.getByRole('group', { name: 'Forecast' }))
    expect(panel.getByRole('button', { name: '선택 해제' })).toBeInTheDocument()
    expect(panel.queryByRole('button', { name: '전체' })).not.toBeInTheDocument()
  })

  // 테스트 코드: UI-038
  it('후보가 아직 없으면 체크박스가 없다', async () => {
    // given: 후보가 빈 다중 선택
    const { user } = setup({ options: [] })
    // when: 연다
    await user.click(button())
    // then: 체크박스가 없다
    expect(screen.queryAllByRole('checkbox')).toHaveLength(0)
  })

  // 테스트 코드: UI-040
  it('Esc를 누르면 닫히고 포커스가 버튼으로 돌아온다', async () => {
    // given: Best를 체크한 연 다중 선택
    const { user } = setup()
    await user.click(button())
    await user.click(screen.getByRole('checkbox', { name: 'Best' }))
    // when: Esc를 누른다
    await user.keyboard('{Escape}')
    // then: 닫히고 포커스는 버튼이다
    expect(screen.queryByRole('group', { name: 'Forecast' })).not.toBeInTheDocument()
    expect(button()).toHaveAttribute('aria-expanded', 'false')
    expect(button()).toHaveFocus()
  })

  // 테스트 코드: UI-040
  it('바깥을 누르면 닫힌다', async () => {
    // given: 연 다중 선택
    const { user } = setup()
    await user.click(button())
    // when: 바깥 버튼을 누른다
    await user.click(screen.getByRole('button', { name: '바깥' }))
    // then: 닫힌다
    expect(screen.queryByRole('group', { name: 'Forecast' })).not.toBeInTheDocument()
  })

  // 테스트 코드: UI-040
  it('패널 안을 누르면 닫히지 않는다', async () => {
    // given: 연 다중 선택
    const { user } = setup()
    await user.click(button())
    // when: 패널 안 글자를 누른다
    await user.click(within(screen.getByRole('group', { name: 'Forecast' })).getByText('Pipeline'))
    // then: 열린 채다
    expect(screen.getByRole('group', { name: 'Forecast' })).toBeInTheDocument()
  })

  // 테스트 코드: UI-040
  it('열린 채 버튼을 다시 누르면 닫힌다', async () => {
    // given: 연 다중 선택
    const { user } = setup()
    await user.click(button())
    // when: 버튼을 다시 누른다
    await user.click(button())
    // then: 닫힌다
    expect(screen.queryByRole('group', { name: 'Forecast' })).not.toBeInTheDocument()
  })

  // 테스트 코드: UI-040
  it('포커스가 컴포넌트 밖으로 나가면 닫히고 포커스는 간 곳에 남는다', async () => {
    // given: 뒤에 "다음 입력란" 버튼이 있는 연 다중 선택, 포커스는 "전체" 버튼
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
    // when: Tab을 누른다
    await user.tab()
    // then: 닫히고 포커스는 "다음 입력란"이다
    expect(screen.queryByRole('group', { name: 'Forecast' })).not.toBeInTheDocument()
    expect(screen.getByRole('button', { name: '다음 입력란' })).toHaveFocus()
  })

  // 테스트 코드: UI-040
  it('체크박스 사이로 포커스가 옮겨가도 닫히지 않는다', async () => {
    // given: Pipeline 체크박스에 포커스가 있는 연 다중 선택
    const { user } = setup()
    await user.click(button())
    screen.getByRole('checkbox', { name: 'Pipeline' }).focus()
    // when: Tab을 누른다
    await user.tab()
    // then: 포커스는 Best이고 열린 채다
    expect(screen.getByRole('checkbox', { name: 'Best' })).toHaveFocus()
    expect(screen.getByRole('group', { name: 'Forecast' })).toBeInTheDocument()
  })

  // 테스트 코드: UI-041
  it('aria-haspopup은 없고 aria-expanded가 열림을 따른다', async () => {
    // given: 닫힌 다중 선택
    const { user } = setup()
    // then: 닫힌 상태는 haspopup 없이 expanded가 false다
    expect(button()).not.toHaveAttribute('aria-haspopup')
    expect(button()).toHaveAttribute('aria-expanded', 'false')
    // when: 연다
    await user.click(button())
    // then: haspopup 없이 expanded가 true다
    expect(button()).not.toHaveAttribute('aria-haspopup')
    expect(button()).toHaveAttribute('aria-expanded', 'true')
  })

  // 테스트 코드: UI-041
  it('aria-controls는 열린 동안만 있고 실제 패널을 가리킨다', async () => {
    // given: 닫힌 다중 선택
    const { user } = setup()
    // then: 닫혀 있으면 aria-controls가 없다
    expect(button()).not.toHaveAttribute('aria-controls')
    // when: 연다
    await user.click(button())
    // then: aria-controls가 실제 패널의 id다
    const id = button().getAttribute('aria-controls')
    expect(id).toBeTruthy()
    expect(document.getElementById(id ?? '')).toBe(screen.getByRole('group', { name: 'Forecast' }))
    // when: 다시 닫는다
    await user.click(button())
    // then: aria-controls가 사라진다
    expect(button()).not.toHaveAttribute('aria-controls')
  })
})

describe('MultiCheckSelect hint', () => {
  // 테스트 코드: UI-041
  it('안내 문구를 버튼의 aria-describedby가 가리킨다', () => {
    // when: 안내 문구를 받은 다중 선택을 그린다
    setup({ hint: '연도가 전체이면 올해(2026) 기준입니다.' })
    // then: 버튼이 안내 문구 요소를 가리키고 안내가 보인다
    const target = button().getAttribute('aria-describedby')
    expect(target).toBeTruthy()
    expect(document.getElementById(target ?? '')).toHaveTextContent('연도가 전체이면 올해(2026) 기준입니다.')
    expect(screen.getByText('연도가 전체이면 올해(2026) 기준입니다.')).toBeVisible()
  })

  // 테스트 코드: UI-041
  it('안내가 없으면 aria-describedby도 없다', () => {
    // when: 안내 없이 그린다
    setup()
    // then: aria-describedby가 없다
    expect(button()).not.toHaveAttribute('aria-describedby')
  })

  // 테스트 코드: UI-041
  it('안내는 닫혀 있을 때도 열려 있을 때도 보인다', async () => {
    // given: 안내 문구를 받은 다중 선택
    const { user } = setup({ hint: '안내 문구' })
    // then: 닫힌 상태에서 보인다
    expect(screen.getByText('안내 문구')).toBeVisible()
    // when: 연다
    await user.click(button())
    // then: 열린 상태에서도 보인다
    expect(screen.getByText('안내 문구')).toBeVisible()
  })
})
