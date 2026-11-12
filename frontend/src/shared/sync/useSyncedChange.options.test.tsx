import { render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { describe, expect, it, vi } from 'vitest'
import type { SyncApplied } from '../model/sync'
import { testCodes } from '../model/testing'
import { useSyncedChange } from './useSyncedChange'

vi.mock('../../data/codes', () => ({ useCodeSet: () => ({ data: testCodes() }) }))

const SUBJECT = { statusKey: 'price_negotiation', forecastKey: 'commit' }
const WON = { statusKey: 'contract_completed', forecastKey: 'won' }

interface HarnessProps {
  onResult: (value: SyncApplied | null) => void
  onError: (message: string) => void
  guard?: (plan: { kind: string }, state: { statusKey: string; forecastKey: string }) => string | null
  from?: typeof WON
}

function Harness({ onResult, onError, guard, from }: HarnessProps) {
  const { request, dialogs } = useSyncedChange(SUBJECT)
  const options = from || guard ? { ...(from ? { from } : {}), ...(guard ? { guard } : {}) } : undefined
  return (
    <>
      <button
        type="button"
        onClick={() =>
          void request({ field: 'forecastKey', value: 'commit' }, options as never).then(onResult, (e: Error) => onError(e.message))
        }
      >
        요청
      </button>
      {dialogs}
    </>
  )
}

describe('useSyncedChange request options', () => {
  it('훅의 대상 값이 아니라 넘겨 준 상태를 기준으로 판정한다', async () => {
    // given: Won 상태를 기준으로 하는 요청 버튼 (전제: 훅 대상은 이미 commit)
    render(<Harness onResult={() => {}} onError={() => {}} from={WON} />)

    // when: 요청 버튼을 누른다
    await userEvent.click(screen.getByRole('button', { name: '요청' }))

    // then: Won -> Commit은 유지할 Status를 묻는 창을 연다(대상 기준이면 이미 Commit이라 아무 일도 없었을 것이다)
    expect(await screen.findByRole('dialog', { name: '함께 바꿀 값 선택' })).toBeVisible()
  })

  it('옵션이 없으면 예전 동작을 유지한다(같은 값은 아무 일도 없는 독립 변경이다)', async () => {
    // given: 옵션 없는 요청 버튼
    const onResult = vi.fn()
    render(<Harness onResult={onResult} onError={() => {}} />)

    // when: 요청 버튼을 누른다
    await userEvent.click(screen.getByRole('button', { name: '요청' }))

    // then: 변경 없는 결과가 전달되고 창은 열리지 않는다
    await waitFor(() => expect(onResult).toHaveBeenCalled())
    expect(onResult.mock.calls[0]?.[0].patch).toEqual({})
    expect(screen.queryByRole('dialog')).not.toBeInTheDocument()
  })

  it('가드가 문구를 돌려주면 그 문구로 거절하고 창을 열지 않는다', async () => {
    // given: 막힌 변경 문구를 돌려주는 가드와 Won 기준 요청 버튼
    const onError = vi.fn()
    const guard = vi.fn(() => '막힌 변경입니다.')
    render(<Harness onResult={() => {}} onError={onError} from={WON} guard={guard} />)

    // when: 요청 버튼을 누른다
    await userEvent.click(screen.getByRole('button', { name: '요청' }))

    // then: 가드 문구로 거절되고 창이 없으며 가드는 Status 선택 계획과 기준 상태를 받았다
    await waitFor(() => expect(onError).toHaveBeenCalledWith('막힌 변경입니다.'))
    expect(screen.queryByRole('dialog')).not.toBeInTheDocument()
    expect(guard).toHaveBeenCalledWith(expect.objectContaining({ kind: 'askStatus' }), WON)
  })

  it('가드가 null을 돌려주면 창을 연다', async () => {
    // given: null을 돌려주는 가드와 Won 기준 요청 버튼
    render(<Harness onResult={() => {}} onError={() => {}} from={WON} guard={() => null} />)

    // when: 요청 버튼을 누른다
    await userEvent.click(screen.getByRole('button', { name: '요청' }))

    // then: 값 선택 창이 열린다
    expect(await screen.findByRole('dialog', { name: '함께 바꿀 값 선택' })).toBeVisible()
  })
})
