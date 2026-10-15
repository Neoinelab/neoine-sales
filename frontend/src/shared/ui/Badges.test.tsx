import { render, screen } from '@testing-library/react'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import type { CodeSet } from '../model/types'
import { AmountText } from './AmountText'
import { ForecastBadge, StatusBadge } from './Badges'
import { RiskBadge, riskRowClass } from './RiskBadge'

const CODES: CodeSet = {
  statuses: [
    { id: 's1', kind: 'status', key: 'poc', name: 'POC', order: 1, locked: false, outcome: 'open', probabilityHint: null },
    { id: 's2', kind: 'status', key: 'contract_completed', name: '계약완료', order: 2, locked: true, outcome: 'open', probabilityHint: null },
  ],
  forecasts: [
    { id: 'f1', kind: 'forecast', key: 'commit', name: 'Commit', order: 1, locked: false, outcome: 'open', probabilityHint: '90%' },
    { id: 'f2', kind: 'forecast', key: 'won', name: '수주', order: 2, locked: true, outcome: 'won', probabilityHint: null },
    { id: 'f3', kind: 'forecast', key: 'lost', name: 'Lost', order: 3, locked: true, outcome: 'lost', probabilityHint: null },
  ],
}

const codeSetState = vi.hoisted(() => ({ data: undefined as unknown }))
vi.mock('../../data/codes', () => ({ useCodeSet: () => ({ data: codeSetState.data }) }))
vi.mock('../model/money', () => ({
  formatKrwShort: (n: number) => `short:${n}`,
  formatKrwFull: (n: number) => `full:${n}`,
}))

beforeEach(() => {
  codeSetState.data = CODES
})

describe('StatusBadge / ForecastBadge', () => {
  it('shows the current code name, not the key', () => {
    render(
      <>
        <StatusBadge statusKey="contract_completed" />
        <ForecastBadge forecastKey="won" />
      </>,
    )

    expect(screen.getByText('계약완료')).toBeInTheDocument()
    expect(screen.getByText('수주')).toBeInTheDocument()
  })

  it('marks the outcome so Won and Lost look different from open values', () => {
    render(
      <>
        <ForecastBadge forecastKey="won" />
        <ForecastBadge forecastKey="lost" />
        <ForecastBadge forecastKey="commit" />
      </>,
    )

    expect(screen.getByText('수주')).toHaveAttribute('data-outcome', 'won')
    expect(screen.getByText('Lost')).toHaveAttribute('data-outcome', 'lost')
    expect(screen.getByText('Commit')).toHaveAttribute('data-outcome', 'open')
  })

  it('falls back to the key while codes are loading or unknown', () => {
    codeSetState.data = undefined
    render(<StatusBadge statusKey="poc" />)

    expect(screen.getByText('poc')).toBeInTheDocument()
  })
})

describe('AmountText', () => {
  it('shows the short form with the full amount as title', () => {
    render(<AmountText amount={180000000} />)

    const el = screen.getByText('short:180000000')
    expect(el).toHaveAttribute('title', 'full:180000000')
  })
})

describe('RiskBadge', () => {
  it('renders nothing for no risk', () => {
    const { container } = render(<RiskBadge risk={null} />)

    expect(container).toBeEmptyDOMElement()
  })

  it('uses text labels, not only color', () => {
    render(
      <>
        <RiskBadge risk="overdue" />
        <RiskBadge risk="stale" />
      </>,
    )

    expect(screen.getByText('기한초과')).toBeInTheDocument()
    expect(screen.getByText('미업데이트')).toBeInTheDocument()
  })

  it('shows both labels when overdue and stale', () => {
    render(<RiskBadge risk="overdue_stale" />)

    expect(screen.getByText('기한초과')).toBeInTheDocument()
    expect(screen.getByText('미업데이트')).toBeInTheDocument()
  })

  it('gives overdue rows precedence for the row class', () => {
    expect(riskRowClass('overdue')).toBe('risk-overdue')
    expect(riskRowClass('overdue_stale')).toBe('risk-overdue')
    expect(riskRowClass('stale')).toBe('risk-stale')
    expect(riskRowClass(null)).toBe('')
  })
})
