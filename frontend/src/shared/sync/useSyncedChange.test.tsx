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
  // 독립 변경은 대화상자 없이 바로 적용된다.
  // 테스트 코드: DD-097
  it('applies an independent change without any dialog', async () => {
    // given: 독립 변경 계획을 돌려주는 모델
    model.plan = { kind: 'independent', patch: { statusKey: 'poc_done' } }
    model.finalize.mockReturnValue({ ok: true, applied: { patch: { statusKey: 'poc_done' }, revenue: null, coChanged: [], notice: null } })
    const onResult = vi.fn()
    render(<Harness onResult={onResult} />)

    // when: 변경을 요청한다
    await userEvent.click(screen.getByRole('button', { name: '요청' }))

    // then: 대화상자가 없고 결과 패치가 전달된다
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

    // '매출 확정' 대화상자는 현재 값으로 채워져 열리고 값이 유효할 때만 확정이 켜진다.
    // 테스트 코드: DD-098
    it('opens "매출 확정" with prefilled values and confirm enabled only when valid', async () => {
      // given: 종결 계획과 현재 금액·Expected Close
      model.plan = plan
      render(<Harness onResult={() => {}} />)

      // when: 변경을 요청한다
      await userEvent.click(screen.getByRole('button', { name: '요청' }))
      const dialog = screen.getByRole('dialog', { name: '매출 확정' })
      // then: 안내 문구와 미리 채운 금액·매출일이 보이고 확정이 켜져 있다
      expect(dialog).toHaveTextContent("Status가 '계약완료'로, Forecast가 'Won'으로 함께 변경됩니다.")
      expect(dialog).toHaveTextContent('실제 매출금액과 매출일을 입력해야 저장할 수 있습니다.')
      const occurrences = (dialog.textContent ?? '').split('실제 매출금액과 매출일을 입력해야 저장할 수 있습니다.').length - 1
      expect(occurrences).toBe(1)
      expect(screen.getByLabelText('매출금액(단위:원, 실제 값)')).toHaveValue('150,000,000')
      expect(screen.getByLabelText('매출일(실제 값)')).toHaveValue('2026.12.31')
      expect(screen.getByRole('button', { name: '확정' })).toBeEnabled()
    })

    // 유효한 금액·날짜가 들어올 때까지 확정이 꺼지고 사유를 안내한다.
    // 테스트 코드: DD-099
    it('disables confirm and explains until a valid amount and date are entered', async () => {
      // given: 빈 금액·날짜의 매출 확정 대화상자
      model.plan = plan
      render(<Harness onResult={() => {}} />)
      // when: 금액과 매출일을 비운다
      await userEvent.click(screen.getByRole('button', { name: '요청' }))
      await userEvent.clear(screen.getByLabelText('매출금액(단위:원, 실제 값)'))
      await userEvent.clear(screen.getByLabelText('매출일(실제 값)'))
      // then: 확정이 꺼지고 안내가 보인다
      expect(screen.getByRole('button', { name: '확정' })).toBeDisabled()
      expect(screen.getByText(AMOUNT_INPUT_MESSAGE)).toBeInTheDocument()
      expect(screen.getByText('매출일을 입력하세요.')).toBeInTheDocument()

      // when: 금액 0을 입력한다
      await userEvent.type(screen.getByLabelText('매출금액(단위:원, 실제 값)'), '0')
      // then: 확정이 계속 꺼져 있다
      expect(screen.getByRole('button', { name: '확정' })).toBeDisabled()
      // when: 유효한 금액·날짜를 입력한다
      await userEvent.clear(screen.getByLabelText('매출금액(단위:원, 실제 값)'))
      await userEvent.type(screen.getByLabelText('매출금액(단위:원, 실제 값)'), '200,000,000')
      await userEvent.type(screen.getByLabelText('매출일(실제 값)'), '2026-10-15')
      // then: 확정이 켜진다
      expect(screen.getByRole('button', { name: '확정' })).toBeEnabled()
    })

    // 매출일이 틀린 날짜이면 확정이 꺼지고 날짜 문구가 보인다.
    // 테스트 코드: DD-099
    it('keeps confirm disabled and shows the date message while the revenue date is a wrong text', async () => {
      // given: 매출 확정 대화상자
      model.plan = plan
      render(<Harness onResult={() => {}} />)
      // when: 매출일에 '20261340'을 입력한다
      await userEvent.click(screen.getByRole('button', { name: '요청' }))
      await userEvent.clear(screen.getByLabelText('매출일(실제 값)'))
      await userEvent.type(screen.getByLabelText('매출일(실제 값)'), '20261340')
      await userEvent.tab()

      // then: 확정이 꺼지고 '없는 날짜입니다.'가 보이며 확정 요청이 없다
      expect(screen.getByRole('button', { name: '확정' })).toBeDisabled()
      expect(screen.getByText('없는 날짜입니다.')).toBeVisible()
      expect(model.finalize).not.toHaveBeenCalled()
    })

    // 매출일을 덜 쳤으면 확정이 꺼져 있다.
    // 테스트 코드: DD-099
    it('keeps confirm disabled while the revenue date is partly typed', async () => {
      // given: 매출 확정 대화상자
      model.plan = plan
      render(<Harness onResult={() => {}} />)
      // when: 매출일에 '2026.10'까지만 입력한다
      await userEvent.click(screen.getByRole('button', { name: '요청' }))
      await userEvent.clear(screen.getByLabelText('매출일(실제 값)'))
      await userEvent.type(screen.getByLabelText('매출일(실제 값)'), '2026.10')

      // then: 확정이 꺼져 있다
      expect(screen.getByRole('button', { name: '확정' })).toBeDisabled()
    })

    // 매출일을 yyyymmdd로 치면 점 구분으로 보이고 ISO 날짜로 확정한다.
    // 테스트 코드: DD-098
    it('finalizes with the ISO date when the revenue date is typed as yyyymmdd', async () => {
      // given: 매출 확정 대화상자
      model.plan = plan
      model.finalize.mockReturnValue(okFinalize())
      render(<Harness onResult={() => {}} />)
      // when: 매출일에 '20261015'를 입력한다
      await userEvent.click(screen.getByRole('button', { name: '요청' }))
      await userEvent.clear(screen.getByLabelText('매출일(실제 값)'))
      await userEvent.type(screen.getByLabelText('매출일(실제 값)'), '20261015')
      // then: 입력이 2026.10.15로 보인다
      expect(screen.getByLabelText('매출일(실제 값)')).toHaveValue('2026.10.15')

      // when: 확정을 누른다
      await userEvent.click(screen.getByRole('button', { name: '확정' }))
      // then: 확정에 2026-10-15가 전달된다
      await waitFor(() => expect(model.finalize).toHaveBeenCalled())
      expect(model.finalize).toHaveBeenLastCalledWith(
        expect.anything(),
        plan,
        { revenueAmount: 150000000, revenueDate: '2026-10-15' },
        CODES,
      )
    })

    // 입력한 값으로 확정하고 결과를 돌려준다.
    // 테스트 코드: DD-098
    it('finalizes with the entered values and resolves with the result', async () => {
      // given: 매출 확정 대화상자
      model.plan = plan
      model.finalize.mockReturnValue(okFinalize())
      const onResult = vi.fn()
      render(<Harness onResult={onResult} />)
      // when: 금액·매출일을 입력하고 확정한다
      await userEvent.click(screen.getByRole('button', { name: '요청' }))
      await userEvent.clear(screen.getByLabelText('매출금액(단위:원, 실제 값)'))
      await userEvent.type(screen.getByLabelText('매출금액(단위:원, 실제 값)'), '200000000')
      await userEvent.clear(screen.getByLabelText('매출일(실제 값)'))
      await userEvent.type(screen.getByLabelText('매출일(실제 값)'), '2026-10-15')
      // when: 확정을 누른다
      await userEvent.click(screen.getByRole('button', { name: '확정' }))

      // then: 확정 함수가 입력 값으로 불리고 결과가 전달되며 대화상자가 닫힌다
      await waitFor(() => expect(onResult).toHaveBeenCalledWith(APPLIED))
      expect(model.finalize).toHaveBeenLastCalledWith(
        expect.objectContaining({ statusKey: 'negotiation' }),
        plan,
        { revenueAmount: 200000000, revenueDate: '2026-10-15' },
        CODES,
      )
      expect(screen.queryByRole('dialog')).not.toBeInTheDocument()
    })

    // 금액은 정확한 원 값으로 시작하고 그대로 확정하면 그 값이 전달된다.
    // 테스트 코드: DD-099
    it('starts with the exact won value and keeps it when confirmed as is', async () => {
      // given: 금액 1,234,567원의 매출 확정 대화상자
      model.plan = plan
      model.finalize.mockReturnValue(okFinalize())
      render(<Harness onResult={() => {}} state={{ ...STATE, revenueAmount: 1_234_567 }} />)
      // when: 변경을 요청한다
      await userEvent.click(screen.getByRole('button', { name: '요청' }))
      // then: 입력이 '1,234,567'이다
      expect(screen.getByLabelText('매출금액(단위:원, 실제 값)')).toHaveValue('1,234,567')

      // when: 그대로 확정한다
      await userEvent.click(screen.getByRole('button', { name: '확정' }))
      // then: 확정에 같은 금액이 전달된다
      await waitFor(() => expect(model.finalize).toHaveBeenCalled())
      expect(model.finalize).toHaveBeenLastCalledWith(
        expect.anything(),
        plan,
        { revenueAmount: 1_234_567, revenueDate: '2026-12-31' },
        CODES,
      )
    })

    // 취소하면 아무것도 바꾸지 않는다.
    // 테스트 코드: DD-099
    it('changes nothing when cancelled', async () => {
      // given: 매출 확정 대화상자
      model.plan = plan
      model.finalize.mockReset()
      const onResult = vi.fn()
      render(<Harness onResult={onResult} />)
      await userEvent.click(screen.getByRole('button', { name: '요청' }))

      // when: '취소'를 누른다
      await userEvent.click(screen.getByRole('button', { name: '취소' }))

      // then: 결과는 null이고 확정 요청이 없으며 대화상자가 닫힌다
      await waitFor(() => expect(onResult).toHaveBeenCalledWith(null))
      expect(model.finalize).not.toHaveBeenCalled()
      expect(screen.queryByRole('dialog')).not.toBeInTheDocument()
    })

    // 확정이 실패하면 서버 문구를 보이고 대화상자를 유지한다.
    // 테스트 코드: DD-098
    it('shows the finalize failure message and stays open', async () => {
      // given: 확정이 실패하도록 한 모델
      model.plan = plan
      model.finalize.mockReturnValue({ ok: false, reason: 'revenue', message: '서버 거부 문구' })
      const onResult = vi.fn()
      render(<Harness onResult={onResult} />)
      await userEvent.click(screen.getByRole('button', { name: '요청' }))

      // when: 확정을 누른다
      await userEvent.click(screen.getByRole('button', { name: '확정' }))

      // then: 오류 문구가 보이고 결과 전달이 없다
      expect(await screen.findByRole('alert')).toHaveTextContent('서버 거부 문구')
      expect(onResult).not.toHaveBeenCalled()
    })
  })

  describe('choice dialog', () => {
    // Won 이탈 시 Status를 묻고 고르기 전에는 확인이 꺼져 있으며 고르면 적용된다.
    // 테스트 코드: DD-100
    it('asks for a Status after leaving Won: disabled until chosen, then applies', async () => {
      // given: Status 선택 계획
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

      // when: 변경을 요청한다
      await userEvent.click(screen.getByRole('button', { name: '요청' }))
      const dialog = screen.getByRole('dialog', { name: '함께 바꿀 값 선택' })
      // then: 안내 문구와 선택지가 보이고 확인이 꺼져 있다
      expect(dialog).toHaveTextContent('어떤 Status로 바꿀까요?')
      expect(screen.getByRole('button', { name: '확인' })).toBeDisabled()
      expect(screen.getAllByRole('radio').map((r) => r.parentElement?.textContent)).toEqual(['POC완료', '가격협상'])

      // when: POC완료를 골라 확인한다
      await userEvent.click(screen.getByRole('radio', { name: 'POC완료' }))
      // then: 확인이 켜진다
      expect(screen.getByRole('button', { name: '확인' })).toBeEnabled()
      // when: 확인을 누른다
      await userEvent.click(screen.getByRole('button', { name: '확인' }))
      // then: 선택이 확정에 전달된다
      await waitFor(() => expect(onResult).toHaveBeenCalled())
      expect(model.finalize).toHaveBeenLastCalledWith(expect.anything(), model.plan, { statusKey: 'poc_done' }, CODES)
    })

    // Forecast 선택 계획에서 기본값이 미리 골라져 있다.
    // 테스트 코드: DD-102
    it('preselects the default and labels with Forecast names for askForecast', async () => {
      // given: 기본값이 있는 선택 계획
      model.plan = {
        kind: 'askStatus',
        options: ['poc_done', 'negotiation'],
        defaultKey: 'negotiation',
        patch: { forecastKey: 'commit' },
        prompt: 'p',
      }
      render(<Harness onResult={() => {}} />)
      // when: 변경을 요청한다
      await userEvent.click(screen.getByRole('button', { name: '요청' }))

      // then: 기본 선택지가 골라져 있고 확인이 켜져 있다
      expect(screen.getByRole('radio', { name: '가격협상' })).toBeChecked()
      expect(screen.getByRole('button', { name: '확인' })).toBeEnabled()
    })

    // Forecast 선택 계획은 Forecast 이름을 보이고 취소하면 바뀌지 않는다.
    // 테스트 코드: DD-101
    it('lists Forecast names for askForecast and cancels without change', async () => {
      // given: Forecast 선택 계획
      model.plan = { kind: 'askForecast', options: ['commit'], patch: { statusKey: 'poc_done' }, prompt: '어떤 값으로?' }
      model.finalize.mockReset()
      const onResult = vi.fn()
      render(<Harness onResult={onResult} />)
      // when: 변경을 요청한다
      await userEvent.click(screen.getByRole('button', { name: '요청' }))
      // then: Forecast 이름 선택지가 보인다
      expect(screen.getByRole('radio', { name: 'Commit' })).not.toBeChecked()

      // when: 취소를 누른다
      await userEvent.click(screen.getByRole('button', { name: '취소' }))
      // then: 결과는 null이며 확정 요청이 없다
      await waitFor(() => expect(onResult).toHaveBeenCalledWith(null))
      expect(model.finalize).not.toHaveBeenCalled()
    })
  })
})

describe('SyncNotice', () => {
  // 함께 바뀐 값 알림은 상태 영역에 보이고 닫을 수 있다.
  // 테스트 코드: DD-098
  it('shows the changed-together note as status and can be closed', async () => {
    // given: 함께 변경 알림 문구
    const onClose = vi.fn()
    // when: 알림을 그린다
    render(<SyncNotice notice={APPLIED.notice} onClose={onClose} />)
    // then: 문구가 보인다
    expect(screen.getByRole('status')).toHaveTextContent("Status가 '계약완료'로, Forecast가 'Won'으로 함께 변경되었습니다.")
    // when: 닫기를 누른다
    await userEvent.click(screen.getByRole('button', { name: '닫기' }))
    // then: 닫기 콜백이 불린다
    expect(onClose).toHaveBeenCalled()
  })

  // 알림 문구가 없으면 아무것도 그리지 않는다.
  it('renders nothing without a note', () => {
    // when: 알림 컴포넌트를 그린다 (전제: 알림이 없다)
    const { container } = render(<SyncNotice notice={null} />)

    // then: 빈 화면이다
    expect(container).toBeEmptyDOMElement()
  })

  // 폼 초안 모드에서는 '저장하면 반영됩니다' 문구를 쓴다.
  it('uses the not-yet-saved wording for a form draft', () => {
    // when: 알림을 그린다 (전제: 폼 초안 모드)
    render(<SyncNotice notice={APPLIED.notice} draft />)

    // then: 저장 전 문구다
    expect(screen.getByRole('status')).toHaveTextContent(
      "Status가 '계약완료'로, Forecast가 'Won'으로 함께 변경됩니다. 저장하면 반영됩니다.",
    )
  })
})
