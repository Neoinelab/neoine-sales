import { UserSelect } from '../../../shared/ui/UserSelect'
import { FormField } from './FormField'
import type { SectionProps } from './sectionTypes'

/** ① 기본: Deal Name, Owner(재직 sales만), Vendor/Solution(자유 입력), Users. */
export function BasicSection({ state, set, errors, original }: SectionProps) {
  return (
    <section className="form-section" aria-labelledby="sec-basic">
      <h2 id="sec-basic">기본 정보</h2>
      <div className="form-grid">
        <FormField label="Deal Name" name="name" value={state.name} onChange={(v) => set('name', v)} error={errors.name} required />
        <UserSelect
          label="Owner"
          name="owner"
          value={state.ownerId}
          onChange={(v) => set('ownerId', v)}
          current={original?.owner}
          error={errors.ownerId}
        />
        <FormField label="Vendor" name="vendor" value={state.vendor} onChange={(v) => set('vendor', v)} />
        <FormField label="Solution" name="solution" value={state.solution} onChange={(v) => set('solution', v)} />
        <FormField
          label="Users"
          name="users"
          inputMode="numeric"
          value={state.users}
          onChange={(v) => set('users', v)}
          error={errors.users}
          hint="견적 단위 사용자 수(선택)"
        />
      </div>
    </section>
  )
}
