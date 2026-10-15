import { useEffect, useRef, useState, type KeyboardEvent } from 'react'
import { useCodeSet } from '../../../data/codes'
import { useApplyDealChange } from '../../../data/deals'
import { parseAmount } from '../../../shared/model/money'
import type { ApplyChangeRequest, DealChange, DealRow } from '../../../shared/model/types'
import { useSyncedChange } from '../../../shared/sync/useSyncedChange'
import { initialDraft, INLINE_LABEL, savedMessage, type InlineField } from './inline'

interface InlineEditorProps {
  row: DealRow
  field: InlineField
  /** 저장했으면 알림 문구, 취소·변경 없음이면 undefined. */
  onDone: (message?: string) => void
}

const AMOUNT_MESSAGE = '매출금액은 1원 이상의 정수로 입력하세요.'
const DATE_MESSAGE = 'Expected Close를 입력하세요.'

/**
 * 한 셀의 편집 모드. 저장 버튼 없이 바로 반영한다.
 * - Status/Forecast 선택, Expected Close 날짜 선택: 고르는 순간 저장
 * - 금액: Enter 또는 포커스 이동(blur)에 저장, Esc는 입력을 버리고 원래 값으로
 * Status/Forecast는 useSyncedChange를 거쳐 매출 확정·함께 바꿀 값 선택 팝업을 띄운다(팝업 취소 시 변경 없음).
 */
export function InlineEditor({ row, field, onDone }: InlineEditorProps) {
  const codes = useCodeSet().data
  const apply = useApplyDealChange()
  const { request, dialogs } = useSyncedChange(row)
  const [draft, setDraft] = useState(() => initialDraft(row, field))
  const [error, setError] = useState<string | null>(null)
  const label = INLINE_LABEL[field]
  const root = useRef<HTMLDivElement>(null)
  // 저장 중·취소 후에는 팝업으로 포커스가 옮겨 가며 생기는 blur를 무시한다.
  const settled = useRef(false)

  // 편집을 시작하면 입력란으로 포커스를 옮겨 키보드로 바로 고칠 수 있게 한다.
  useEffect(() => {
    root.current?.querySelector<HTMLElement>('select, input')?.focus()
  }, [])

  async function send(value: string, change: DealChange, resolution: ApplyChangeRequest['resolution']) {
    const result = await apply.mutateAsync({ code: row.code, request: resolution ? { change, resolution } : { change } })
    onDone(savedMessage(row, field, value, codes, result))
  }

  async function saveCodeChange(codeField: 'statusKey' | 'forecastKey', value: string) {
    if (value === row[codeField]) return onDone()
    const applied = await request({ field: codeField, value })
    if (applied === null) return onDone()
    const resolution: NonNullable<ApplyChangeRequest['resolution']> = {}
    if (applied.revenue) {
      resolution.revenueAmount = applied.revenue.amount
      resolution.revenueDate = applied.revenue.date
    }
    if (applied.patch.statusKey !== undefined) resolution.statusKey = applied.patch.statusKey
    if (applied.patch.forecastKey !== undefined) resolution.forecastKey = applied.patch.forecastKey
    await send(value, { field: codeField, value }, resolution)
  }

  async function saveValue(value: string) {
    if (field === 'statusKey' || field === 'forecastKey') return saveCodeChange(field, value)
    if (field === 'revenueAmount') {
      const amount = parseAmount(value)
      if (amount === null) return setError(AMOUNT_MESSAGE)
      return amount === row.revenueAmount ? onDone() : send(value, { field, value: amount }, undefined)
    }
    if (value === '') return setError(DATE_MESSAGE)
    return value === row.revenueDate ? onDone() : send(value, { field, value }, undefined)
  }

  async function save(value: string) {
    if (settled.current) return
    setError(null)
    settled.current = true
    try {
      await saveValue(value)
    } catch (failure) {
      setError(failure instanceof Error ? failure.message : '저장하지 못했습니다.')
    } finally {
      // 검증·저장 실패로 편집이 계속되면 다시 시도할 수 있게 푼다(편집이 끝났으면 언마운트됨).
      settled.current = false
    }
  }

  function pick(value: string) {
    setDraft(value)
    void save(value)
  }

  function cancel() {
    settled.current = true
    onDone()
  }

  function onKeyDown(event: KeyboardEvent) {
    if (event.key === 'Escape') {
      event.preventDefault()
      cancel()
    } else if (event.key === 'Enter' && field === 'revenueAmount') {
      event.preventDefault()
      void save(draft)
    }
  }

  function onBlur() {
    if (settled.current) return
    if (field === 'revenueAmount') void save(draft)
    else if (!error) onDone()
  }

  const common = { 'aria-label': `${label} 값`, onKeyDown, onBlur }
  const list = field === 'statusKey' ? codes?.statuses : codes?.forecasts

  return (
    <div className="inline-editor" ref={root}>
      {(field === 'statusKey' || field === 'forecastKey') && (
        <select {...common} value={draft} onChange={(e) => pick(e.target.value)}>
          {list?.map((c) => (
            <option key={c.key} value={c.key}>
              {c.name}
            </option>
          ))}
        </select>
      )}
      {field === 'revenueAmount' && (
        <input {...common} inputMode="numeric" value={draft} onChange={(e) => setDraft(e.target.value)} />
      )}
      {field === 'revenueDate' && <input {...common} type="date" value={draft} onChange={(e) => pick(e.target.value)} />}
      {error && (
        <p role="alert" className="field-error">
          {error}
        </p>
      )}
      {dialogs}
    </div>
  )
}
