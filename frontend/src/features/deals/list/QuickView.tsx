import { Link } from 'react-router'
import { useLabels } from '../../../data/labels'
import { BANT_CATEGORIES, BANT_CATEGORY_NAMES } from '../../../shared/model/constants'
import type { Contact, DealRow } from '../../../shared/model/types'

function contactLine(contact: Contact): string {
  return [contact.name, contact.title, contact.email, contact.phone].filter(Boolean).join(' · ')
}

function dated(value: string | null, date: string | null): string {
  if (!value) return '—'
  return date ? `${value} (${date})` : value
}

/** 행 아래로 펼치는 빠른 보기: 견적·POC·고객 담당자·파트너 영업대표·BANT·Users count·구매절차. */
export function QuickView({ row }: { row: DealRow }) {
  // 목록은 Label을 미리 읽지 않는다. 고른 Label이 있는 구분만 로딩·실패를 보이고, 고르지 않은 구분은 '—'.
  const labels = useLabels()
  const labelName = (id: number | null) => {
    if (id === null) return '—'
    if (labels.data) return labels.data.find((l) => l.id === id)?.name ?? '—'
    return labels.error ? '불러오지 못함' : '불러오는 중…'
  }

  return (
    <section className="quick-view" aria-label={`빠른 보기: ${row.name}`}>
      <dl>
        <div>
          <dt>견적</dt>
          <dd>{dated(row.quote.submitted, row.quote.submittedDate)}</dd>
        </div>
        <div>
          <dt>POC</dt>
          <dd>{dated(row.poc.state, row.poc.completedDate)}</dd>
        </div>
        <div>
          <dt>고객 담당자</dt>
          <dd>{contactLine(row.customer)}</dd>
        </div>
        <div>
          <dt>파트너 영업대표</dt>
          <dd>{row.activePartner ? contactLine(row.activePartner) : '파트너 없음'}</dd>
        </div>
        {BANT_CATEGORIES.map((category) => (
          <div key={category}>
            <dt>{BANT_CATEGORY_NAMES[category]}</dt>
            <dd>{labelName(row.bant[category])}</dd>
          </div>
        ))}
        <div>
          <dt>Users count</dt>
          <dd>{row.users.toLocaleString('en-US')}</dd>
        </div>
        <div>
          <dt>구매절차</dt>
          <dd>{row.procurement || '—'}</dd>
        </div>
      </dl>
      <Link to={`/deals/${row.code}`} className="quick-view-link">
        상세 보기
      </Link>
    </section>
  )
}
