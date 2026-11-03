import { useId } from 'react'
import type { ReportChartLegend } from '../../../shared/model/reportTypes'
import type { DesignerAction, DesignerColumn } from '../designer/state/designerState'
import type { Message } from '../designer/state/issueView'
import { kindRule } from './chartKinds'
import { comboSettings, type ChartDraft, type ChartDraftIssue } from './chartDraft'
import { ComboSeriesEditor } from './ComboSeriesEditor'
import { HistogramOptions } from './HistogramOptions'
import { KindPicker } from './KindPicker'

const LEGENDS: { value: ReportChartLegend; label: string }[] = [
  { value: 'top', label: '위' },
  { value: 'right', label: '오른쪽' },
  { value: 'bottom', label: '아래' },
  { value: 'none', label: '숨김' },
]

interface PanelProps {
  draft: ChartDraft
  columns: readonly DesignerColumn[]
  headerOf: (uid: number) => string
  /** 화면에서 판정한 안내(칸 옆에 보인다). */
  issues: readonly ChartDraftIssue[]
  /** 저장 때 서버가 알려 준 위반. 화면 안내와 같은 문구는 한 번만 보인다. */
  serverIssues: readonly Message[]
  dispatch: (action: DesignerAction) => void
}

/** 칸 하나의 안내 문구 목록과 입력에 붙일 접근성 속성. */
function useNotes(issues: readonly ChartDraftIssue[], serverIssues: readonly Message[]) {
  const base = useId()
  const own = new Set(issues.map((i) => i.message))
  const notes = (part: string): { id: string; text: string }[] => [
    ...issues.filter((i) => i.part === part).map((i) => ({ id: `${base}-${part}`, text: i.message })),
    ...serverIssues.filter((m) => m.part === part && !own.has(m.text)).map((m) => ({ id: m.id, text: m.text })),
  ]
  const aria = (part: string): { 'aria-invalid'?: true; 'aria-describedby'?: string } => {
    const list = notes(part)
    return list.length > 0 ? { 'aria-invalid': true, 'aria-describedby': [...new Set(list.map((n) => n.id))].join(' ') } : {}
  }
  return { notes, aria }
}

function Notes({ list }: { list: { id: string; text: string }[] }) {
  return (
    <>
      {list.map((n, i) => (
        <p key={`${n.id}-${i}`} id={i === 0 ? n.id : undefined} className="error">
          {n.text}
        </p>
      ))}
    </>
  )
}

/** 칸 옆에 직접 보이는 위치(나머지 서버 위반은 패널 위쪽에 모아 보인다). */
const FIELD_PARTS = ['category', 'series', 'values', 'value_min', 'value_max', 'combo_series']
const ownPart = (part: string | null): boolean => part !== null && (FIELD_PARTS.includes(part) || part.startsWith('histogram.'))

/** 축이 없는 종류(원·도넛·방사형·트리맵·선버스트). */
const NO_AXES: readonly string[] = ['pie', 'doughnut', 'radar', 'radar_markers', 'radar_filled', 'treemap', 'sunburst']

/** 시안 9장의 설정 패널: 종류 · 데이터 · 종류별 옵션 · 제목과 범례 · 축. 쓰지 않는 칸은 이유와 함께 비활성이다. */
export function ChartSettingsPanel({ draft, columns, headerOf, issues, serverIssues, dispatch }: PanelProps) {
  const ids = useId()
  const { notes, aria } = useNotes(issues, serverIssues)
  const rule = kindRule(draft.kind)
  const groups = columns.filter((c) => c.group)
  const values = columns.filter((c) => !c.group)
  const change = (patch: Partial<ChartDraft>) => dispatch({ type: 'changeChart', patch })
  const horizontal = draft.kind.includes('horizontal') || draft.kind === 'funnel'
  const valueMax = draft.seriesUid === null ? rule.valuesMax : 1
  const noAxes = NO_AXES.includes(draft.kind)
  const noValueAxis = noAxes || draft.kind === 'funnel'
  const noRange = rule.allowsValueRange ? undefined : '이 종류는 축 범위를 쓸 수 없습니다'
  const noAxisReason = noAxes ? '이 종류는 축이 없습니다' : undefined
  const noValueAxisReason = noAxes ? noAxisReason : noValueAxis ? '깔때기는 값 축을 보이지 않습니다' : undefined
  const combo = rule.options.includes('combo_series')
  const noCategory = !rule.usesCategory
  const textOf = (part: string): string | undefined => notes(part).map((n) => n.text).join(' ') || undefined
  const histogramIssues = {
    bin_mode: textOf('histogram.bin_mode'),
    bin_count: textOf('histogram.bin_count'),
    bin_width: textOf('histogram.bin_width'),
    overflow: textOf('histogram.overflow'),
    underflow: textOf('histogram.underflow'),
  }
  const comboSeries = comboSettings(draft)
  const rangeAxis = draft.kind.startsWith('radar') ? '반지름 축' : horizontal ? '가로축' : '세로축'

  const pickCategory = (uid: number) =>
    uid === draft.seriesUid ? change({ categoryUid: uid, seriesUid: draft.categoryUid }) : change({ categoryUid: uid })
  const pickSeries = (text: string) => {
    if (text === '') return change({ seriesUid: null })
    const uid = Number(text)
    if (uid === draft.categoryUid) return change({ seriesUid: uid, categoryUid: draft.seriesUid })
    change({ seriesUid: uid, valueUids: draft.valueUids.slice(0, 1) })
  }
  const toggleValue = (uid: number, on: boolean) => {
    const current = new Set(draft.valueUids)
    if (!on) current.delete(uid)
    else if (valueMax === 1) return change({ valueUids: [uid] })
    else current.add(uid)
    change({ valueUids: values.filter((c) => current.has(c.uid)).map((c) => c.uid) })
  }

  return (
    <div className="report-chart-panel">
      <KindPicker kind={draft.kind} groupCount={groups.length} onChange={(kind) => dispatch({ type: 'setChartKind', kind })} />
      <Notes list={serverIssues.filter((m) => !ownPart(m.part)).map((m) => ({ id: m.id, text: m.text }))} />
      <fieldset className="report-chart-group">
        <legend>데이터</legend>
        <div className="field">
          <label htmlFor={`${ids}-category`}>범주</label>
          <select
            id={`${ids}-category`}
            value={draft.categoryUid ?? ''}
            disabled={noCategory}
            title={noCategory ? '이 차트는 범주 열을 쓰지 않습니다' : undefined}
            {...aria('category')}
            onChange={(e) => pickCategory(Number(e.target.value))}
          >
            {draft.categoryUid === null && <option value="">{noCategory ? '(없음)' : '선택'}</option>}
            {groups.map((c) => (
              <option key={c.uid} value={c.uid}>
                {headerOf(c.uid)}
              </option>
            ))}
          </select>
          {noCategory && <p className="field-hint">이 차트는 범주 열을 쓰지 않습니다</p>}
          <Notes list={notes('category')} />
        </div>
        <div className="field">
          <label htmlFor={`${ids}-series`}>계열</label>
          <select
            id={`${ids}-series`}
            value={draft.seriesUid ?? ''}
            disabled={!rule.allowsSeries || groups.length < 2}
            title={rule.allowsSeries ? (groups.length < 2 ? '그룹핑 컬럼이 2개일 때 계열을 고를 수 있습니다' : undefined) : '이 종류는 계열 열을 쓰지 않습니다'}
            {...aria('series')}
            onChange={(e) => pickSeries(e.target.value)}
          >
            {groups.length < 2 && <option value="">(없음)</option>}
            {draft.seriesUid === null && groups.length === 2 && <option value="">선택</option>}
            {groups.length === 2 &&
              groups.map((c) => (
                <option key={c.uid} value={c.uid}>
                  {headerOf(c.uid)}
                </option>
              ))}
          </select>
          <Notes list={notes('series')} />
        </div>
        <fieldset className="report-chart-values">
          <legend>값</legend>
          {values.length === 0 && <p className="hint">값으로 쓸 숫자 컬럼이 없습니다</p>}
          {values.map((c) => (
            <label key={c.uid} className="report-check">
              <input type="checkbox" checked={draft.valueUids.includes(c.uid)} onChange={(e) => toggleValue(c.uid, e.target.checked)} />
              {headerOf(c.uid)}
            </label>
          ))}
          <Notes list={notes('values')} />
        </fieldset>
        <label className="report-check">
          <input
            type="checkbox"
            checked={draft.swap}
            disabled={!rule.allowsSwap}
            title={rule.allowsSwap ? undefined : '이 종류는 행/열 전환을 쓸 수 없습니다'}
            onChange={(e) => change({ swap: e.target.checked })} />
          행/열 전환
        </label>
      </fieldset>
      {rule.options.includes('histogram') && (
        <fieldset className="report-chart-group">
          <legend>구간</legend>
          <HistogramOptions value={draft.histogram} issues={histogramIssues} onChange={(next) => change({ histogram: next })} />
        </fieldset>
      )}
      {rule.options.includes('show_total') && (
        <fieldset className="report-chart-group">
          <legend>폭포</legend>
          <label className="report-check">
            <input type="checkbox" checked={draft.showTotal} onChange={(e) => change({ showTotal: e.target.checked })} />
            마지막에 합계 막대
          </label>
        </fieldset>
      )}
      {combo && (
        <fieldset className="report-chart-group">
          <legend>계열</legend>
          <ComboSeriesEditor
            columns={draft.valueUids.map((uid) => ({ uid, header: headerOf(uid) }))}
            value={Object.fromEntries(draft.valueUids.map((uid, i) => [uid, comboSeries[i]!]))}
            issue={textOf('combo_series')}
            onChange={(next) => change({ comboTypes: next, secondaryAxis: Object.values(next).some((s) => s.secondary) })}
          />
        </fieldset>
      )}
      <fieldset className="report-chart-group">
        <legend>제목과 범례</legend>
        <div className="field">
          <label htmlFor={`${ids}-title`}>차트 제목</label>
          <input id={`${ids}-title`} type="text" value={draft.title} onChange={(e) => change({ title: e.target.value })} />
        </div>
        <div className="field">
          <label htmlFor={`${ids}-legend`}>범례</label>
          <select id={`${ids}-legend`} value={draft.legend} onChange={(e) => change({ legend: e.target.value as ReportChartLegend })}>
            {LEGENDS.map((l) => (
              <option key={l.value} value={l.value}>
                {l.label}
              </option>
            ))}
          </select>
        </div>
        <label className="report-check">
          <input
            type="checkbox"
            checked={draft.dataLabels}
            disabled={draft.kind === 'treemap'}
            title={draft.kind === 'treemap' ? '트리맵은 이름과 값을 항상 보입니다' : undefined}
            onChange={(e) => change({ dataLabels: e.target.checked })}
          />
          데이터 레이블
        </label>
      </fieldset>
      <fieldset className="report-chart-group">
        <legend>축</legend>
        <div className="field">
          <label htmlFor={`${ids}-cat-axis`}>{horizontal ? '세로축 제목(범주)' : '가로축 제목'}</label>
          <input id={`${ids}-cat-axis`} type="text" value={draft.categoryAxisTitle} disabled={noAxes} title={noAxisReason} onChange={(e) => change({ categoryAxisTitle: e.target.value })} />
        </div>
        <div className="field">
          <label htmlFor={`${ids}-val-axis`}>{horizontal ? '가로축 제목(값)' : '세로축 제목'}</label>
          <input id={`${ids}-val-axis`} type="text" value={draft.valueAxisTitle} disabled={noValueAxis} title={noValueAxisReason} onChange={(e) => change({ valueAxisTitle: e.target.value })} />
        </div>
        <div className="field">
          <label htmlFor={`${ids}-min`}>{rangeAxis} 최소</label>
          <input id={`${ids}-min`} type="text" inputMode="decimal" value={draft.valueMin} disabled={!rule.allowsValueRange} title={noRange} {...aria('value_min')} onChange={(e) => change({ valueMin: e.target.value })} />
          <Notes list={notes('value_min')} />
        </div>
        <div className="field">
          <label htmlFor={`${ids}-max`}>{rangeAxis} 최대</label>
          <input id={`${ids}-max`} type="text" inputMode="decimal" value={draft.valueMax} disabled={!rule.allowsValueRange} title={noRange} {...aria('value_max')} onChange={(e) => change({ valueMax: e.target.value })} />
          <Notes list={notes('value_max')} />
        </div>
        {rule.percentAxis && <p className="field-hint">100% 누적은 0~100 사이로 입력하세요</p>}
        {!combo && (
          <label className="report-check">
            <input type="checkbox" checked={false} disabled title="보조 축은 콤보 차트에서만 쓸 수 있습니다" />
            보조 축
          </label>
        )}
      </fieldset>
    </div>
  )
}
