import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { useState } from 'react'
import { describe, expect, it } from 'vitest'
import { Tabs } from './Tabs'

const TABS = [
  { id: 'actions', label: 'Actions' },
  { id: 'history', label: 'Deal History' },
  { id: 'files', label: 'Files' },
]

function Host() {
  const [active, setActive] = useState('actions')
  return (
    <Tabs label="Deal 하단" tabs={TABS} active={active} onChange={setActive}>
      <p>{active} 내용</p>
    </Tabs>
  )
}

const tab = (name: string) => screen.getByRole('tab', { name })

describe('Tabs', () => {
  // 테스트 코드: UI-053
  it('선택된 탭과 이름 붙은 패널을 가진 tablist를 그린다', () => {
    // when: 첫 탭이 선택된 탭 목록을 그린다
    render(<Host />)
    // then: 선택 상태와 패널 이름이 첫 탭이다
    expect(screen.getByRole('tablist', { name: 'Deal 하단' })).toBeInTheDocument()
    expect(tab('Actions')).toHaveAttribute('aria-selected', 'true')
    expect(tab('Deal History')).toHaveAttribute('aria-selected', 'false')
    expect(screen.getByRole('tabpanel', { name: 'Actions' })).toHaveTextContent('actions 내용')
  })

  // 테스트 코드: UI-053
  it('탭을 누르면 그 탭이 선택되고 패널 내용이 바뀐다', async () => {
    // given: 첫 탭이 선택된 탭 목록
    render(<Host />)
    // when: "Deal History"를 누른다
    await userEvent.click(tab('Deal History'))
    // then: 그 탭이 선택되고 패널이 바뀐다
    expect(tab('Deal History')).toHaveAttribute('aria-selected', 'true')
    expect(screen.getByRole('tabpanel', { name: 'Deal History' })).toHaveTextContent('history 내용')
  })

  // 테스트 코드: UI-053
  it('오른쪽 화살표로 선택과 포커스가 옮겨지고 선택된 탭만 Tab 순서에 든다', async () => {
    // given: Actions에 포커스가 있다
    render(<Host />)
    tab('Actions').focus()
    // when: →를 누른다
    await userEvent.keyboard('{ArrowRight}')
    // then: Deal History가 선택되고 포커스를 받으며 Actions는 tabindex -1이다
    expect(tab('Deal History')).toHaveFocus()
    expect(tab('Deal History')).toHaveAttribute('aria-selected', 'true')
    expect(tab('Actions')).toHaveAttribute('tabindex', '-1')
    expect(tab('Deal History')).toHaveAttribute('tabindex', '0')
  })

  // 테스트 코드: UI-053
  it('End는 마지막, Home은 처음, 처음에서 ←는 마지막, 끝에서 →는 처음으로 간다', async () => {
    // given: 탭 3개이고 Actions에 포커스가 있다
    render(<Host />)
    tab('Actions').focus()
    // when: End를 누른다
    await userEvent.keyboard('{End}')
    // then: 마지막 탭 Files가 선택·포커스된다
    expect(tab('Files')).toHaveFocus()
    expect(tab('Files')).toHaveAttribute('aria-selected', 'true')
    // when: →를 누른다
    await userEvent.keyboard('{ArrowRight}')
    // then: 끝에서 처음 탭으로 돈다
    expect(tab('Actions')).toHaveFocus()
    // when: ←를 누른다
    await userEvent.keyboard('{ArrowLeft}')
    // then: 처음에서 마지막 탭으로 돈다
    expect(tab('Files')).toHaveFocus()
    // when: Home을 누른다
    await userEvent.keyboard('{Home}')
    // then: 처음 탭이 선택·포커스된다
    expect(tab('Actions')).toHaveFocus()
    expect(tab('Actions')).toHaveAttribute('aria-selected', 'true')
  })
})
