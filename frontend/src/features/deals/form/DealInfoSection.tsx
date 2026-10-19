import { useId } from 'react'
import { UserSelect } from '../../../shared/ui/UserSelect'
import type { SyncApplied } from '../../../shared/model/sync'
import { FormField } from './FormField'
import { VendorRows } from './VendorRows'
import { ProgressRows } from './ProgressRows'
import { QuoteRows } from './QuoteRows'
import type { SectionProps } from './sectionTypes'

interface DealInfoSectionProps extends SectionProps {
  /** 동기화 결과(함께 바뀐 값, 매출 확정값)를 폼에 반영한다. */
  onApplied: (applied: SyncApplied) => void
}

/** 수정 폼의 읽기 전용 Deal code 행. 값은 라벨에 연결한 group이다. */
function CodeRow({ code }: { code: string }) {
  const id = useId()
  return (
    <div className="kv-row field">
      <span id={id}>Deal code</span>
      <span className="kv-static" role="group" aria-labelledby={id}>
        {code}
      </span>
    </div>
  )
}

/** 첫 타일 Deal 정보: 상세와 같은 순서(Deal Name, [Deal code], Owner, Status~Expected Close, Vendor~Users, 견적·POC·구매절차). */
export function DealInfoSection(props: DealInfoSectionProps) {
  const { state, set, errors, original, onApplied } = props
  return (
    <section className="form-section" aria-labelledby="sec-info">
      <h2 id="sec-info">Deal 정보</h2>
      <div className="kv-grid">
        <FormField
          className="kv-wide"
          label="Deal Name"
          name="name"
          value={state.name}
          onChange={(v) => set('name', v)}
          error={errors.name}
          required
        />
        {original && <CodeRow code={original.code} />}
        <div className="kv-row">
          <UserSelect
            label="Owner"
            name="owner"
            value={state.ownerId}
            onChange={(v) => set('ownerId', v)}
            current={original?.owner}
            error={errors.ownerId}
          />
        </div>
        <ProgressRows state={state} set={set} errors={errors} onApplied={onApplied} />
        <VendorRows state={state} set={set} errors={errors} original={original} />
        <FormField
          label="Users"
          name="users"
          inputMode="numeric"
          value={state.users}
          onChange={(v) => set('users', v)}
          error={errors.users}
          hint="견적 단위 사용자 수(선택)"
        />
        <QuoteRows state={state} set={set} errors={errors} />
        <p className="hint">
          통화: <strong>KRW</strong>(고정)
        </p>
      </div>
    </section>
  )
}
