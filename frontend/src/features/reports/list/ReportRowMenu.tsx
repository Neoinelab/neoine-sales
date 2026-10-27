import { useEffect, useId, useRef, useState } from 'react'
import { Link } from 'react-router'
import { canDeleteReport, canEditReport, type Viewer } from '../../../shared/model/permissions'
import type { SavedReportSummary } from '../../../shared/model/reportTypes'

interface ReportRowMenuProps {
  report: SavedReportSummary
  viewer: Viewer
  onCopy: () => void
  onDelete: () => void
}

/**
 * 목록 한 행의 ⋯ 메뉴(열기·편집·복제·삭제). 편집·삭제는 권한이 있을 때만 보인다.
 * 단추로 여닫는 목록이며, Escape(포커스를 단추로 되돌림)·바깥 클릭·항목 선택으로 닫힌다.
 */
export function ReportRowMenu({ report, viewer, onCopy, onDelete }: ReportRowMenuProps) {
  const [open, setOpen] = useState(false)
  const rootRef = useRef<HTMLDivElement>(null)
  const buttonRef = useRef<HTMLButtonElement>(null)
  const panelId = useId()

  useEffect(() => {
    if (!open) return
    const outside = (event: PointerEvent) => {
      if (!rootRef.current?.contains(event.target as Node)) setOpen(false)
    }
    const escape = (event: KeyboardEvent) => {
      if (event.key !== 'Escape') return
      setOpen(false)
      buttonRef.current?.focus()
    }
    document.addEventListener('pointerdown', outside)
    document.addEventListener('keydown', escape)
    return () => {
      document.removeEventListener('pointerdown', outside)
      document.removeEventListener('keydown', escape)
    }
  }, [open])

  const choose = (action: () => void) => () => {
    setOpen(false)
    action()
  }

  return (
    <div ref={rootRef} className="report-menu">
      <button
        ref={buttonRef}
        type="button"
        className="report-menu-button"
        aria-label={`${report.name} 메뉴`}
        aria-haspopup="menu"
        aria-expanded={open}
        aria-controls={open ? panelId : undefined}
        onClick={() => setOpen((v) => !v)}
      >
        ⋯
      </button>
      {open && (
        <ul id={panelId} className="report-menu-list">
          <li>
            <Link to={`/reports/${report.id}`} onClick={() => setOpen(false)}>
              열기
            </Link>
          </li>
          {canEditReport(viewer, report) && (
            <li>
              <Link to={`/reports/${report.id}/edit`} onClick={() => setOpen(false)}>
                편집
              </Link>
            </li>
          )}
          <li>
            <button type="button" onClick={choose(onCopy)}>
              복제
            </button>
          </li>
          {canDeleteReport(viewer, report) && (
            <li>
              <button type="button" className="danger-text" onClick={choose(onDelete)}>
                삭제
              </button>
            </li>
          )}
        </ul>
      )}
    </div>
  )
}
