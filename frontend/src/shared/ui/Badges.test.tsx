import { render, screen } from '@testing-library/react'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import type { CodeSet } from '../model/types'
import { AmountText } from './AmountText'
import { ForecastBadge, StatusBadge } from './Badges'
import { RiskBadge, riskRowClass } from './RiskBadge'

const CODES: CodeSet = {
  statuses: [
    { id: 1, kind: 'status', key: 'poc', name: 'POC', order: 1, locked: false, outcome: 'open', probabilityHint: null },
    { id: 2, kind: 'status', key: 'contract_completed', name: '계약완료', order: 2, locked: true, outcome: 'open', probabilityHint: null },
  ],
  forecasts: [
    { id: 4, kind: 'forecast', key: 'commit', name: 'Commit', order: 1, locked: false, outcome: 'open', probabilityHint: '90%' },
    { id: 5, kind: 'forecast', key: 'won', name: '수주', order: 2, locked: true, outcome: 'won', probabilityHint: null },
    { id: 6, kind: 'forecast', key: 'lost', name: 'Lost', order: 3, locked: true, outcome: 'lost', probabilityHint: null },
  ],
}

const codeSetState = vi.hoisted(() => ({ data: undefined as unknown }))
vi.mock('../../data/codes', () => ({ useCodeSet: () => ({ data: codeSetState.data }) }))
vi.mock('../model/money', () => ({
  formatWon: (n: number) => `fmt:${n}`,
}))

beforeEach(() => {
  codeSetState.data = CODES
})

describe('StatusBadge / ForecastBadge', () => {
  // Status·Forecast 배지는 키가 아니라 현재 코드 이름을 보인다.
  it('shows the current code name, not the key', () => {
    // when: 두 배지를 그린다
    render(
      <>
        <StatusBadge statusKey="contract_completed" />
        <ForecastBadge forecastKey="won" />
      </>,
    )
    // then: '계약완료'와 '수주' 이름이 보인다
    expect(screen.getByText('계약완료')).toBeInTheDocument()
    expect(screen.getByText('수주')).toBeInTheDocument()
  })

  // Won·Lost는 열린 값과 다르게 data-outcome으로 표시한다.
  it('marks the outcome so Won and Lost look different from open values', () => {
    // when: 세 배지를 그린다
    render(
      <>
        <ForecastBadge forecastKey="won" />
        <ForecastBadge forecastKey="lost" />
        <ForecastBadge forecastKey="commit" />
      </>,
    )
    // then: won·lost·open 결과 표식이 붙는다
    expect(screen.getByText('수주')).toHaveAttribute('data-outcome', 'won')
    expect(screen.getByText('Lost')).toHaveAttribute('data-outcome', 'lost')
    expect(screen.getByText('Commit')).toHaveAttribute('data-outcome', 'open')
  })

  // 코드를 못 읽었으면 키를 그대로 보인다.
  it('falls back to the key while codes are loading or unknown', () => {
    // given: 코드 목록이 아직 없는 상태
    codeSetState.data = undefined
    // when: poc Status 배지를 그린다
    render(<StatusBadge statusKey="poc" />)
    // then: 키 'poc'가 보인다
    expect(screen.getByText('poc')).toBeInTheDocument()
  })
})

describe('AmountText', () => {
  // 금액 글자는 title 없이 포맷한 숫자를 보인다.
  it('shows the thousand-won number without a title', () => {
    // when: AmountText를 그린다
    render(<AmountText amount={180000000} />)
    // then: 포맷한 숫자가 보이고 title이 없다
    const el = screen.getByText('fmt:180000000')
    expect(el).not.toHaveAttribute('title')
  })
})

describe('RiskBadge', () => {
  // 경고가 없으면 아무것도 그리지 않는다.
  // 테스트 코드: RK-051
  it('renders nothing for no risk', () => {
    // when: risk가 null인 RiskBadge를 그린다
    const { container } = render(<RiskBadge risk={null} />)

    // then: 아무것도 그려지지 않는다
    expect(container).toBeEmptyDOMElement()
  })

  // 경고 배지는 색만이 아니라 텍스트 라벨로 구분한다.
  // 테스트 코드: RK-051
  it('uses text labels, not only color', () => {
    // when: overdue와 stale 배지를 그린다
    render(
      <>
        <RiskBadge risk="overdue" />
        <RiskBadge risk="stale" />
      </>,
    )

    // then: '기한초과'와 '미업데이트' 텍스트가 보인다
    expect(screen.getByText('기한초과')).toBeInTheDocument()
    expect(screen.getByText('미업데이트')).toBeInTheDocument()
  })

  // overdue_stale이면 두 라벨을 모두 보인다.
  // 테스트 코드: RK-051
  it('shows both labels when overdue and stale', () => {
    // when: overdue_stale 배지를 그린다
    render(<RiskBadge risk="overdue_stale" />)

    // then: '기한초과'와 '미업데이트'가 함께 보인다
    expect(screen.getByText('기한초과')).toBeInTheDocument()
    expect(screen.getByText('미업데이트')).toBeInTheDocument()
  })

  // 행 클래스는 기한초과가 우선이다.
  // 테스트 코드: RK-051
  it('gives overdue rows precedence for the row class', () => {
    // when: 각 경고의 행 클래스를 구한다
    const result1 = riskRowClass('overdue')
    const result2 = riskRowClass('overdue_stale')
    const result3 = riskRowClass('stale')
    const result4 = riskRowClass(null)
    // then: overdue와 overdue_stale은 risk-overdue, stale은 risk-stale, 없으면 빈 문자열이다
    expect(result1).toBe('risk-overdue')
    expect(result2).toBe('risk-overdue')
    expect(result3).toBe('risk-stale')
    expect(result4).toBe('')
  })
})
