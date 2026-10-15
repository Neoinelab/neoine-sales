import { useId, useRef, type KeyboardEvent, type ReactNode } from 'react'
import './ui.css'

export interface TabItem {
  id: string
  label: string
}

interface TabsProps {
  /** tablist의 접근성 이름. */
  label: string
  tabs: readonly TabItem[]
  active: string
  onChange: (id: string) => void
  /** 활성 탭의 패널 내용. */
  children: ReactNode
}

/** 탭 목록 + 활성 패널. 좌우 화살표·Home·End로 이동(선택도 함께 바뀜), 활성 탭만 Tab 순서에 든다. */
export function Tabs({ label, tabs, active, onChange, children }: TabsProps) {
  const baseId = useId()
  const refs = useRef<Record<string, HTMLButtonElement | null>>({})

  function onKeyDown(event: KeyboardEvent<HTMLDivElement>) {
    const index = tabs.findIndex((t) => t.id === active)
    const moves: Record<string, number> = {
      ArrowRight: (index + 1) % tabs.length,
      ArrowLeft: (index - 1 + tabs.length) % tabs.length,
      Home: 0,
      End: tabs.length - 1,
    }
    const next = moves[event.key]
    if (next === undefined) return
    event.preventDefault()
    const target = tabs[next]
    if (!target) return
    onChange(target.id)
    refs.current[target.id]?.focus()
  }

  return (
    <div>
      {/* tablist의 키보드 처리는 각 tab 버튼에서 버블링된 이벤트를 받는다. */}
      {/* eslint-disable-next-line jsx-a11y/interactive-supports-focus */}
      <div role="tablist" aria-label={label} className="tabs-list" onKeyDown={onKeyDown}>
        {tabs.map((tab) => (
          <button
            key={tab.id}
            ref={(el) => {
              refs.current[tab.id] = el
            }}
            type="button"
            role="tab"
            id={`${baseId}-tab-${tab.id}`}
            aria-selected={tab.id === active}
            aria-controls={`${baseId}-panel`}
            tabIndex={tab.id === active ? 0 : -1}
            className="tab"
            onClick={() => onChange(tab.id)}
          >
            {tab.label}
          </button>
        ))}
      </div>
      <div role="tabpanel" id={`${baseId}-panel`} aria-labelledby={`${baseId}-tab-${active}`} className="tabpanel">
        {children}
      </div>
    </div>
  )
}
