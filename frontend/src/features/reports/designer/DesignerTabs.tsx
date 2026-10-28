import { useId, type KeyboardEvent, type ReactNode } from 'react'

export type DesignerTab = 'design' | 'result'

const TABS: { key: DesignerTab; label: string }[] = [
  { key: 'design', label: '작성' },
  { key: 'result', label: '결과' },
]

interface DesignerTabsProps {
  tab: DesignerTab
  onTab: (tab: DesignerTab) => void
  /** 탭마다 그 탭에 보일 위반 수(0이면 이름만). */
  issueCounts: Record<DesignerTab, number>
  panels: Record<DesignerTab, ReactNode>
}

/**
 * 디자이너의 작성/결과 탭. 비활성 탭의 패널도 DOM에 남기고 `hidden`으로 숨긴다
 * (표 페이지·합계 행 선택 같은 화면 상태가 탭을 옮겨도 남는다).
 */
export function DesignerTabs({ tab, onTab, issueCounts, panels }: DesignerTabsProps) {
  const baseId = useId()
  const onKeyDown = (event: KeyboardEvent<HTMLButtonElement>) => {
    if (event.key !== 'ArrowLeft' && event.key !== 'ArrowRight') return
    event.preventDefault()
    const next: DesignerTab = tab === 'design' ? 'result' : 'design'
    onTab(next)
    document.getElementById(`${baseId}-tab-${next}`)?.focus()
  }
  return (
    <>
      <div role="tablist" aria-label="리포트 디자이너" className="report-tabs">
        {TABS.map(({ key, label }) => (
          <button
            key={key}
            type="button"
            role="tab"
            id={`${baseId}-tab-${key}`}
            aria-selected={tab === key}
            aria-controls={`${baseId}-panel-${key}`}
            tabIndex={tab === key ? 0 : -1}
            className={tab === key ? 'is-active' : undefined}
            onClick={() => onTab(key)}
            onKeyDown={onKeyDown}
          >
            {issueCounts[key] > 0 ? `${label} (고칠 곳 ${issueCounts[key]})` : label}
          </button>
        ))}
      </div>
      {TABS.map(({ key }) => (
        <div key={key} role="tabpanel" id={`${baseId}-panel-${key}`} aria-labelledby={`${baseId}-tab-${key}`} hidden={tab !== key}>
          {panels[key]}
        </div>
      ))}
    </>
  )
}
