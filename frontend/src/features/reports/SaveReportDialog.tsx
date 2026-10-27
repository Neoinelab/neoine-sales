import { useId, useState } from 'react'
import type { SaveFailure } from '../../data/reports'
import type { ReportVisibility, SavedReportMeta } from '../../shared/model/reportTypes'
import { Modal } from '../../shared/ui/Modal'

/** create: 새 리포트 · overwrite: 같은 리포트에 덮어쓰기 · saveAs: 편집 중 다른 이름으로 · copy: 목록·보기에서 복제 */
export type SaveMode = 'create' | 'overwrite' | 'saveAs' | 'copy'

const NAME_MAX = 100
const DESCRIPTION_MAX = 1000
const GUIDE = '저장 내용: 컬럼·조건·정렬·행 수·차트 설정과 생성 SQL. 결과 데이터는 저장하지 않고 열 때마다 다시 조회합니다.'
const VISIBILITY_LOCKED = '공개 범위는 만든 사람 또는 admin만 바꿀 수 있습니다'

const BLANK: SavedReportMeta = { name: '', description: '', visibility: 'public' }

/** 모드별 대화상자 기본값: 덮어쓰기는 현재 메타, 다른 이름·복제는 "<이름> 복사본"(100자로 자름)과 공개. */
function defaultsFor(mode: SaveMode, base: SavedReportMeta | null): SavedReportMeta {
  if (!base || mode === 'create') return BLANK
  if (mode === 'overwrite') return base
  return { name: `${base.name} 복사본`.slice(0, NAME_MAX), description: base.description, visibility: 'public' }
}

interface SaveReportDialogProps {
  mode: SaveMode
  /** 기존 리포트의 메타(create가 아니면 필요). */
  base: SavedReportMeta | null
  /** 덮어쓰기에서 공개 범위를 바꿀 수 있는지(만든 사람·admin). 다른 모드는 항상 바꿀 수 있다. */
  canChangeVisibility: boolean
  busy: boolean
  /** 저장 요청이 실패했을 때 대화상자 안에 보일 내용(정의 위반은 호출처가 대화상자를 닫고 보인다). */
  failure: SaveFailure | null
  onSubmit: (meta: SavedReportMeta) => void
  onCancel: () => void
  /** 저장 충돌 경고의 "다른 이름으로 저장". */
  onSaveAs?: () => void
}

/** 리포트 저장 대화상자. 같은 대화상자가 모드만 바뀔 수 있어(충돌 → 다른 이름으로 저장) 모드가 바뀌면 입력 칸을 새 기본값으로 되돌린다. */
export function SaveReportDialog({ mode, base, canChangeVisibility, busy, failure, onSubmit, onCancel, onSaveAs }: SaveReportDialogProps) {
  const [shownMode, setShownMode] = useState(mode)
  const [meta, setMeta] = useState<SavedReportMeta>(() => defaultsFor(mode, base))
  const [emptyName, setEmptyName] = useState(false)
  const ids = { form: useId(), name: useId(), nameError: useId(), description: useId(), visibility: useId(), locked: useId() }
  if (shownMode !== mode) {
    setShownMode(mode)
    setMeta(defaultsFor(mode, base))
    setEmptyName(false)
  }

  const lockVisibility = mode === 'overwrite' && !canChangeVisibility
  const nameProblem = emptyName ? '이름을 입력하세요' : failure?.kind === 'name' ? failure.message : null
  const conflict = failure?.kind === 'conflict'
  const otherFailure = failure && failure.kind !== 'name' && failure.kind !== 'conflict' && (failure.kind !== 'invalid' || mode === 'copy') ? failure : null

  const submit = () => {
    if (meta.name.trim() === '') {
      setEmptyName(true)
      return
    }
    setEmptyName(false)
    onSubmit(meta)
  }

  return (
    <Modal
      title="리포트 저장"
      onClose={() => {
        // 요청 중에는 닫지 않는다(응답이 닫힌 뒤 도착해 그 사이 편집을 덮어쓰지 않게)
        if (!busy) onCancel()
      }}
      footer={
        conflict ? (
          <button type="button" onClick={onCancel}>
            닫기
          </button>
        ) : (
          <>
            <button type="button" onClick={onCancel} disabled={busy}>
              취소
            </button>
            <button type="submit" form={ids.form} className="primary" disabled={busy}>
              저장
            </button>
          </>
        )
      }
    >
      <form
        id={ids.form}
        noValidate
        className="report-save-form"
        onSubmit={(event) => {
          event.preventDefault()
          submit()
        }}
      >
        <div className="field">
          <label htmlFor={ids.name}>이름</label>
          <input
            id={ids.name}
            type="text"
            required
            maxLength={NAME_MAX}
            value={meta.name}
            aria-invalid={nameProblem ? true : undefined}
            aria-describedby={nameProblem ? ids.nameError : undefined}
            onChange={(e) => {
              setMeta({ ...meta, name: e.target.value })
              setEmptyName(false)
            }}
          />
          {nameProblem && (
            <p id={ids.nameError} className="field-error">
              {nameProblem}
            </p>
          )}
        </div>
        <div className="field">
          <label htmlFor={ids.description}>설명</label>
          <textarea id={ids.description} rows={3} maxLength={DESCRIPTION_MAX} value={meta.description} onChange={(e) => setMeta({ ...meta, description: e.target.value })} />
        </div>
        <div className="field">
          <label htmlFor={ids.visibility}>공개 범위</label>
          <select
            id={ids.visibility}
            value={meta.visibility}
            disabled={lockVisibility}
            aria-describedby={lockVisibility ? ids.locked : undefined}
            onChange={(e) => setMeta({ ...meta, visibility: e.target.value as ReportVisibility })}
          >
            <option value="public">모든 사용자에게 보임</option>
            <option value="private">나만 보기</option>
          </select>
          {lockVisibility && (
            <p id={ids.locked} className="field-hint">
              {VISIBILITY_LOCKED}
            </p>
          )}
        </div>
        <p className="hint">{GUIDE}</p>
      </form>
      {conflict && (
        <div role="alert" className="report-conflict">
          <p>{failure.message}</p>
          {onSaveAs && (
            <button type="button" onClick={onSaveAs}>
              다른 이름으로 저장
            </button>
          )}
        </div>
      )}
      {otherFailure && (
        <p role="alert" className="error">
          {otherFailure.kind === 'invalid' ? `원본 설계가 지금 규칙과 맞지 않아 복제할 수 없습니다. 편집에서 고치세요. ${otherFailure.message}` : otherFailure.message}
        </p>
      )}
    </Modal>
  )
}
