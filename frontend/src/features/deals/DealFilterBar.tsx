import { useState } from 'react'
import { nextDay } from '../../shared/format'
import { SelectField, TextField } from '../../shared/ui/fields'
import { useCustomerOptions } from '../customers/hooks'
import { usePartnerOptions } from '../partners/hooks'
import { UserSelect } from '../users/UserSelect'
import type { DealFilters } from './hooks'
import { DEAL_STAGES, STAGE_LABEL, type DealStage } from './stages'

interface Props {
  onSearch: (filters: DealFilters) => void
}

/** 딜 검색 조건 입력. 종료일은 그날을 포함하도록 다음 날(미만 조건)로 보낸다. 값이 있는 조건만 전달한다. */
export function DealFilterBar({ onSearch }: Props) {
  const customers = useCustomerOptions()
  const partners = usePartnerOptions()
  const [keyword, setKeyword] = useState('')
  const [customerId, setCustomerId] = useState('')
  const [partnerId, setPartnerId] = useState('')
  const [ownerId, setOwnerId] = useState('')
  const [vendor, setVendor] = useState('')
  const [stage, setStage] = useState('')
  const [from, setFrom] = useState('')
  const [to, setTo] = useState('')

  return (
    <form
      className="filters"
      role="search"
      onSubmit={(e) => {
        e.preventDefault()
        onSearch({
          keyword: keyword.trim() || undefined,
          customer_id: customerId || undefined,
          partner_id: partnerId || undefined,
          owner_user_id: ownerId || undefined,
          vendor: vendor.trim() || undefined,
          stage: (stage || undefined) as DealStage | undefined,
          revenue_from: from || undefined,
          revenue_to: to ? nextDay(to) : undefined,
        })
      }}
    >
      <TextField label="검색어" name="keyword" value={keyword} onChange={setKeyword} />
      <SelectField label="고객" name="customer_id" value={customerId} onChange={setCustomerId}>
        <option value="">전체</option>
        {customers.data?.items.map((c) => (
          <option key={c.id} value={c.id}>
            {c.company_name}
          </option>
        ))}
      </SelectField>
      <SelectField label="파트너" name="partner_id" value={partnerId} onChange={setPartnerId}>
        <option value="">전체</option>
        {partners.data?.items.map((p) => (
          <option key={p.id} value={p.id}>
            {p.company_name}
          </option>
        ))}
      </SelectField>
      <UserSelect label="Owner" name="owner_user_id" value={ownerId} onChange={setOwnerId} includeResigned />
      <TextField label="Vendor" name="vendor" value={vendor} onChange={setVendor} />
      <SelectField label="단계" name="stage" value={stage} onChange={setStage}>
        <option value="">전체</option>
        {DEAL_STAGES.map((code) => (
          <option key={code} value={code}>
            {STAGE_LABEL[code]}
          </option>
        ))}
      </SelectField>
      <TextField label="매출 시작일" name="revenue_from" type="date" value={from} onChange={setFrom} />
      <TextField label="매출 종료일" name="revenue_to" type="date" value={to} onChange={setTo} />
      <button type="submit">검색</button>
    </form>
  )
}
