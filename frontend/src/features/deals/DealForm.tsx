import { useState } from 'react'
import { ErrorBanner } from '../../shared/ui/ErrorBanner'
import { SelectField, TextField } from '../../shared/ui/fields'
import { useCustomerOptions } from '../customers/hooks'
import { usePartnerOptions } from '../partners/hooks'
import { useUserChoice } from '../users/options'
import { UserSelect } from '../users/UserSelect'
import { useSaveDeal, type Deal } from './hooks'

interface Props {
  initial?: Deal
  onDone: () => void
}

export function DealForm({ initial, onDone }: Props) {
  const save = useSaveDeal()
  const customers = useCustomerOptions()
  const partners = usePartnerOptions()
  const [form, setForm] = useState({
    code: initial?.code ?? '',
    name: initial?.name ?? '',
    vendor: initial?.vendor ?? '',
    solution: initial?.solution ?? '',
    revenue_amount: initial?.revenue_amount ?? '',
    revenue_currency: initial?.revenue_currency ?? 'KRW',
    revenue_date: initial?.revenue_date ?? '',
    customer_id: initial?.customer_id ?? '',
    partner_id: initial?.partner_id ?? '',
  })
  // 신규는 로그인 사용자를 초기 선택하고, 수정은 기존 담당자를 유지한다.
  const [ownerId, setOwnerId] = useUserChoice(initial?.owner.id)
  const set = (key: keyof typeof form) => (value: string) => setForm((f) => ({ ...f, [key]: value }))

  return (
    <form
      className="panel"
      onSubmit={(e) => {
        e.preventDefault()
        // 금액은 문자열 그대로 보낸다(숫자로 바꾸면 소수 정밀도가 깨질 수 있다).
        save.mutate(
          { id: initial?.id, body: { ...form, owner_user_id: ownerId, partner_id: form.partner_id || null } },
          { onSuccess: onDone },
        )
      }}
    >
      <h2>{initial ? '딜 수정' : '딜 등록'}</h2>
      <ErrorBanner error={save.error ?? customers.error ?? partners.error} />
      <TextField label="Deal Code" name="code" value={form.code} onChange={set('code')} required />
      <TextField label="Deal Name" name="name" value={form.name} onChange={set('name')} required />
      <UserSelect label="Deal Owner" name="owner_user_id" value={ownerId} onChange={setOwnerId} current={initial?.owner} required />
      <TextField label="Vendor" name="vendor" value={form.vendor} onChange={set('vendor')} required />
      <TextField label="Solution" name="solution" value={form.solution} onChange={set('solution')} required />
      <TextField label="매출금액" name="revenue_amount" value={form.revenue_amount} onChange={set('revenue_amount')} required />
      <TextField label="통화" name="revenue_currency" value={form.revenue_currency} onChange={set('revenue_currency')} required />
      <TextField label="매출일" name="revenue_date" type="date" value={form.revenue_date} onChange={set('revenue_date')} required />
      <SelectField label="고객" name="customer_id" value={form.customer_id} onChange={set('customer_id')} required>
        <option value="">선택하세요</option>
        {customers.data?.items.map((c) => (
          <option key={c.id} value={c.id}>
            {c.company_name}
          </option>
        ))}
      </SelectField>
      <SelectField label="파트너(선택)" name="partner_id" value={form.partner_id} onChange={set('partner_id')}>
        <option value="">없음</option>
        {partners.data?.items.map((p) => (
          <option key={p.id} value={p.id}>
            {p.company_name}
          </option>
        ))}
      </SelectField>
      <div className="actions">
        <button type="submit" className="primary" disabled={save.isPending}>
          저장
        </button>
        <button type="button" onClick={onDone}>
          취소
        </button>
      </div>
    </form>
  )
}
