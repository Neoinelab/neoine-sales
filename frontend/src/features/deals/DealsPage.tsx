import { useState } from 'react'
import { Link } from 'react-router'
import { PAGE_SIZE } from '../../shared/constants'
import { formatAmount } from '../../shared/format'
import { ErrorBanner } from '../../shared/ui/ErrorBanner'
import { Pager } from '../../shared/ui/Pager'
import { useCustomerOptions } from '../customers/hooks'
import { DealFilterBar } from './DealFilterBar'
import { DealForm } from './DealForm'
import { PipelineSummary } from './PipelineSummary'
import { STAGE_LABEL } from './stages'
import { useDeals, useDeleteDeal, type Deal, type DealFilters } from './hooks'

/** 값이 있는 검색 조건이 하나라도 있는지(빈 폼이 넘기는 undefined 키는 조건이 아니다). */
function hasCondition(filters: DealFilters): boolean {
  return Object.values(filters).some((v) => v !== undefined && v !== '' && v !== false)
}

/** 두 검색 조건이 같은지(undefined·빈 값·false는 조건 없음으로 보고 비교한다). */
function sameFilters(a: DealFilters, b: DealFilters): boolean {
  const clean = (f: DealFilters) =>
    Object.entries(f)
      .filter(([, v]) => v !== undefined && v !== '' && v !== false)
      .sort(([x], [y]) => x.localeCompare(y))
  return JSON.stringify(clean(a)) === JSON.stringify(clean(b))
}

type Editing = { kind: 'new' } | { kind: 'edit'; deal: Deal } | null

export function DealsPage() {
  const [offset, setOffset] = useState(0)
  const [filters, setFilters] = useState<DealFilters>({})
  const [editing, setEditing] = useState<Editing>(null)
  const deals = useDeals(filters, offset)
  const customers = useCustomerOptions()
  const remove = useDeleteDeal()
  const items = deals.data?.items ?? []
  const mine = filters.mine === true
  const searching = hasCondition(filters)
  const customerName = new Map(customers.data?.items.map((c) => [c.id, c.company_name]))

  return (
    <section>
      <div className="heading">
        <h1>딜</h1>
        <button type="button" className="primary" onClick={() => setEditing({ kind: 'new' })}>
          딜 등록
        </button>
      </div>
      <ErrorBanner error={deals.error ?? remove.error} />
      {editing && (
        <DealForm
          key={editing.kind === 'edit' ? editing.deal.id : 'new'}
          initial={editing.kind === 'edit' ? editing.deal : undefined}
          onDone={() => setEditing(null)}
        />
      )}
      <label>
        <input
          type="checkbox"
          checked={mine}
          onChange={(e) => {
            setFilters({ ...filters, mine: e.target.checked })
            setOffset(0)
          }}
        />{' '}
        내 딜만
      </label>
      <p className="hint">내가 등록한 딜만 목록과 파이프라인 현황에 표시합니다.</p>
      <DealFilterBar
        onSearch={(conditions) => {
          const next = { ...conditions, mine }
          // 조건이 그대로면 쿼리 키가 같아 재조회되지 않으므로, 검색 버튼은 직접 다시 조회한다.
          if (sameFilters(next, filters) && offset === 0) void deals.refetch()
          setFilters(next)
          setOffset(0)
        }}
      />
      <PipelineSummary mine={mine} />
      <table>
        <thead>
          <tr>
            <th>Deal Code</th>
            <th>Deal Name</th>
            <th>Owner</th>
            <th>Vendor</th>
            <th>Solution</th>
            <th>단계</th>
            <th>매출금액</th>
            <th>매출일</th>
            <th>고객</th>
            <th />
          </tr>
        </thead>
        <tbody>
          {items.map((d) => (
            <tr key={d.id}>
              <td>
                <Link to={`/deals/${d.id}`}>{d.code}</Link>
              </td>
              <td>{d.name}</td>
              <td>{d.owner}</td>
              <td>{d.vendor}</td>
              <td>{d.solution}</td>
              <td>{STAGE_LABEL[d.stage]}</td>
              <td className="num">{formatAmount(d.revenue_amount, d.revenue_currency)}</td>
              <td>{d.revenue_date}</td>
              <td>{customerName.get(d.customer_id) ?? ''}</td>
              <td className="row-actions">
                <button type="button" onClick={() => setEditing({ kind: 'edit', deal: d })}>
                  수정
                </button>
                <button
                  type="button"
                  onClick={() => {
                    if (window.confirm(`${d.code} 딜을 삭제할까요?`)) remove.mutate(d.id)
                  }}
                >
                  삭제
                </button>
              </td>
            </tr>
          ))}
          {deals.isSuccess && items.length === 0 && (
            <tr>
              <td colSpan={10}>{searching ? '조건에 맞는 딜이 없습니다.' : '등록된 딜이 없습니다.'}</td>
            </tr>
          )}
        </tbody>
      </table>
      <Pager offset={offset} limit={PAGE_SIZE} count={items.length} onChange={setOffset} />
    </section>
  )
}
