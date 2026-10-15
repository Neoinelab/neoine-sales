import { useState } from 'react'
import { useHistory } from '../../../data/history'
import { formatDateTime } from '../../../shared/format'
import { HISTORY_CATEGORY_LABELS } from '../../../shared/model/history'
import { userLabel } from '../../../shared/model/period'
import type { HistoryCategory } from '../../../shared/model/types'
import { ErrorBanner } from '../../../shared/ui/ErrorBanner'
import { Pager } from '../../../shared/ui/Pager'
import { messageOf } from './detailHelpers'
import { useLatest } from './useLatest'
import './detail.css'

const PAGE_SIZE = 20

/** Deal History 탭: 읽기 전용. 변경 대상 필터와 20건 단위 페이지. */
export function HistoryTab({ dealCode }: { dealCode: string }) {
  const [category, setCategory] = useState<HistoryCategory | ''>('')
  const [offset, setOffset] = useState(0)
  const history = useHistory(dealCode, category === '' ? {} : { category })
  const entries = useLatest(history.data) ?? []
  const rows = entries.slice(offset, offset + PAGE_SIZE)

  return (
    <div className="dd-page">
      <div className="dd-toolbar">
        <label className="field">
          <span>변경 대상</span>
          <select
            value={category}
            onChange={(e) => {
              setCategory(e.target.value as HistoryCategory | '')
              setOffset(0)
            }}
          >
            <option value="">전체</option>
            {(Object.entries(HISTORY_CATEGORY_LABELS) as [HistoryCategory, string][]).map(([key, label]) => (
              <option key={key} value={key}>
                {label}
              </option>
            ))}
          </select>
        </label>
        <p className="hint">Action 수정·삭제와 첨부 파일 변경도 이 이력에 기록됩니다.</p>
      </div>
      <ErrorBanner error={history.error} format={messageOf} />
      {history.isPending && <p role="status">불러오는 중…</p>}
      {history.isSuccess && entries.length === 0 && <p className="hint">변경 이력이 없습니다.</p>}
      {entries.length > 0 && (
        <>
          <div className="dd-scroll">
            <table className="dd-table" aria-label="Deal History">
              <thead>
                <tr>
                  <th>변경 시각</th>
                  <th>변경자</th>
                  <th>변경 대상</th>
                  <th>변경 전</th>
                  <th>변경 후</th>
                </tr>
              </thead>
              <tbody>
                {rows.map((h) => (
                  <tr key={h.id}>
                    <td>{formatDateTime(h.at)}</td>
                    <td>{userLabel(h.by)}</td>
                    <td>{h.target}</td>
                    <td className="wrap">{h.before || '—'}</td>
                    <td className="wrap">{h.after || '—'}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
          <Pager offset={offset} limit={PAGE_SIZE} total={entries.length} onChange={setOffset} />
        </>
      )}
    </div>
  )
}
