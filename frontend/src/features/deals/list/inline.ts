import { AMOUNT_LABEL, formatThousandWon } from '../../../shared/model/money'
import type { CodeSet, DealDetail, DealRow } from '../../../shared/model/types'
import { withGa, withRo } from '../../../shared/model/text'

/** 목록에서 바로 고칠 수 있는 4개 열(DL-08). */
export type InlineField = 'statusKey' | 'forecastKey' | 'revenueAmount' | 'revenueDate'

export const INLINE_LABEL: Record<InlineField, string> = {
  statusKey: 'Status',
  forecastKey: 'Forecast',
  revenueAmount: AMOUNT_LABEL,
  revenueDate: 'Expected Close',
}

/** 편집 시작 값(입력란에 보여 줄 문자열). */
export function initialDraft(row: DealRow, field: InlineField): string {
  if (field === 'revenueAmount') return formatThousandWon(row.revenueAmount)
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
  // 금액 라벨은 ')'로 끝나 조사 계산(withGa)이 틀리므로 고정 문구를 쓴다.
  if (field === 'revenueAmount') {
    return `${row.name}: ${AMOUNT_LABEL}이 '${formatThousandWon(result.deal.revenueAmount)}'(으)로 변경되었습니다.`
  }
  return `${row.name}: ${withGa(label)} '${result.deal.revenueDate}'(으)로 변경되었습니다.`
}
