import { formatKrwShort } from '../../../shared/model/money'
import type { CodeSet, DealDetail, DealRow } from '../../../shared/model/types'
import { withGa, withRo } from '../../../shared/model/text'

/** 목록에서 바로 고칠 수 있는 4개 열(DL-08). */
export type InlineField = 'statusKey' | 'forecastKey' | 'revenueAmount' | 'revenueDate'

export const INLINE_LABEL: Record<InlineField, string> = {
  statusKey: 'Status',
  forecastKey: 'Forecast',
  revenueAmount: '금액',
  revenueDate: 'Expected Close',
}

/** 편집 시작 값(입력란에 보여 줄 문자열). */
export function initialDraft(row: DealRow, field: InlineField): string {
  if (field === 'revenueAmount') return String(row.revenueAmount)
  return row[field]
}

function codeName(codes: CodeSet | undefined, field: 'statusKey' | 'forecastKey', key: string): string {
  const list = field === 'statusKey' ? codes?.statuses : codes?.forecasts
  return list?.find((c) => c.key === key)?.name ?? key
}

/** 저장 성공 알림. 함께 바뀐 값이 있으면 서버(게이트웨이) 문구를 그대로 쓴다. */
export function savedMessage(
  row: DealRow,
  field: InlineField,
  draft: string,
  codes: CodeSet | undefined,
  result: { deal: DealDetail; notice: string | null },
): string {
  if (result.notice) return `${row.name}: ${result.notice}`
  const label = INLINE_LABEL[field]
  if (field === 'statusKey' || field === 'forecastKey') {
    const name = codeName(codes, field, draft)
    return `${row.name}: ${withGa(label)} '${name}'${withRo(name).slice(name.length)} 변경되었습니다.`
  }
  const shown = field === 'revenueAmount' ? formatKrwShort(result.deal.revenueAmount) : result.deal.revenueDate
  return `${row.name}: ${withGa(label)} '${shown}'(으)로 변경되었습니다.`
}
