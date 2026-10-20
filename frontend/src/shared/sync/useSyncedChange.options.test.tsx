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
  it('judges from the given state instead of the hook subject', async () => {
    render(<Harness onResult={() => {}} onError={() => {}} from={WON} />)

    await userEvent.click(screen.getByRole('button', { name: '요청' }))

    // Won -> Commit asks which status to keep; against the subject (already Commit) it would be a silent no-op.
    expect(await screen.findByRole('dialog', { name: '함께 바꿀 값 선택' })).toBeVisible()
  })

  it('keeps the old behaviour without options (same value is an independent no-op)', async () => {
    const onResult = vi.fn()
    render(<Harness onResult={onResult} onError={() => {}} />)

    await userEvent.click(screen.getByRole('button', { name: '요청' }))

    await waitFor(() => expect(onResult).toHaveBeenCalled())
    expect(onResult.mock.calls[0]?.[0].patch).toEqual({})
    expect(screen.queryByRole('dialog')).not.toBeInTheDocument()
  })

  it('rejects with the guard message and opens no dialog', async () => {
    const onError = vi.fn()
    const guard = vi.fn(() => '막힌 변경입니다.')
    render(<Harness onResult={() => {}} onError={onError} from={WON} guard={guard} />)

    await userEvent.click(screen.getByRole('button', { name: '요청' }))

    await waitFor(() => expect(onError).toHaveBeenCalledWith('막힌 변경입니다.'))
    expect(screen.queryByRole('dialog')).not.toBeInTheDocument()
    expect(guard).toHaveBeenCalledWith(expect.objectContaining({ kind: 'askStatus' }), WON)
  })

  it('opens the dialog when the guard returns null', async () => {
    render(<Harness onResult={() => {}} onError={() => {}} from={WON} guard={() => null} />)

    await userEvent.click(screen.getByRole('button', { name: '요청' }))

    expect(await screen.findByRole('dialog', { name: '함께 바꿀 값 선택' })).toBeVisible()
  })
})
