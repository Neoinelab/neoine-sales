import { formatAmount } from '../../shared/format'
import { useDealPipeline } from './hooks'
import { STAGE_LABEL } from './stages'

/** 단계별 딜 건수와 통화별 매출 합계. 불러오지 못하면 목록을 가리지 않도록 아무것도 그리지 않는다. */
export function PipelineSummary({ mine = false }: { mine?: boolean }) {
  const pipeline = useDealPipeline({ mine })
  if (!pipeline.data) return null

  return (
    <section aria-label="파이프라인 현황" className="pipeline">
      <h2>파이프라인 현황</h2>
      <ul>
        {pipeline.data.stages.map((s) => (
          <li key={s.stage}>
            <span>{STAGE_LABEL[s.stage]}</span> <strong>{s.deal_count}건</strong>
            {s.totals.map((t) => (
              <div key={t.currency}>{formatAmount(t.amount, t.currency)}</div>
            ))}
          </li>
        ))}
      </ul>
    </section>
  )
}
