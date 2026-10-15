import { ContactPicker } from '../../../shared/contact/ContactPicker'
import { EMPTY_DRAFT, isPartnerEntered, replacedPartner } from './formState'
import type { SectionProps } from './sectionTypes'

/** ②고객(필수) ③파트너(선택). 수정 화면에서 파트너를 바꾸거나 비우면 이력 안내를 보인다. */
export function PartiesSection({ state, set, errors, original }: SectionProps) {
  const active = original?.activePartner ?? null
  const replaced = replacedPartner(original, state.partner)
  const removing = active !== null && !isPartnerEntered(state.partner)
  const activeLabel = active ? `${active.company} ${active.name}` : ''

  return (
    <section className="form-section" aria-labelledby="sec-parties">
      <h2 id="sec-parties">고객 · 파트너</h2>
      <p className="hint">회사명을 고르거나 직접 입력한 뒤 담당자를 고르면 직급·이메일·전화가 채워집니다. 고치면 연락처 정보도 함께 갱신됩니다.</p>
      <ContactPicker
        kind="customer"
        label="고객"
        value={state.customer}
        onChange={(next) => set('customer', next)}
        errors={errors.customer}
        linkedHere={original !== undefined && state.customer.contactId === original.customer.id}
      />
      <div className="partner-block">
        <ContactPicker
          kind="partner"
          label="파트너"
          value={state.partner}
          onChange={(next) => set('partner', next)}
          errors={errors.partner}
          linkedHere={active !== null && state.partner.contactId === active.id}
        />
        {!isPartnerEntered(state.partner) && !removing && <p className="field-hint">파트너가 없으면 비워 두세요. 입력을 시작하면 회사명과 담당자명이 모두 필요합니다.</p>}
        {replaced && (
          <p className="field-hint" role="status">
            기존 활성 파트너({activeLabel})는 이력으로 남고 비활성이 됩니다.
          </p>
        )}
        {removing && (
          <p className="field-hint" role="status">
            저장하면 기존 활성 파트너({activeLabel})가 제거되고 이력으로 남습니다.
          </p>
        )}
        {isPartnerEntered(state.partner) && (
          <button type="button" className="partner-clear" onClick={() => set('partner', EMPTY_DRAFT)}>
            파트너 제거
          </button>
        )}
      </div>
    </section>
  )
}
