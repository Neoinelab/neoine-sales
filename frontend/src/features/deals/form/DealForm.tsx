import { useRef, useState, type FormEvent } from 'react'
import { useNavigate } from 'react-router'
import { useCreateDeal, useUpdateDeal } from '../../../data/deals'
import type { SyncApplied } from '../../../shared/model/sync'
import type { DealDetail } from '../../../shared/model/types'
import { ErrorBanner } from '../../../shared/ui/ErrorBanner'
import { useDealListPath } from '../../../shared/ui/useDealListPath'
import { SyncNotice } from '../../../shared/sync/SyncNotice'
import { BantSection } from './BantSection'
import { CustomerSection } from './CustomerSection'
import { DealInfoSection } from './DealInfoSection'
import {
  emptyForm,
  formFromDeal,
  hasErrors,
  toDealInput,
  toDealPatch,
  validateForm,
  type DealFormState,
  type FormErrors,
} from './formState'
import { PartnerSection } from './PartnerSection'
import type { SetField } from './sectionTypes'

interface DealFormProps {
  /** 수정이면 불러온 Deal, 신규면 undefined. */
  original?: DealDetail
  /** 신규 Deal의 Owner 기본값(접속 사용자가 sales일 때만 그 id, 아니면 빈 값). */
  defaultOwnerId: string
}

/** 등록·수정 공용 폼. 검증 → 저장 → 상세로 이동하고, Status/Forecast 변경은 draft에 반영만 한다(저장 시 일괄). */
export function DealForm({ original, defaultOwnerId }: DealFormProps) {
  const navigate = useNavigate()
  const listPath = useDealListPath()
  const create = useCreateDeal()
  const update = useUpdateDeal()
  const form = useRef<HTMLFormElement>(null)
  const [state, setState] = useState<DealFormState>(() => (original ? formFromDeal(original) : emptyForm(defaultOwnerId)))
  const [errors, setErrors] = useState<FormErrors>({})
  const [syncNotice, setSyncNotice] = useState<string | null>(null)
  const [saveError, setSaveError] = useState<unknown>(null)
  const [saving, setSaving] = useState(false)

  const set: SetField = (key, value) => setState((prev) => ({ ...prev, [key]: value }))

  /** 동기화 결과를 draft에 반영한다. 매출 확정값이 있으면 금액·Expected Close도 함께 바꾼다. */
  function onApplied(applied: SyncApplied) {
    setState((prev) => ({
      ...prev,
      statusKey: applied.patch.statusKey ?? prev.statusKey,
      forecastKey: applied.patch.forecastKey ?? prev.forecastKey,
      revenueAmount: applied.revenue ? String(applied.revenue.amount) : prev.revenueAmount,
      revenueDate: applied.revenue ? applied.revenue.date : prev.revenueDate,
    }))
    setSyncNotice(applied.notice)
  }

  function focusFirstInvalid() {
    // 오류가 화면에 그려진 다음에 문서 순서상 첫 번째 잘못된 입력으로 이동한다.
    window.setTimeout(() => form.current?.querySelector<HTMLElement>('[aria-invalid="true"]')?.focus(), 0)
  }

  async function onSubmit(event: FormEvent) {
    event.preventDefault()
    if (saving) return
    const found = validateForm(state, original?.owner)
    setErrors(found)
    setSaveError(null)
    if (hasErrors(found)) return focusFirstInvalid()
    setSaving(true)
    try {
      if (original) {
        const saved = await update.mutateAsync({ code: original.code, patch: toDealPatch(state, original) })
        navigate(`/deals/${saved.code}`, { state: { notice: '저장되었습니다.' } })
      } else {
        const saved = await create.mutateAsync(toDealInput(state))
        navigate(`/deals/${saved.code}`, { state: { notice: `Deal ${saved.code}이(가) 등록되었습니다.` } })
      }
    } catch (failure) {
      setSaveError(failure)
      setSaving(false)
    }
  }

  const section = { state, set, errors, ...(original ? { original } : {}) }
  return (
    <form ref={form} className="deal-form" noValidate onSubmit={(e) => void onSubmit(e)}>
      {syncNotice && <SyncNotice notice={syncNotice} draft onClose={() => setSyncNotice(null)} />}
      <DealInfoSection {...section} onApplied={onApplied} />
      <CustomerSection {...section} />
      <PartnerSection {...section} />
      <BantSection {...section} />
      <div className="form-actions">
        <ErrorBanner error={saveError} />
        <button type="submit" className="primary" disabled={saving}>
          {saving ? '저장 중…' : '저장'}
        </button>
        <button type="button" disabled={saving} onClick={() => navigate(original ? `/deals/${original.code}` : listPath)}>
          취소
        </button>
      </div>
    </form>
  )
}
