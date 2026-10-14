import { formatDateTime } from '../../shared/format'
import { ErrorBanner } from '../../shared/ui/ErrorBanner'
import { STAGE_HISTORY_LIMIT, useDealStageChanges } from './hooks'
import { STAGE_LABEL } from './stages'

/** 딜의 단계 변경 이력(API가 주는 최신순 그대로). */
export function StageHistory({ dealId }: { dealId: string }) {
  const changes = useDealStageChanges(dealId, 0)
  const items = changes.data?.items ?? []
  // 불러오는 동안에는 영역(region)을 만들지 않는다. 완료(성공·실패) 후에 이름 있는 영역으로 나타난다.
  if (changes.isPending) {
    return (
      <div>
        <h2>단계 이력</h2>
        <p>불러오는 중…</p>
      </div>
    )
  }
  return (
    <section aria-label="단계 이력">
      <h2>단계 이력</h2>
      <ErrorBanner error={changes.error} />
      {changes.isSuccess && items.length === 0 && <p>단계 변경 이력이 없습니다.</p>}
      {items.length >= STAGE_HISTORY_LIMIT && <p>최근 {STAGE_HISTORY_LIMIT}건만 표시됩니다.</p>}
      {items.length > 0 && (
        <ul>
          {items.map((c) => (
            <li key={c.id}>
              {formatDateTime(c.changed_at)} · {STAGE_LABEL[c.from_stage]} → {STAGE_LABEL[c.to_stage]} ·{' '}
              {c.changed_by.label}
              {c.reason ? ` · ${c.reason}` : ''}
            </li>
          ))}
        </ul>
      )}
    </section>
  )
}
