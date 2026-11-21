import { useEffect, useRef, useState, type FocusEvent, type KeyboardEvent, type ReactNode } from 'react'
import { useWhitespaceGuard } from '../../../shared/contact/useWhitespaceGuard'
import { WHITESPACE_MESSAGE } from '../../../shared/model/contactRules'
import { dateTextToValue, dateValueError, finalizeDateText } from '../../../shared/model/dateText'
import type { ComboOption } from '../../../shared/ui/ComboBox'
import { ErrorBanner } from '../../../shared/ui/ErrorBanner'
import { messageOf } from './detailHelpers'
import { InlineControl, type InlineControlContext, type InlineKind } from './InlineControl'

export type { InlineControlContext } from './InlineControl'

interface InlineEditProps {
  /** 필드 이름. 버튼 이름은 "<label> 수정". */
  label: string
  /** 쓰기 권한. false면 값만 그리고 클릭 편집 어포던스를 만들지 않는다. */
  canEdit: boolean
  /** 읽기 모드의 값 표시(클릭하면 편집이 열리는 버튼의 내용). */
  display: ReactNode
  /** 편집을 시작할 때 입력기에 넣을 값. */
  initial: string
  kind?: InlineKind
  /** select·combo의 목록. */
  options?: readonly ComboOption[]
  control?: (context: InlineControlContext) => ReactNode
  /** true면 입력 중 공백을 제거하고 안내한다. */
  noSpace?: boolean
  /** 편집 중 입력기 아래에 보이는 안내. */
  hint?: string
  /** 제목(h1) 안에서 버튼으로 그린다(제목의 접근성 이름을 값으로 유지하려고 이름은 title로 준다). */
  asHeading?: boolean
  /** 입력기 접근성 이름(기본 label). */
  inputLabel?: string
  /** true면 값 버튼이 칸 폭 전체를 쓰고, 여는 순간 값 버튼 높이를 `startHeight`로 입력기에 전한다(여러 줄 칸용). */
  fill?: boolean
  /** true면 저장·취소 버튼으로만 저장한다(Enter·Shift+Enter는 줄바꿈, 포커스 이탈·날짜 Enter·달력 선택은 저장하지 않고 편집 유지). */
  saveButtons?: boolean
  /** 같은 팝업의 다른 칸이 저장 중이다(saveButtons 칸의 "저장"을 끈다. 옛 값으로 앞 수정을 덮어쓰지 않게 한다). */
  otherSaving?: boolean
  /** 저장. 화면 검증 문구는 throw new Error(message)로, 서버 오류는 그대로 reject하면 된다. 성공하면 편집이 닫힌다. */
  onSave: (text: string, option?: ComboOption) => Promise<void>
}

/**
 * 값을 클릭하면 그 자리에서 입력기로 바뀌는 인라인 편집. 값은 button이라 Enter/Space로도 열린다.
 * `saveButtons`가 켜진 칸은 저장·취소 버튼으로만 저장하고(Enter·Shift+Enter는 줄바꿈, 포커스 이동은 저장 아님), 아래 규칙은 켜지지 않은 칸의 동작이다.
 * - 선택형(select, 자동완성 후보 선택)은 고르는 순간 저장한다.
 * - 입력형(텍스트·숫자·날짜, 자동완성 직접 입력)은 Enter 또는 포커스 이동(blur)으로 저장한다(saveButtons 제외). 값이 그대로면 저장 없이 닫는다.
 * - Esc는 입력 중이던 값을 버리고 닫는다.
 * 검증·서버 오류는 입력란 옆에 보이고 편집 상태를 유지한다(다시 고쳐 재시도).
 */
export function InlineEdit(props: InlineEditProps) {
  const { label, canEdit, display, initial, kind = 'text', options = [], control, noSpace = false, hint, asHeading = false, fill = false, saveButtons = false, otherSaving = false, onSave } = props
  const inputLabel = props.inputLabel ?? label
  const [editing, setEditing] = useState(false)
  const [text, setText] = useState(initial)
  const [error, setError] = useState<unknown>(null)
  const [busy, setBusy] = useState(false)
  const [startHeight, setStartHeight] = useState(0)
  const wrapRef = useRef<HTMLDivElement>(null)
  const openerRef = useRef<HTMLButtonElement>(null)
  const returnFocus = useRef(false)
  const skipBlur = useRef(false)
  const { flashed, guard } = useWhitespaceGuard()
  const focusFirst = () => wrapRef.current?.querySelector<HTMLElement>('input, select, textarea')?.focus()

  useEffect(() => {
    if (editing) focusFirst()
    else if (returnFocus.current) {
      returnFocus.current = false
      openerRef.current?.focus()
    }
  }, [editing])

  useEffect(() => {
    if (error) focusFirst()
  }, [error])

  function start() {
    skipBlur.current = false
    setStartHeight(fill ? (openerRef.current?.offsetHeight ?? 0) : 0)
    setText(initial)
    setError(null)
    setEditing(true)
  }

  function close() {
    skipBlur.current = true
    returnFocus.current = true
    setEditing(false)
    setError(null)
  }

  async function commit(override?: string, option?: ComboOption) {
    if (busy || (saveButtons && otherSaving)) return
    // 날짜 칸은 DateInput이 글자를 확정한 값(blur 직전 상태 포함)을 쓰고, 틀린 날짜는 저장하지 않는다(문구는 칸이 보인다).
    const value = override ?? (kind === 'date' ? dateTextToValue(finalizeDateText(text)) : text)
    if (kind === 'date' && dateValueError(value) !== null) return
    if (value === initial) return close()
    setBusy(true)
    setError(null)
    try {
      await onSave(value, option)
      close()
    } catch (caught) {
      setError(caught)
    } finally {
      setBusy(false)
    }
  }

  function onKeyDown(event: KeyboardEvent<HTMLElement>) {
    // 저장 중에는 Esc·Enter를 무시한다(응답 전에 편집이 닫히면 거절 문구와 입력이 사라진다).
    if (event.defaultPrevented || busy) return
    if (event.key === 'Escape') {
      event.stopPropagation()
      close()
    } else if (saveButtons) {
      return
    } else if (event.key === 'Enter' && !(event.target instanceof HTMLElement && (event.target.tagName === 'SELECT' || event.target.closest('.date-input-button')))) {
      event.preventDefault()
      void commit()
    }
  }

  function onBlur(event: FocusEvent<HTMLElement>) {
    if (skipBlur.current || busy || saveButtons) return
    if (event.relatedTarget instanceof Node && event.currentTarget.contains(event.relatedTarget)) return
    if (kind === 'select') close()
    else void commit()
  }

  function onChange(value: string) {
    setText(value)
    if (kind === 'select') void commit(value)
  }

  if (!canEdit) {
    if (asHeading) return <h1>{display}</h1>
    // 값이 없으면 빈 상자(여백·테두리)를 남기지 않는다.
    return display ? <span className="kv-static">{display}</span> : null
  }
  if (!editing) {
    const opener = (
      <button
        ref={openerRef}
        type="button"
        className={fill ? 'dd-click dd-click-fill' : 'dd-click'}
        aria-label={asHeading ? undefined : `${label} 수정`}
        title={asHeading ? `${label} 수정` : undefined}
        onClick={start}
      >
        {display}
      </button>
    )
    return asHeading ? <h1>{opener}</h1> : opener
  }
  return (
    <div className={asHeading ? 'dd-inline-wrap dd-h1-edit' : 'dd-inline-wrap'}>
      {/* 입력기 안의 Enter/Esc/blur를 한 곳에서 처리한다(그룹 자체는 포커스를 받지 않는다). */}
      {/* eslint-disable-next-line jsx-a11y/no-noninteractive-element-interactions */}
      <div role="group" aria-label={`${label} 편집`} className="dd-inline-edit" ref={wrapRef} onKeyDown={onKeyDown} onBlur={onBlur}>
        <InlineControl
          kind={kind}
          name={label}
          inputLabel={inputLabel}
          value={text}
          onChange={onChange}
          busy={busy}
          options={options}
          sanitize={noSpace ? (raw) => guard(label, raw) : undefined}
          onPick={(option) => void commit(option.value, option)}
          commit={saveButtons ? (v) => v !== undefined && setText(v) : (v) => void commit(v)}
          control={control}
          startHeight={startHeight}
        />
        {saveButtons && (
          <div className="dd-inline-buttons">
            <button type="button" className="primary" aria-label={`${label} 저장`} disabled={busy || otherSaving} onClick={() => void commit()}>
              저장
            </button>
            <button type="button" aria-label={`${label} 취소`} disabled={busy} onClick={close}>
              취소
            </button>
          </div>
        )}
      </div>
      {(hint || flashed[label]) && <p className="field-hint">{flashed[label] ? WHITESPACE_MESSAGE : hint}</p>}
      <ErrorBanner error={error} format={messageOf} />
    </div>
  )
}
