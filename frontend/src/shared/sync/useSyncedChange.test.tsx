import { render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { describe, expect, it, vi } from 'vitest'
import { AMOUNT_INPUT_MESSAGE } from '../model/money'
import type { SyncApplied, SyncFinalize, SyncPlan } from '../model/sync'
import type { CodeSet } from '../model/types'
import { SyncNotice } from './SyncNotice'
import { useSyncedChange } from './useSyncedChange'

const CODES: CodeSet = {
  statuses: [
    { id: 1, kind: 'status', key: 'poc_done', name: 'POC완료', order: 1, locked: false, outcome: 'open', probabilityHint: null },
    { id: 2, kind: 'status', key: 'negotiation', name: '가격협상', order: 2, locked: false, outcome: 'open', probabilityHint: null },
    { id: 3, kind: 'status', key: 'contract_completed', name: '계약완료', order: 3, locked: true, outcome: 'open', probabilityHint: null },
  ],
  forecasts: [
    { id: 4, kind: 'forecast', key: 'commit', name: 'Commit', order: 1, locked: false, outcome: 'open', probabilityHint: null },
    { id: 5, kind: 'forecast', key: 'won', name: 'Won', order: 2, locked: true, outcome: 'won', probabilityHint: null },
  ],
}

const model = vi.hoisted(() => ({
  plan: undefined as unknown as SyncPlan,
  finalize: vi.fn(),
}))
vi.mock('../../data/codes', () => ({ useCodeSet: () => ({ data: CODES }) }))
vi.mock('../model/sync', () => ({
  planChange: () => model.plan,
  finalizePlan: (...args: unknown[]) => model.finalize(...args),
}))
const STATE = { statusKey: 'negotiation', forecastKey: 'commit', revenueAmount: 150000000, revenueDate: '2026-12-31' }

function Harness({ onResult, state = STATE }: { onResult: (v: SyncApplied | null) => void; state?: typeof STATE }) {
  const { request, dialogs } = useSyncedChange(state)
  return (
    <>
      <button type="button" onClick={() => void request({ field: 'statusKey', value: 'contract_completed' }).then(onResult)}>
        요청
      </button>
      {dialogs}
    </>
  )
}

const APPLIED: SyncApplied = {
  patch: { statusKey: 'contract_completed', forecastKey: 'won' },
  revenue: { amount: 200000000, date: '2026-10-15' },
  coChanged: [{ field: 'forecastKey', from: 'commit', to: 'won' }],
  notice: "Status가 '계약완료'로, Forecast가 'Won'으로 함께 변경되었습니다.",
}

function okFinalize(): SyncFinalize {
  return { ok: true, applied: APPLIED }
}

describe('useSyncedChange', () => {
  it('applies an independent change without any dialog', async () => {
    model.plan = { kind: 'independent', patch: { statusKey: 'poc_done' } }
    model.finalize.mockReturnValue({ ok: true, applied: { patch: { statusKey: 'poc_done' }, revenue: null, coChanged: [], notice: null } })
    const onResult = vi.fn()
    render(<Harness onResult={onResult} />)

    await userEvent.click(screen.getByRole('button', { name: '요청' }))

    await waitFor(() => expect(onResult).toHaveBeenCalled())
    expect(screen.queryByRole('dialog')).not.toBeInTheDocument()
    expect(onResult.mock.calls[0]?.[0].patch).toEqual({ statusKey: 'poc_done' })
  })

  describe('revenue dialog', () => {
    const plan: SyncPlan = {
      kind: 'needRevenue',
      patch: { statusKey: 'contract_completed', forecastKey: 'won' },
      notice:
        "Status가 '계약완료'로, Forecast가 'Won'으로 함께 변경됩니다. 실제 매출금액과 매출일을 입력해야 저장할 수 있습니다.",
    }

    it('opens "매출 확정" with prefilled values and confirm enabled only when valid', async () => {
      model.plan = plan
      render(<Harness onResult={() => {}} />)

      await userEvent.click(screen.getByRole('button', { name: '요청' }))

      const dialog = screen.getByRole('dialog', { name: '매출 확정' })
      expect(dialog).toHaveTextContent("Status가 '계약완료'로, Forecast가 'Won'으로 함께 변경됩니다.")
      expect(dialog).toHaveTextContent('실제 매출금액과 매출일을 입력해야 저장할 수 있습니다.')
      const occurrences = (dialog.textContent ?? '').split('실제 매출금액과 매출일을 입력해야 저장할 수 있습니다.').length - 1
      expect(occurrences).toBe(1)
      expect(screen.getByLabelText('매출금액(단위:천원, 실제 값)')).toHaveValue('150,000')
      expect(screen.getByLabelText('매출일(실제 값)')).toHaveValue('2026.12.31')
      expect(screen.getByRole('button', { name: '확정' })).toBeEnabled()
    })

    it('disables confirm and explains until a valid amount and date are entered', async () => {
      model.plan = plan
      render(<Harness onResult={() => {}} />)
      await userEvent.click(screen.getByRole('button', { name: '요청' }))
      await userEvent.clear(screen.getByLabelText('매출금액(단위:천원, 실제 값)'))
      await userEvent.clear(screen.getByLabelText('매출일(실제 값)'))

      expect(screen.getByRole('button', { name: '확정' })).toBeDisabled()
      expect(screen.getByText(AMOUNT_INPUT_MESSAGE)).toBeInTheDocument()
      expect(screen.getByText('매출일을 입력하세요.')).toBeInTheDocument()

      await userEvent.type(screen.getByLabelText('매출금액(단위:천원, 실제 값)'), '0')
      expect(screen.getByRole('button', { name: '확정' })).toBeDisabled()
      await userEvent.clear(screen.getByLabelText('매출금액(단위:천원, 실제 값)'))
      await userEvent.type(screen.getByLabelText('매출금액(단위:천원, 실제 값)'), '200,000')
      await userEvent.type(screen.getByLabelText('매출일(실제 값)'), '2026-10-15')
      expect(screen.getByRole('button', { name: '확정' })).toBeEnabled()
    })

    it('keeps confirm disabled and shows the date message while the revenue date is a wrong text', async () => {
      model.plan = plan
      render(<Harness onResult={() => {}} />)
      await userEvent.click(screen.getByRole('button', { name: '요청' }))
      await userEvent.clear(screen.getByLabelText('매출일(실제 값)'))
      await userEvent.type(screen.getByLabelText('매출일(실제 값)'), '20261340')
      await userEvent.tab()

      expect(screen.getByRole('button', { name: '확정' })).toBeDisabled()
      expect(screen.getByText('없는 날짜입니다.')).toBeVisible()
      expect(model.finalize).not.toHaveBeenCalled()
    })

    it('keeps confirm disabled while the revenue date is partly typed', async () => {
      model.plan = plan
      render(<Harness onResult={() => {}} />)
      await userEvent.click(screen.getByRole('button', { name: '요청' }))
      await userEvent.clear(screen.getByLabelText('매출일(실제 값)'))
      await userEvent.type(screen.getByLabelText('매출일(실제 값)'), '2026.10')

      expect(screen.getByRole('button', { name: '확정' })).toBeDisabled()
    })

    it('finalizes with the ISO date when the revenue date is typed as yyyymmdd', async () => {
      model.plan = plan
      model.finalize.mockReturnValue(okFinalize())
      render(<Harness onResult={() => {}} />)
      await userEvent.click(screen.getByRole('button', { name: '요청' }))
      await userEvent.clear(screen.getByLabelText('매출일(실제 값)'))
      await userEvent.type(screen.getByLabelText('매출일(실제 값)'), '20261015')
      expect(screen.getByLabelText('매출일(실제 값)')).toHaveValue('2026.10.15')

      await userEvent.click(screen.getByRole('button', { name: '확정' }))

      await waitFor(() => expect(model.finalize).toHaveBeenCalled())
      expect(model.finalize).toHaveBeenLastCalledWith(
        expect.anything(),
        plan,
        { revenueAmount: 150000000, revenueDate: '2026-10-15' },
        CODES,
      )
    })

    it('finalizes with the entered values and resolves with the result', async () => {
      model.plan = plan
      model.finalize.mockReturnValue(okFinalize())
      const onResult = vi.fn()
      render(<Harness onResult={onResult} />)
      await userEvent.click(screen.getByRole('button', { name: '요청' }))
      await userEvent.clear(screen.getByLabelText('매출금액(단위:천원, 실제 값)'))
      await userEvent.type(screen.getByLabelText('매출금액(단위:천원, 실제 값)'), '200000')
      await userEvent.clear(screen.getByLabelText('매출일(실제 값)'))
      await userEvent.type(screen.getByLabelText('매출일(실제 값)'), '2026-10-15')

      await userEvent.click(screen.getByRole('button', { name: '확정' }))

      await waitFor(() => expect(onResult).toHaveBeenCalledWith(APPLIED))
      expect(model.finalize).toHaveBeenLastCalledWith(
        expect.objectContaining({ statusKey: 'negotiation' }),
        plan,
        { revenueAmount: 200000000, revenueDate: '2026-10-15' },
        CODES,
      )
      expect(screen.queryByRole('dialog')).not.toBeInTheDocument()
    })

    it('keeps the original won amount when the shown thousands are left as they were', async () => {
      model.plan = plan
      model.finalize.mockReturnValue(okFinalize())
      render(<Harness onResult={() => {}} state={{ ...STATE, revenueAmount: 1_234_567 }} />)
      await userEvent.click(screen.getByRole('button', { name: '요청' }))
      expect(screen.getByLabelText('매출금액(단위:천원, 실제 값)')).toHaveValue('1,235')

      await userEvent.click(screen.getByRole('button', { name: '확정' }))

      await waitFor(() => expect(model.finalize).toHaveBeenCalled())
      expect(model.finalize).toHaveBeenLastCalledWith(
        expect.anything(),
        plan,
        { revenueAmount: 1_234_567, revenueDate: '2026-12-31' },
        CODES,
      )
    })

    it('changes nothing when cancelled', async () => {
      model.plan = plan
      model.finalize.mockReset()
      const onResult = vi.fn()
      render(<Harness onResult={onResult} />)
      await userEvent.click(screen.getByRole('button', { name: '요청' }))

      await userEvent.click(screen.getByRole('button', { name: '취소' }))

      await waitFor(() => expect(onResult).toHaveBeenCalledWith(null))
      expect(model.finalize).not.toHaveBeenCalled()
      expect(screen.queryByRole('dialog')).not.toBeInTheDocument()
    })

    it('shows the finalize failure message and stays open', async () => {
      model.plan = plan
      model.finalize.mockReturnValue({ ok: false, reason: 'revenue', message: '서버 거부 문구' })
      const onResult = vi.fn()
      render(<Harness onResult={onResult} />)
      await userEvent.click(screen.getByRole('button', { name: '요청' }))

      await userEvent.click(screen.getByRole('button', { name: '확정' }))

      expect(await screen.findByRole('alert')).toHaveTextContent('서버 거부 문구')
      expect(onResult).not.toHaveBeenCalled()
    })
  })

  describe('choice dialog', () => {
    it('asks for a Status after leaving Won: disabled until chosen, then applies', async () => {
      model.plan = {
        kind: 'askStatus',
        options: ['poc_done', 'negotiation'],
        defaultKey: null,
        patch: { forecastKey: 'commit' },
        prompt: "Forecast를 'Commit'(으)로 바꾸면 Won 상태가 해제되어 Status를 계약완료로 둘 수 없습니다. 어떤 Status로 바꿀까요?",
      }
      model.finalize.mockReturnValue({
        ok: true,
        applied: { patch: { forecastKey: 'commit', statusKey: 'poc_done' }, revenue: null, coChanged: [], notice: null },
      })
      const onResult = vi.fn()
      render(<Harness onResult={onResult} />)
      await userEvent.click(screen.getByRole('button', { name: '요청' }))

      const dialog = screen.getByRole('dialog', { name: '함께 바꿀 값 선택' })
      expect(dialog).toHaveTextContent('어떤 Status로 바꿀까요?')
      expect(screen.getByRole('button', { name: '확인' })).toBeDisabled()
      expect(screen.getAllByRole('radio').map((r) => r.parentElement?.textContent)).toEqual(['POC완료', '가격협상'])

      await userEvent.click(screen.getByRole('radio', { name: 'POC완료' }))
      expect(screen.getByRole('button', { name: '확인' })).toBeEnabled()
      await userEvent.click(screen.getByRole('button', { name: '확인' }))

      await waitFor(() => expect(onResult).toHaveBeenCalled())
      expect(model.finalize).toHaveBeenLastCalledWith(expect.anything(), model.plan, { statusKey: 'poc_done' }, CODES)
    })

    it('preselects the default and labels with Forecast names for askForecast', async () => {
      model.plan = {
        kind: 'askStatus',
        options: ['poc_done', 'negotiation'],
        defaultKey: 'negotiation',
        patch: { forecastKey: 'commit' },
        prompt: 'p',
      }
      render(<Harness onResult={() => {}} />)
      await userEvent.click(screen.getByRole('button', { name: '요청' }))

      expect(screen.getByRole('radio', { name: '가격협상' })).toBeChecked()
      expect(screen.getByRole('button', { name: '확인' })).toBeEnabled()
    })

    it('lists Forecast names for askForecast and cancels without change', async () => {
      model.plan = { kind: 'askForecast', options: ['commit'], patch: { statusKey: 'poc_done' }, prompt: '어떤 값으로?' }
      model.finalize.mockReset()
      const onResult = vi.fn()
      render(<Harness onResult={onResult} />)
      await userEvent.click(screen.getByRole('button', { name: '요청' }))

      expect(screen.getByRole('radio', { name: 'Commit' })).not.toBeChecked()
      await userEvent.click(screen.getByRole('button', { name: '취소' }))

      await waitFor(() => expect(onResult).toHaveBeenCalledWith(null))
      expect(model.finalize).not.toHaveBeenCalled()
    })
  })
})

describe('SyncNotice', () => {
  it('shows the changed-together note as status and can be closed', async () => {
    const onClose = vi.fn()
    render(<SyncNotice notice={APPLIED.notice} onClose={onClose} />)

    expect(screen.getByRole('status')).toHaveTextContent("Status가 '계약완료'로, Forecast가 'Won'으로 함께 변경되었습니다.")
    await userEvent.click(screen.getByRole('button', { name: '닫기' }))
    expect(onClose).toHaveBeenCalled()
  })

  it('renders nothing without a note', () => {
    const { container } = render(<SyncNotice notice={null} />)

    expect(container).toBeEmptyDOMElement()
  })

  it('uses the not-yet-saved wording for a form draft', () => {
    render(<SyncNotice notice={APPLIED.notice} draft />)

    expect(screen.getByRole('status')).toHaveTextContent(
      "Status가 '계약완료'로, Forecast가 'Won'으로 함께 변경됩니다. 저장하면 반영됩니다.",
    )
  })
})
