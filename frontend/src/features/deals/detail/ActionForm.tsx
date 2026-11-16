import { useId, useRef, useState, type FormEvent } from 'react'
import { useToday } from '../../../data/today'
import { useCodeSet } from '../../../data/codes'
import { useCreateAction } from '../../../data/actions'
import { useMe } from '../../../data/auth'
import { useActionTypes } from '../../../data/actionTypes'
import { toChoice } from '../../../shared/model/catalogChoice'
import { ACTION_TYPE_NAME_MAX_LENGTH } from '../../../shared/model/constants'
import { dateValueError } from '../../../shared/model/dateText'
import { canEditAction } from '../../../shared/model/permissions'
import type { DealAction, DealDetail } from '../../../shared/model/types'
import { DateInput } from '../../../shared/ui/DateInput'
import { ErrorBanner } from '../../../shared/ui/ErrorBanner'
import { Modal } from '../../../shared/ui/Modal'
import { useWonExitConfirm } from '../useWonExitConfirm'
import { PreviousUpdate } from './PreviousUpdate'
import { ActionTypeInput } from './ActionTypeInput'
import { ActionSyncFields } from './ActionSyncFields'
import { messageOf } from './detailHelpers'
import { changeSummary, toStatusChanges } from './syncDraft'
import { useActionSync } from './useActionSync'
import './detail.css'

interface ActionFormProps {
  deal: DealDetail
  /** Next Action이 있는 가장 최근 Action(이전 Update 참조 카드). */
  previous: DealAction | null
  onDone: (message: string) => void
  onCancel: () => void
}

interface Errors {
  actedOn?: string
  type?: string
  progress?: string
  dueDate?: string
}

function FieldError({ message }: { message: string | undefined }) {
  if (!message) return null
  return (
    <p role="alert" className="field-error">
      {message}
    </p>
  )
}

/** Action 추가 팝업(Modal 안의 폼). Status 변경 시 동기화 팝업이 겹쳐 열린다. 수정은 Action 상세 팝업의 칸별 인라인 수정이 맡는다.
 * 저장 중에는 취소·Esc로 닫히지 않는다. 닫으면 입력은 버려진다. */
export function ActionForm({ deal, previous, onDone, onCancel }: ActionFormProps) {
  const codes = useCodeSet().data
  const me = useMe().data
  const create = useCreateAction()
  const today = useToday().today
  const sync = useActionSync(deal)
  const wonExit = useWonExitConfirm()
  const formId = useId()
  const types = useActionTypes().data
  const [type, setType] = useState('')
  const [progress, setProgress] = useState('')
  const [nextAction, setNextAction] = useState('')
  const [dueDate, setDueDate] = useState('')
  // 채우기 버튼을 누르면 켜진 채 나타난다(닫을 수 있을 때만). 끄면 요청에 id를 보내지 않는다.
  const [filledFromId, setFilledFromId] = useState<number | null>(null)
  const [closePrevious, setClosePrevious] = useState(false)
  const [actedOn, setActedOn] = useState(today)
  const [memo, setMemo] = useState('')
  const [errors, setErrors] = useState<Errors>({})
  const [error, setError] = useState<unknown>(null)
  const actedOnRef = useRef<HTMLInputElement>(null)
  const typeRef = useRef<HTMLInputElement>(null)
  const progressRef = useRef<HTMLTextAreaElement>(null)
  const dueRef = useRef<HTMLInputElement>(null)
  const busy = create.isPending
  const title = 'Action 추가'
  const previousOpen = previous?.nextActionStatus === 'open'
  const previousClosable = previousOpen && me !== undefined && previous !== null && canEditAction({ id: me.id, role: me.role }, previous.actor.id)

  // 채운 뒤 이전 Update 카드가 다른 행으로 바뀌면 채움·체크는 무효다(입력한 진행사항은 그대로 둔다).
  const cardChanged = filledFromId !== null && previous?.id !== filledFromId
  const filled = filledFromId !== null && !cardChanged

  function fillFromPrevious(text: string) {
    setProgress(text)
    // 처음(또는 카드가 바뀐 뒤 다시) 누를 때만 체크를 켠다. 같은 행을 다시 눌러도 사용자가 끈 체크는 유지한다.
    if (!filled) setClosePrevious(previousClosable)
    setFilledFromId(previous?.id ?? null)
  }

  const actor = me?.name ?? ''

  const closing = filledFromId !== null && filled && previousClosable && closePrevious

  /** 수행일 화면 검증(AC-R41): 위에서부터 첫 위반만. */
  function actedOnError(): string | undefined {
    if (actedOn === '') return '수행일을 입력하세요.'
    const invalid = dateValueError(actedOn)
    if (invalid !== null) return invalid
    if (actedOn > today) return '수행일은 오늘 이후로 지정할 수 없습니다.'
    const registered = deal.createdAt.slice(0, 10)
    if (actedOn < registered) return `수행일은 Deal 등록일(${registered}) 이전으로 지정할 수 없습니다.`
    if (closing && previous && actedOn < previous.actedOn) {
      return `이전 Next Action의 수행일(${previous.actedOn})보다 앞선 날짜로는 이전 Next Action을 종료할 수 없습니다.`
    }
    return undefined
  }

  function validate(): Errors {
    const found: Errors = {}
    found.actedOn = actedOnError()
    const typeName = type.trim()
    if (typeName === '') found.type = '유형을 입력하세요.'
    else if ([...typeName].length > ACTION_TYPE_NAME_MAX_LENGTH) found.type = `유형은 ${ACTION_TYPE_NAME_MAX_LENGTH}자 이내로 입력하세요.`
    // 서버와 같은 규칙: 진행사항·Next Action은 각각 선택(둘 다 비면 거절), Due Date는 Next Action이 있을 때만 필수.
    const hasNext = nextAction.trim() !== ''
    if (progress.trim() === '' && !hasNext) found.progress = '진행사항 또는 Next Action을 입력하세요.'
    else if (hasNext && dueDate === '') found.dueDate = 'Due Date를 입력하세요.'
    else if (dateValueError(dueDate) !== null) found.dueDate = dateValueError(dueDate) ?? undefined
    else if (!hasNext && dueDate !== '') found.dueDate = 'Next Action 없이 Due Date를 입력할 수 없습니다.'
    return found
  }

  /** Next Action을 모두 지우면 Due Date도 비운다(Next Action 없이 Due Date는 저장할 수 없다). */
  function changeNextAction(value: string) {
    setNextAction(value)
    if (value.trim() === '') setDueDate('')
  }

  async function submit(event: FormEvent) {
    event.preventDefault()
    setError(null)
    const found = validate()
    setErrors(found)
    if (found.actedOn) return actedOnRef.current?.focus()
    if (found.type) return typeRef.current?.focus()
    if (found.progress) return progressRef.current?.focus()
    if (found.dueDate) return dueRef.current?.focus()
    const choice = toChoice(type, types ?? [])
    if (!choice) return typeRef.current?.focus()
    const fields = { type: choice, progress: progress.trim(), nextAction: nextAction.trim(), dueDate, memo }
    try {
      const statusChanges = toStatusChanges(sync.entries)
      // 상태 변경이 Won을 벗어나면 라이선스 계약 처리를 묻는다(동기화 선택 뒤, 등록 요청 전). 취소하면 폼을 그대로 둔다.
      const exit = await wonExit.ask(sync.base, sync.state, deal)
      if (!exit.proceed) return
      const input = {
        ...fields,
        ...(statusChanges.length > 0 ? { statusChanges } : {}),
        ...(closing ? { closePreviousNextActionId: filledFromId } : {}),
        ...(exit.deleteLicenseContracts === undefined ? {} : { deleteLicenseContracts: exit.deleteLicenseContracts }),
        ...(actedOn === today ? {} : { actedOn }),
      }
      await create.mutateAsync({ dealCode: deal.code, input })
      const summary = codes ? changeSummary(sync.base, sync.entries, codes) : null
      onDone(['Action이 등록되었습니다.', closing ? '이전 Next Action을 종료(수행)로 바꿨습니다.' : null, summary].filter(Boolean).join(' '))
    } catch (caught) {
      setError(caught)
    }
  }

  const typeInput = <ActionTypeInput value={type} onChange={setType} error={errors.type} inputRef={typeRef} />

  return (
    <Modal title={title} wide onClose={busy ? () => undefined : onCancel}>
      <div className="dd-action-popup">
        {previous && (
          <PreviousUpdate
            previous={previous}
            filled={filled}
            open={previousOpen}
            closable={previousClosable}
            closeChecked={closePrevious}
            onFill={fillFromPrevious}
            onCloseChange={setClosePrevious}
          />
        )}
        {cardChanged && (
          <p role="alert" className="hint">
            이전 Update가 바뀌었습니다. 확인 후 다시 채우세요.
          </p>
        )}
        <form aria-label={title} className="dd-form" onSubmit={(e) => void submit(e)} noValidate>
          <p className="hint">
            담당자: {actor}
          </p>
          <div className="field">
            <label htmlFor={`${formId}-acted`}>수행일</label>
            <DateInput id={`${formId}-acted`} aria-label="수행일" inputRef={actedOnRef} value={actedOn} onChange={setActedOn} error={errors.actedOn} />
          </div>
          <ActionSyncFields sync={sync}>{typeInput}</ActionSyncFields>
          <label className="field">
            <span>진행사항</span>
            <textarea ref={progressRef} data-autofocus="" value={progress} onChange={(e) => setProgress(e.target.value)} aria-invalid={errors.progress ? true : undefined} />
          </label>
          <FieldError message={errors.progress} />
          <label className="field">
            <span>Next Action</span>
            <input value={nextAction} onChange={(e) => changeNextAction(e.target.value)} />
          </label>
          <div className="field">
            <label htmlFor={`${formId}-due`}>Due Date</label>
            <DateInput id={`${formId}-due`} aria-label="Due Date" inputRef={dueRef} value={dueDate} onChange={setDueDate} error={errors.dueDate} />
          </div>
          <label className="field">
            <span>Memo</span>
            <textarea value={memo} onChange={(e) => setMemo(e.target.value)} />
          </label>
          <ErrorBanner error={error ?? sync.error} format={messageOf} />
          <div className="dd-form-actions">
            <button type="submit" className="primary" disabled={busy}>
              등록
            </button>
            <button type="button" disabled={busy} onClick={onCancel}>
              취소
            </button>
          </div>
        </form>
      </div>
      {sync.dialogs}
      {wonExit.dialog}
    </Modal>
  )
}
