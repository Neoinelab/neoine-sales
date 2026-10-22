import { useId } from 'react'
import { useVendors } from '../../../data/vendors'
import { ErrorBanner } from '../../../shared/ui/ErrorBanner'
import { SelectField } from '../../../shared/ui/fields'
import { FormField } from './FormField'
import type { SectionProps } from './sectionTypes'

/** 목록을 못 받았을 때 현재 값을 보이는 읽기 전용 라벨-값 행. */
function ReadOnlyRow({ label, value }: { label: string; value: string }) {
  const id = useId()
  return (
    <div className="kv-row field">
      <span id={id}>{label}</span>
      <span className="kv-static" role="group" aria-labelledby={id}>
        {value}
      </span>
    </div>
  )
}

/** Deal 정보 타일의 Vendor·Solution 행. Vendor는 등록된 목록에서만 고르고(만드는 곳은 관리 화면), Solution은 Vendor와 무관한 필수 텍스트다. */
export function VendorRows({ state, set, errors, original }: SectionProps) {
  const query = useVendors()
  const vendors = query.data ?? []

  const solution = (
    <FormField label="Solution" name="solution" value={state.solution} onChange={(v) => set('solution', v)} error={errors.solution} required />
  )

  // 수정 중 목록을 못 받으면 select가 '선택 안 함'으로 보여 저장 시 값이 지워질 수 있다. 읽기 전용으로 현재 값을 보이고 state는 그대로 둔다.
  if (original && !query.data) {
    return (
      <>
        <ReadOnlyRow label="Vendor" value={original.vendor?.name ?? ''} />
        {solution}
        <ErrorBanner error={query.error} />
      </>
    )
  }

  return (
    <>
      <div className="kv-row">
        <SelectField label="Vendor" name="vendor" value={state.vendorId} onChange={(v) => set('vendorId', v)}>
          <option value="">선택 안 함</option>
          {vendors.map((v) => (
            <option key={v.id} value={v.id}>
              {v.name}
            </option>
          ))}
        </SelectField>
      </div>
      {solution}
    </>
  )
}
