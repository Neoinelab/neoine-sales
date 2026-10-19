import { useRef, useState, type FormEvent } from 'react'
import { useCodeSet } from '../../../data/codes'
import { useCreateAction, useUpdateAction } from '../../../data/actions'
import { useMe } from '../../../data/auth'
import { formatDateTime } from '../../../shared/format'
import { useActionTypes } from '../../../data/actionTypes'
import { toChoice } from '../../../shared/model/catalogChoice'
import { ACTION_TYPE_NAME_MAX_LENGTH } from '../../../shared/model/constants'
import type { SyncApplied } from '../../../shared/model/sync'
import { userLabel } from '../../../shared/model/period'
import type { DealAction, DealDetail } from '../../../shared/model/types'
import { ErrorBanner } from '../../../shared/ui/ErrorBanner'
import { SyncNotice } from '../../../shared/sync/SyncNotice'
import { useSyncedChange } from '../../../shared/sync/useSyncedChange'
import { ActionTypeInput } from './ActionTypeInput'
import { messageOf, toResolution } from './detailHelpers'
import './detail.css'

interface ActionFormProps {
  deal: DealDetail
  /** 수정할 Action. 없으면 등록. */
  editing: DealAction | null
  /** 가장 최근 Action(이전 Update 참조 카드). 등록 모드에서만 쓴다. */
  previous: DealAction | null
  onDone: (message: string) => void
  onCancel: () => void
}

interface Errors {
  type?: string
  progress?: string
  nextAction?: string
  dueDate?: string
}

interface StatusDraft {
  value: string
  applied: SyncApplied
}

function FieldError({ message }: { message: string | undefined }) {
  if (!message) return null
  return (
    <p role="alert" className="field-error">
      {message}
    </p>
  )
}

/** 이전 Update 참조 카드: 가장 최근 Action을 읽기 전용으로 보여 주고 Next Action을 진행사항으로 채울 수 있다. */
function PreviousUpdate({ previous, onFill }: { previous: DealAction; onFill: (text: string) => void }) {
  return (
    <aside aria-label="이전 Update" className="dd-prev">
      <h3>이전 Update</h3>
      <dl className="dd-dl">
        <dt>진행사항</dt>
        <dd>{previous.progress}</dd>
        <dt>Next Action</dt>
        <dd>{previous.nextAction}</dd>
        <dt>Due</dt>
        <dd>{previous.dueDate}</dd>
      </dl>
      <button type="button" className="dd-small" onClick={() => onFill(previous.nextAction)}>
        이전 Next Action을 진행사항에 채우기
      </button>
    </aside>
  )
}

/** Next Action 업데이트 폼(등록·수정). 등록은 Status 변경 시 동기화 팝업, 수정은 Deal History에 기록됨을 안내한다. */
export function ActionForm({ deal, editing, previous, onDone, onCancel }: ActionFormProps) {
  const codes = useCodeSet().data
  const me = useMe().data
  const create = useCreateAction()
  const update = useUpdateAction()
  const { request, dialogs } = useSyncedChange(deal)
  const types = useActionTypes().data
  const [type, setType] = useState(editing?.type ?? '')
  const [progress, setProgress] = useState(editing?.progress ?? '')
  const [nextAction, setNextAction] = useState(editing?.nextAction ?? '')
  const [dueDate, setDueDate] = useState(editing?.dueDate ?? '')
  // 유형 목록이 재조회돼 이름이 바뀌어도, 사용자가 건드리지 않은 유형 입력은 같은 typeId의 현재 이름으로 다시 채운다.
  const [shownType, setShownType] = useState(editing?.type ?? '')
  const currentType = editing ? types?.find((t) => t.id === editing.typeId)?.name : undefined
  if (currentType !== undefined && currentType !== shownType) {
    // 렌더 중 상태 조정: 목록이 바뀐 같은 렌더에서 반영해 옛 이름이 한 번도 화면에 남지 않게 한다.
    setShownType(currentType)
    if (type === shownType) setType(currentType)
  }
  const [memo, setMemo] = useState(editing?.memo ?? '')
  const [status, setStatus] = useState<StatusDraft | null>(null)
  const [errors, setErrors] = useState<Errors>({})
  const [error, setError] = useState<unknown>(null)
  const typeRef = useRef<HTMLInputElement>(null)
  const progressRef = useRef<HTMLTextAreaElement>(null)
  const nextRef = useRef<HTMLInputElement>(null)
  const dueRef = useRef<HTMLInputElement>(null)
  const busy = create.isPending || update.isPending
  const title = editing ? 'Action 수정' : 'Next Action 업데이트'
  const shownStatus = status?.applied.patch.statusKey ?? deal.statusKey
  const actor = editing ? userLabel(editing.actor) : (me?.name ?? '')

  async function changeStatus(value: string) {
    if (value === deal.statusKey) {
      setStatus(null)
      return
    }
    try {
      const applied = await request({ field: 'statusKey', value })
      if (applied !== null) setStatus({ value, applied })
    } catch (caught) {
      setError(caught)
    }
  }

  function validate(): Errors {
    const found: Errors = {}
    const typeName = type.trim()
    if (typeName === '') found.type = '유형을 입력하세요.'
    else if ([...typeName].length > ACTION_TYPE_NAME_MAX_LENGTH) found.type = `유형은 ${ACTION_TYPE_NAME_MAX_LENGTH}자 이내로 입력하세요.`
    if (progress.trim() === '') found.progress = '진행사항을 입력하세요.'
    if (nextAction.trim() === '') found.nextAction = 'Next Action을 입력하세요.'
    if (dueDate === '') found.dueDate = 'Due Date를 입력하세요.'
    return found
  }

  async function submit(event: FormEvent) {
    event.preventDefault()
    setError(null)
    const found = validate()
    setErrors(found)
    if (found.type) return typeRef.current?.focus()
    if (found.progress) return progressRef.current?.focus()
    if (found.nextAction) return nextRef.current?.focus()
    if (found.dueDate) return dueRef.current?.focus()
    // 처음 값 그대로면 이름을 다시 해석하지 않고 원래 {id}를 보낸다(그사이 유형 이름이 바뀌어도 새 유형이 생기지 않는다).
    const choice = editing && (type === editing.type || type === shownType) ? { id: editing.typeId } : toChoice(type, types ?? [])
    if (!choice) return typeRef.current?.focus()
    const fields = { type: choice, progress: progress.trim(), nextAction: nextAction.trim(), dueDate, memo }
    try {
      if (editing) {
        await update.mutateAsync({ dealCode: deal.code, actionId: editing.id, input: fields })
        onDone('Action이 수정되었습니다.')
        return
      }
      const statusChange = status
        ? { change: { field: 'statusKey' as const, value: status.value }, resolution: toResolution(status.applied) }
        : undefined
      await create.mutateAsync({ dealCode: deal.code, input: statusChange ? { ...fields, statusChange } : fields })
      onDone(['Action이 등록되었습니다.', status?.applied.notice].filter(Boolean).join(' '))
    } catch (caught) {
      setError(caught)
    }
  }

  return (
    <>
      <div className={editing ? 'dd-page' : 'dd-action-grid'}>
        <form aria-label={title} className="dd-form" onSubmit={(e) => void submit(e)} noValidate>
          <h3>{title}</h3>
          {editing && <p className="hint">수정한 내용은 Deal History에 기록됩니다. 등록 시점의 Status·Forecast는 바뀌지 않습니다.</p>}
          <p className="hint">
            {editing ? `수행일시: ${formatDateTime(editing.actedAt)}` : '업데이트 일자: 등록 시각으로 자동 기록'} · 담당자: {actor}
          </p>
          {!editing && codes && (
            <label className="field">
              <span>Status</span>
              <select value={shownStatus} onChange={(e) => void changeStatus(e.target.value)}>
                {codes.statuses.map((c) => (
                  <option key={c.key} value={c.key}>
                    {c.name}
                  </option>
                ))}
              </select>
            </label>
          )}
          {status && <SyncNotice notice={status.applied.notice} draft />}
          <ActionTypeInput value={type} onChange={setType} error={errors.type} inputRef={typeRef} />
          <label className="field">
            <span>진행사항</span>
            <textarea ref={progressRef} value={progress} onChange={(e) => setProgress(e.target.value)} aria-invalid={errors.progress ? true : undefined} />
          </label>
          <FieldError message={errors.progress} />
          <label className="field">
            <span>Next Action</span>
            <input ref={nextRef} value={nextAction} onChange={(e) => setNextAction(e.target.value)} aria-invalid={errors.nextAction ? true : undefined} />
          </label>
          <FieldError message={errors.nextAction} />
          <label className="field">
            <span>Due Date</span>
            <input ref={dueRef} type="date" value={dueDate} onChange={(e) => setDueDate(e.target.value)} aria-invalid={errors.dueDate ? true : undefined} />
          </label>
          <FieldError message={errors.dueDate} />
          <label className="field">
            <span>Memo</span>
            <textarea value={memo} onChange={(e) => setMemo(e.target.value)} />
          </label>
          <ErrorBanner error={error} format={messageOf} />
          <div className="dd-form-actions">
            <button type="submit" className="primary" disabled={busy}>
              {editing ? '저장' : '등록'}
            </button>
            <button type="button" onClick={onCancel}>
              취소
            </button>
          </div>
        </form>
        {!editing && previous && <PreviousUpdate previous={previous} onFill={setProgress} />}
      </div>
      {dialogs}
    </>
  )
}
