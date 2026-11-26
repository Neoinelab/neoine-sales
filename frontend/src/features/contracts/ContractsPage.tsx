import { useMemo, useState } from 'react'
import { useLicenseContracts } from '../../data/licenseContracts'
import { useToday } from '../../data/today'
import type { SortOrder } from '../../shared/model/inputs'
import type { LicenseContract } from '../../shared/model/types'
import { ErrorBanner } from '../../shared/ui/ErrorBanner'
import { Notice } from '../../shared/ui/Notice'
import { useInfiniteScroll } from '../../shared/ui/useInfiniteScroll'
import { ContractEditDialog } from './ContractEditDialog'
import { ContractFilterBar } from './ContractFilterBar'
import { ContractTable } from './ContractTable'
import { NO_CONTRACT_CONDITIONS, toContractQuery, type ContractConditions, type ContractSort } from './contractFilter'
import './contracts.css'

/** 계약관리(`/contracts`): 라이선스 계약 목록. 검색·정렬·쪽 나누기는 서버가 하고 화면은 50건씩 이어서 읽는다. */
export function ContractsPage() {
  const [conditions, setConditions] = useState<ContractConditions>(NO_CONTRACT_CONDITIONS)
  const [sort, setSort] = useState<ContractSort>('issuancePriority')
  const [order, setOrder] = useState<SortOrder>('asc')
  const [editing, setEditing] = useState<LicenseContract | null>(null)
  const [notice, setNotice] = useState<string | null>(null)
  const { today } = useToday()
  const query = useMemo(() => toContractQuery(conditions, sort, order), [conditions, sort, order])
  const contracts = useLicenseContracts(query)
  const { fetchNextPage } = contracts
  const sentinelRef = useInfiniteScroll({
    hasNextPage: contracts.hasNextPage,
    isFetchingNextPage: contracts.isFetchingNextPage,
    fetchNextPage: () => void fetchNextPage(),
    pages: contracts.pageCount,
  })
  const loaded = contracts.data !== undefined && !contracts.isPlaceholderData

  function search(next: ContractConditions) {
    setConditions(next)
    setSort('issuancePriority')
    setOrder('asc')
  }

  function toggleSort(column: ContractSort) {
    if (column === sort) setOrder(order === 'asc' ? 'desc' : 'asc')
    else {
      setSort(column)
      setOrder('asc')
    }
  }

  return (
    <div className="contracts-page">
      <div className="heading">
        <h1>계약관리</h1>
      </div>

      <ContractFilterBar applied={conditions} onSearch={search} onReset={() => search(NO_CONTRACT_CONDITIONS)} />

      <p className="hint contracts-count">전체 {contracts.total}건</p>
      {notice && (
        <Notice kind="success" onClose={() => setNotice(null)}>
          {notice}
        </Notice>
      )}
      <ErrorBanner error={contracts.error} />
      {contracts.data !== undefined && (
        <ContractTable rows={contracts.items} sort={sort} order={order} onSort={toggleSort} today={today} onEdit={setEditing} />
      )}
      {contracts.isPending && <p className="hint">불러오는 중…</p>}
      {loaded && contracts.total === 0 && <p className="contracts-empty">조건에 맞는 계약이 없습니다.</p>}
      {contracts.hasNextPage && (
        <div ref={sentinelRef} className="contracts-more">
          <button type="button" disabled={contracts.isFetchingNextPage} onClick={() => void fetchNextPage()}>
            더 보기
          </button>
        </div>
      )}
      {loaded && !contracts.hasNextPage && contracts.total > 0 && <p className="hint contracts-end">모두 불러왔습니다 (전체 {contracts.total}건)</p>}
      {editing && (
        <ContractEditDialog
          key={`edit-${editing.id}`}
          contract={editing}
          today={today}
          onClose={() => setEditing(null)}
          onDone={(message) => {
            setEditing(null)
            setNotice(message)
          }}
        />
      )}
    </div>
  )
}
