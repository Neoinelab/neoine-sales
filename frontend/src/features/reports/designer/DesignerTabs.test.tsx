import { render, screen, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { useState } from 'react'
import { describe, expect, it } from 'vitest'
import { DesignerTabs, type DesignerTab } from './DesignerTabs'

/** 디자이너 작성/결과 탭은 Deal 상세 탭과 같은 Tabs 마크업 구조(tabs-prominent > tabs-list > tab)를 쓴다. 기존 동작은 유지. */

function Harness({ counts = { design: 0, result: 0 } }: { counts?: Record<DesignerTab, number> }) {
  const [tab, setTab] = useState<DesignerTab>('design')
  return <DesignerTabs tab={tab} onTab={setTab} issueCounts={counts} panels={{ design: <p>작성 내용</p>, result: <p>결과 내용</p> }} />
}

const tablist = (): HTMLElement => screen.getByRole('tablist', { name: '리포트 디자이너' })

describe('DesignerTabs 마크업', () => {
  it('uses the same class structure as the deal detail tabs', () => {
    render(<Harness />)

    expect(tablist()).toHaveClass('tabs-list')
    expect(tablist().parentElement).toHaveClass('tabs-prominent')
    for (const tab of within(tablist()).getAllByRole('tab')) expect(tab).toHaveClass('tab')
  })

  it('no longer uses the old report-tabs styling hooks', () => {
    render(<Harness />)

    expect(tablist()).not.toHaveClass('report-tabs')
    expect(tablist().parentElement).not.toHaveClass('report-tabs')
  })

  it('names the tabs by their labels only', () => {
    render(<Harness />)

    expect(within(tablist()).getAllByRole('tab').map((t) => t.textContent)).toEqual(['작성', '결과'])
  })
})

describe('DesignerTabs 동작', () => {
  it('keeps the inactive panel in the DOM, hidden, and links tabs to panels by aria', () => {
    render(<Harness />)
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

  it('shows the number of places to fix in the tab name', () => {
    render(<Harness counts={{ design: 2, result: 0 }} />)

    expect(screen.getByRole('tab', { name: '작성 (고칠 곳 2)' })).toBeInTheDocument()
    expect(screen.getByRole('tab', { name: '결과' })).toBeInTheDocument()
  })

  it('moves the selection and focus with the left and right arrow keys', async () => {
    const user = userEvent.setup()
    render(<Harness />)
    screen.getByRole('tab', { name: '작성' }).focus()

    await user.keyboard('{ArrowRight}')

    expect(screen.getByRole('tab', { name: '결과' })).toHaveAttribute('aria-selected', 'true')
    expect(screen.getByRole('tab', { name: '결과' })).toHaveFocus()

    await user.keyboard('{ArrowLeft}')

    expect(screen.getByRole('tab', { name: '작성' })).toHaveAttribute('aria-selected', 'true')
    expect(screen.getByRole('tab', { name: '작성' })).toHaveFocus()
  })
})
