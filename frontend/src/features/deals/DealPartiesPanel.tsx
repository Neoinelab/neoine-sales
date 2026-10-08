import type { Schemas } from '../../shared/api/client'
import { ErrorBanner } from '../../shared/ui/ErrorBanner'
import { useCustomer } from '../customers/hooks'
import { usePartner } from '../partners/hooks'

type Contact = Pick<
  Schemas['CustomerResponse'],
  'company_name' | 'contact_name' | 'contact_title' | 'email' | 'phone'
>

interface Props {
  customerId: string
  partnerId: string | null
}

interface ContactQuery {
  data?: Contact
  error: unknown
  isPending: boolean
}

function ContactCard({ label, query }: { label: string; query: ContactQuery }) {
  const c = query.data
  return (
    <section aria-label={label}>
      <h2>{label}</h2>
      <ErrorBanner error={query.error} />
      {query.isPending && <p>불러오는 중…</p>}
      {c && (
        <dl className="summary">
          <dt>회사명</dt>
          <dd>{c.company_name}</dd>
          <dt>담당자</dt>
          <dd>{c.contact_name}</dd>
          <dt>직함</dt>
          <dd>{c.contact_title ?? '-'}</dd>
          <dt>이메일</dt>
          <dd>{c.email ?? '-'}</dd>
          <dt>전화번호</dt>
          <dd>{c.phone ?? '-'}</dd>
        </dl>
      )}
    </section>
  )
}

/** 딜에 연결된 고객·파트너 정보. 한쪽 조회가 실패해도 다른 쪽과 딜 화면은 유지한다. */
export function DealPartiesPanel({ customerId, partnerId }: Props) {
  const customer = useCustomer(customerId)
  const partner = usePartner(partnerId ?? '')
  return (
    <>
      <ContactCard label="고객 정보" query={customer} />
      {partnerId ? (
        <ContactCard label="파트너 정보" query={partner} />
      ) : (
        <section aria-label="파트너 정보">
          <h2>파트너 정보</h2>
          <p>파트너 없음</p>
        </section>
      )}
    </>
  )
}
