import { Link } from 'react-router'

interface DesignerHeadingProps {
  title: string
  unsaved: boolean
  edit: boolean
  canSave: boolean
  saveTitle: string | undefined
  onReset: () => void
  onSaveAs: () => void
  onSave: () => void
}

/** 디자이너 제목 줄: 경로 · 제목 · 저장 안 됨 표시 · 초기화(되돌리기)/다른 이름으로 저장/저장. */
export function DesignerHeading({ title, unsaved, edit, canSave, saveTitle, onReset, onSaveAs, onSave }: DesignerHeadingProps) {
  return (
    <header className="heading report-heading">
      <div>
        <nav aria-label="경로" className="report-crumb">
          <Link to="/reports">Reports</Link>
          <span aria-hidden="true"> ›</span>
        </nav>
        <div className="report-title">
          <h1>{title}</h1>
          {unsaved && (
            <span role="status" className="report-unsaved">
              ● 저장 안 됨
            </span>
          )}
        </div>
      </div>
      <div className="report-heading-actions">
        <button type="button" onClick={onReset}>
          {edit ? '되돌리기' : '초기화'}
        </button>
        {edit && (
          <button type="button" onClick={onSaveAs}>
            다른 이름으로 저장
          </button>
        )}
        <button type="button" className="primary" disabled={!canSave} title={saveTitle} onClick={onSave}>
          저장
        </button>
      </div>
    </header>
  )
}
