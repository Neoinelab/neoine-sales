import { useCodeSet } from '../../../data/codes'
import { formatKrwShort, parseAmount } from '../../../shared/model/money'
import type { SyncApplied } from '../../../shared/model/sync'
import { useSyncedChange } from '../../../shared/sync/useSyncedChange'
import { SelectField } from '../../../shared/ui/fields'
import { FormField } from './FormField'
import type { SectionProps } from './sectionTypes'

interface ProgressRowsProps extends SectionProps {
  /** 동기화 결과(함께 바뀐 값, 매출 확정값)를 폼에 반영한다. 팝업을 취소하면 호출되지 않는다. */
  onApplied: (applied: SyncApplied) => void
}

/** Deal 정보 타일의 Status/Forecast(동기화 팝업)·금액·Expected Close 행. 신규 기본값은 기회발굴/Pipeline. */
export function ProgressRows({ state, set, errors, onApplied }: ProgressRowsProps) {
  const codes = useCodeSet().data
  const amount = parseAmount(state.revenueAmount)
  const { request, dialogs } = useSyncedChange({
    statusKey: state.statusKey,
    forecastKey: state.forecastKey,
    ...(amount !== null ? { revenueAmount: amount } : {}),
    ...(state.revenueDate ? { revenueDate: state.revenueDate } : {}),
  })

  async function change(field: 'statusKey' | 'forecastKey', value: string) {
    const applied = await request({ field, value })
    if (applied) onApplied(applied)
  }

  return (
    <>
      <div className="kv-row">
        <SelectField label="Status" name="status" value={state.statusKey} onChange={(v) => void change('statusKey', v)}>
          {codes?.statuses.map((c) => (
            <option key={c.key} value={c.key}>
              {c.name}
            </option>
          ))}
        </SelectField>
      </div>
      <div className="kv-row">
        <SelectField label="Forecast" name="forecast" value={state.forecastKey} onChange={(v) => void change('forecastKey', v)}>
          {codes?.forecasts.map((c) => (
            <option key={c.key} value={c.key}>
              {c.name}
            </option>
          ))}
        </SelectField>
      </div>
      <FormField
        label="금액"
        name="revenueAmount"
        inputMode="numeric"
        value={state.revenueAmount}
        onChange={(v) => set('revenueAmount', v)}
        error={errors.revenueAmount}
        hint={amount !== null ? `KRW · ${formatKrwShort(amount)}` : 'KRW(원 단위 정수)'}
        required
      />
      <FormField
        label="Expected Close"
        name="revenueDate"
        type="date"
        value={state.revenueDate}
        onChange={(v) => set('revenueDate', v)}
        error={errors.revenueDate}
        hint="Won이면 실제 매출일"
        required
      />
      {dialogs}
    </>
  )
}
