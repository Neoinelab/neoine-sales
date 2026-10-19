import { ContactPicker } from '../../../shared/contact/ContactPicker'
import type { SectionProps } from './sectionTypes'

/** 고객 타일(필수): 회사·담당자·직급·이메일·전화 행. */
export function CustomerSection({ state, set, errors, original }: SectionProps) {
  return (
    <section className="form-section" aria-labelledby="sec-customer">
      <h2 id="sec-customer">고객</h2>
      <p className="hint">회사명을 고르거나 직접 입력한 뒤 담당자를 고르면 직급·이메일·전화가 채워집니다. 고치면 연락처 정보도 함께 갱신됩니다.</p>
      <ContactPicker
        layout="rows"
        kind="customer"
        label="고객"
        value={state.customer}
        onChange={(next) => set('customer', next)}
        errors={errors.customer}
        linkedHere={original !== undefined && state.customer.contactId === original.customer.id}
      />
    </section>
  )
}
