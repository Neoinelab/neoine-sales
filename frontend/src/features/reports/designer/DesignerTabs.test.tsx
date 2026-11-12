import { render, screen, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { useState } from 'react'
import { describe, expect, it } from 'vitest'
import { DesignerTabs, type DesignerTab } from './DesignerTabs'

/** 디자이너 작성/결과 탭은 Deal 상세 탭과 같은 Tabs 마크업 구조(tabs-prominent > tabs-list > tab)를 쓴다. */

function Harness({ counts = { design: 0, result: 0 } }: { counts?: Record<DesignerTab, number> }) {
  const [tab, setTab] = useState<DesignerTab>('design')
  return <DesignerTabs tab={tab} onTab={setTab} issueCounts={counts} panels={{ design: <p>작성 내용</p>, result: <p>결과 내용</p> }} />
}

const tablist = (): HTMLElement => screen.getByRole('tablist', { name: '리포트 디자이너' })

describe('DesignerTabs 마크업', () => {
  it('Deal 상세 탭과 같은 마크업 클래스 구조를 쓴다', () => {
    // when: 탭을 그린다
    render(<Harness />)

    // then: tablist·부모·탭이 Deal 상세 탭과 같은 클래스를 가진다
    expect(tablist()).toHaveClass('tabs-list')
    expect(tablist().parentElement).toHaveClass('tabs-prominent')
    for (const tab of within(tablist()).getAllByRole('tab')) expect(tab).toHaveClass('tab')
  })

  it('예전 report-tabs 스타일 훅은 쓰지 않는다', () => {
    // when: 탭을 그린다
    render(<Harness />)

    // then: report-tabs 클래스가 없다
    expect(tablist()).not.toHaveClass('report-tabs')
    expect(tablist().parentElement).not.toHaveClass('report-tabs')
  })

  it('탭 이름은 작성과 결과 두 라벨뿐이다', () => {
    // when: 탭을 그린다
    render(<Harness />)

    // then: 탭 이름이 작성, 결과다
    expect(within(tablist()).getAllByRole('tab').map((t) => t.textContent)).toEqual(['작성', '결과'])
  })
})

describe('DesignerTabs 동작', () => {
  // 테스트 코드: RQ-068, RS-082
  it('숨은 패널을 DOM에 유지하고 탭과 패널을 aria로 잇는다', () => {
    // when: 탭을 그린다 (전제: 작성 탭 선택)
    render(<Harness />)
    // then: 작성 탭은 선택, 결과 탭은 선택 해제이며 결과 패널은 숨은 채 내용을 유지한다
    const design = screen.getByRole('tab', { name: '작성' })
    const result = screen.getByRole('tab', { name: '결과' })

    expect(design).toHaveAttribute('aria-selected', 'true')
    expect(design).toHaveAttribute('tabindex', '0')
    expect(result).toHaveAttribute('aria-selected', 'false')
    expect(result).toHaveAttribute('tabindex', '-1')
    const resultPanel = document.getElementById(result.getAttribute('aria-controls') ?? '')
    expect(resultPanel).toHaveAttribute('role', 'tabpanel')
    expect(resultPanel).toHaveAttribute('hidden')
    expect(resultPanel).toHaveTextContent('결과 내용')
    expect(document.getElementById(design.getAttribute('aria-controls') ?? '')).not.toHaveAttribute('hidden')
  })

  // 테스트 코드: RQ-090
  it('탭 이름에 고칠 곳 수를 보인다', () => {
    // when: 작성 탭에 고칠 곳 2가 있게 탭을 그린다
    render(<Harness counts={{ design: 2, result: 0 }} />)

    // then: 작성 탭 이름에 수가 붙고 결과 탭은 그대로다
    expect(screen.getByRole('tab', { name: '작성 (고칠 곳 2)' })).toBeInTheDocument()
    expect(screen.getByRole('tab', { name: '결과' })).toBeInTheDocument()
  })

  // 테스트 코드: RQ-068, RS-082
  it('좌우 화살표로 선택과 포커스가 옮겨진다', async () => {
    // given: 작성 탭에 포커스가 있다
    const user = userEvent.setup()
    render(<Harness />)
    screen.getByRole('tab', { name: '작성' }).focus()

    // when: 오른쪽 화살표를 누른다
    await user.keyboard('{ArrowRight}')

    // then: 결과 탭이 선택되고 포커스를 가진다
    expect(screen.getByRole('tab', { name: '결과' })).toHaveAttribute('aria-selected', 'true')
    expect(screen.getByRole('tab', { name: '결과' })).toHaveFocus()

    // when: 왼쪽 화살표를 누른다
    await user.keyboard('{ArrowLeft}')

    // then: 작성 탭이 선택되고 포커스를 가진다
    expect(screen.getByRole('tab', { name: '작성' })).toHaveAttribute('aria-selected', 'true')
    expect(screen.getByRole('tab', { name: '작성' })).toHaveFocus()
  })
})
