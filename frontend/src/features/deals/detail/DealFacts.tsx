import type { ReactNode } from 'react'
import { useDealFacets } from '../../../data/deals'
import { formatDate } from '../../../shared/format'
import type { DealDetail, PocState, QuoteSubmitted } from '../../../shared/model/types'
import { InlineEdit } from './InlineEdit'
import { useDealPatch } from './useDealPatch'

const QUOTE_TEXT: Record<QuoteSubmitted, string> = { YES: '제출', NO: '미제출' }
const POC_TEXT: Record<PocState, string> = { YES: '완료', ING: '진행 중', NO: '하지 않음' }
const NONE = { value: '', label: '선택 안 함' }
const QUOTE_OPTIONS = [NONE, { value: 'YES', label: 'YES' }, { value: 'NO', label: 'NO' }]
const POC_OPTIONS = [NONE, { value: 'YES', label: 'YES' }, { value: 'ING', label: 'ING' }, { value: 'NO', label: 'NO' }]

interface DealFactsProps {
  deal: DealDetail
  canWrite: boolean
  onNotice: (message: string) => void
}

/** 단계(YES/ING/NO)와 날짜를 따로 클릭해 고치는 쌍의 날짜 표시. 쓰기 권한이 없고 값도 없으면 아무것도 그리지 않는다. */
function dateDisplay(date: string | null, canWrite: boolean): ReactNode {
  if (date) return ` (${date})`
  return canWrite ? <span className="dd-muted"> 일자 입력</span> : null
}

/** Deal 정보 타일의 항목 행(Vendor·Solution·Users·견적·POC·구매절차·등록일). 값을 클릭해 그 자리에서 고친다. */
export function DealFacts({ deal, canWrite, onNotice }: DealFactsProps) {
  const { save } = useDealPatch(deal.code, onNotice)
  const facets = useDealFacets().data
  const options = (list: readonly string[] | undefined) => (list ?? []).map((value) => ({ value }))
  const { quote, poc } = deal

  async function saveText(field: 'vendor' | 'solution' | 'procurement', text: string, message: string) {
    const value = text.trim()
    if (value !== deal[field]) await save({ [field]: value }, message)
  }

  async function saveUsers(text: string) {
    const raw = text.trim()
    if (raw !== '' && !(/^\d+$/.test(raw) && Number(raw) >= 1)) throw new Error('Users는 1 이상의 정수로 입력하세요.')
    const users = raw === '' ? null : Number(raw)
    if (users !== deal.users) await save({ users }, 'Users가 변경되었습니다.')
  }

  async function saveQuote(patch: Partial<typeof quote>, message: string) {
    await save({ quote: { ...quote, ...patch } }, message)
  }

  async function savePoc(patch: Partial<typeof poc>, message: string) {
    await save({ poc: { ...poc, ...patch } }, message)
  }

  const facts: Array<[string, ReactNode]> = [
    [
      'Vendor',
      <InlineEdit
        key="vendor"
        label="Vendor"
        canEdit={canWrite}
        kind="combo"
        options={options(facets?.vendors)}
        display={deal.vendor || '—'}
        initial={deal.vendor}
        onSave={(text) => saveText('vendor', text, 'Vendor가 변경되었습니다.')}
      />,
    ],
    [
      'Solution',
      <InlineEdit
        key="solution"
        label="Solution"
        canEdit={canWrite}
        kind="combo"
        options={options(facets?.solutions)}
        display={deal.solution || '—'}
        initial={deal.solution}
        onSave={(text) => saveText('solution', text, 'Solution이 변경되었습니다.')}
      />,
    ],
    [
      'Users',
      <InlineEdit
        key="users"
        label="Users"
        canEdit={canWrite}
        kind="number"
        display={String(deal.users ?? '—')}
        initial={deal.users === null ? '' : String(deal.users)}
        onSave={saveUsers}
      />,
    ],
    [
      '견적',
      <>
        <InlineEdit
          label="견적 제출여부"
          canEdit={canWrite}
          kind="select"
          options={QUOTE_OPTIONS}
          display={quote.submitted === null ? '—' : QUOTE_TEXT[quote.submitted]}
          initial={quote.submitted ?? ''}
          onSave={(text) => saveQuote({ submitted: text === 'YES' || text === 'NO' ? text : null }, '견적 제출여부가 변경되었습니다.')}
        />
        <InlineEdit
          label="견적 제출일"
          canEdit={canWrite}
          kind="date"
          display={dateDisplay(quote.submittedDate, canWrite)}
          initial={quote.submittedDate ?? ''}
          onSave={(text) => saveQuote({ submittedDate: text || null }, '견적 제출일이 변경되었습니다.')}
        />
      </>,
    ],
    [
      'POC',
      <>
        <InlineEdit
          label="POC 여부"
          canEdit={canWrite}
          kind="select"
          options={POC_OPTIONS}
          display={poc.state === null ? '—' : `${poc.state} · ${POC_TEXT[poc.state]}`}
          initial={poc.state ?? ''}
          onSave={(text) => savePoc({ state: text === 'YES' || text === 'ING' || text === 'NO' ? text : null }, 'POC 여부가 변경되었습니다.')}
        />
        <InlineEdit
          label="POC 완료일"
          canEdit={canWrite}
          kind="date"
          display={dateDisplay(poc.completedDate, canWrite)}
          initial={poc.completedDate ?? ''}
          onSave={(text) => savePoc({ completedDate: text || null }, 'POC 완료일이 변경되었습니다.')}
        />
      </>,
    ],
    [
      '구매절차',
      <InlineEdit
        key="procurement"
        label="구매절차"
        canEdit={canWrite}
        display={deal.procurement || '—'}
        initial={deal.procurement}
        onSave={(text) => saveText('procurement', text, '구매절차가 변경되었습니다.')}
      />,
    ],
    ['등록일', <span key="created" className="kv-static">{formatDate(deal.createdAt)}</span>],
  ]
  return (
    <>
      {facts.map(([label, value]) => (
        <div key={label} className="kv-row">
          <dt>{label}</dt>
          <dd>{value}</dd>
        </div>
      ))}
    </>
  )
}
