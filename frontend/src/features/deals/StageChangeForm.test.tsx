import { screen, waitFor, within, fireEvent } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { describe, expect, it, vi } from 'vitest'
import { DETAIL_DEAL } from '../../test/dealFixtures'
import { mockApi, problem, renderApp } from '../../test/utils'
import type { Deal } from './hooks'
import { StageChangeForm } from './StageChangeForm'
import { DEAL_STAGES, STAGE_LABEL } from './stages'

const deal: Deal = DETAIL_DEAL
const PLACEHOLDER = '선택하세요'
const STAGE_URL = 'POST /api/v1/deals/d-1/stage'
const posts = (requests: ReturnType<typeof mockApi>) => requests.filter((r) => r.method === 'POST')

describe('StageChangeForm', () => {
  it('offers every stage except the current one, in Korean and in pipeline order', () => {
    mockApi({})

    renderApp(<StageChangeForm deal={deal} />)

    const [placeholder, ...options] = within(screen.getByLabelText('변경할 단계')).getAllByRole('option')
    const expected = DEAL_STAGES.filter((s) => s !== deal.stage).map((s) => STAGE_LABEL[s])
    expect(expected).toHaveLength(7)
    expect(placeholder).toHaveTextContent(PLACEHOLDER)
    expect(placeholder).toHaveValue('')
    expect(options.map((o) => o.textContent)).toEqual(expected)
    expect(options.map((o) => o.getAttribute('value'))).toEqual(DEAL_STAGES.filter((s) => s !== deal.stage))
    expect(screen.queryByRole('option', { name: '기회발굴' })).not.toBeInTheDocument()
  })

  it('excludes whichever stage is current, including lost', () => {
    mockApi({})

    renderApp(<StageChangeForm deal={{ ...deal, stage: 'lost' }} />)

    const options = within(screen.getByLabelText('변경할 단계'))
      .getAllByRole('option')
      .filter((o) => o.getAttribute('value') !== '')
    expect(options).toHaveLength(7)
    expect(screen.queryByRole('option', { name: '실주' })).not.toBeInTheDocument()
    expect(screen.getByRole('option', { name: '기회발굴' })).toBeInTheDocument()
  })

  it('posts the selected stage and reason to the stage endpoint', async () => {
    const requests = mockApi({ [STAGE_URL]: { body: { ...DETAIL_DEAL, stage: 'price_negotiation' } } })
    renderApp(<StageChangeForm deal={deal} />)

    await userEvent.selectOptions(screen.getByLabelText('변경할 단계'), 'price_negotiation')
    await userEvent.type(screen.getByLabelText('사유'), '견적 제출 완료')
    await userEvent.click(screen.getByRole('button', { name: '단계 변경' }))

    await waitFor(() => expect(posts(requests)).toHaveLength(1))
    expect(posts(requests)[0]!.path).toBe('/api/v1/deals/d-1/stage')
    expect(posts(requests)[0]!.body).toEqual({ stage: 'price_negotiation', reason: '견적 제출 완료' })
  })

  it('treats the reason as an optional memo when the stage is not lost', async () => {
    const requests = mockApi({ [STAGE_URL]: { body: { ...DETAIL_DEAL, stage: 'introduction' } } })
    renderApp(<StageChangeForm deal={deal} />)

    await userEvent.selectOptions(screen.getByLabelText('변경할 단계'), 'introduction')
    expect(screen.getByLabelText('사유')).not.toBeRequired()
    await userEvent.click(screen.getByRole('button', { name: '단계 변경' }))

    await waitFor(() => expect(posts(requests)).toHaveLength(1))
    const body = posts(requests)[0]!.body as { stage: string; reason?: string | null }
    expect(body.stage).toBe('introduction')
    expect(body.reason ?? null).toBeNull()
  })

  it('marks the reason as required when lost is selected', async () => {
    mockApi({})
    renderApp(<StageChangeForm deal={deal} />)

    await userEvent.selectOptions(screen.getByLabelText('변경할 단계'), 'lost')

    expect(screen.getByLabelText('실주 사유(필수)')).toBeRequired()
    expect(screen.queryByLabelText('사유')).not.toBeInTheDocument()
  })

  it('requires a reason for lost before sending', async () => {
    const requests = mockApi({ [STAGE_URL]: { body: { ...DETAIL_DEAL, stage: 'lost' } } })
    renderApp(<StageChangeForm deal={deal} />)
    await userEvent.selectOptions(screen.getByLabelText('변경할 단계'), 'lost')

    await userEvent.click(screen.getByRole('button', { name: '단계 변경' }))

    expect(posts(requests)).toHaveLength(0)
  })

  it('rejects a whitespace-only lost reason with guidance and sends nothing', async () => {
    const requests = mockApi({ [STAGE_URL]: { body: { ...DETAIL_DEAL, stage: 'lost' } } })
    renderApp(<StageChangeForm deal={deal} />)
    await userEvent.selectOptions(screen.getByLabelText('변경할 단계'), 'lost')
    await userEvent.type(screen.getByLabelText('실주 사유(필수)'), '   ')

    await userEvent.click(screen.getByRole('button', { name: '단계 변경' }))

    expect(await screen.findByRole('alert')).toHaveTextContent('실주 사유')
    expect(posts(requests)).toHaveLength(0)
  })

  it('sends lost with the reason once it is filled in', async () => {
    const requests = mockApi({ [STAGE_URL]: { body: { ...DETAIL_DEAL, stage: 'lost' } } })
    renderApp(<StageChangeForm deal={deal} />)
    await userEvent.selectOptions(screen.getByLabelText('변경할 단계'), 'lost')

    await userEvent.type(screen.getByLabelText('실주 사유(필수)'), '예산 부족')
    await userEvent.click(screen.getByRole('button', { name: '단계 변경' }))

    await waitFor(() => expect(posts(requests)).toHaveLength(1))
    expect(posts(requests)[0]!.body).toEqual({ stage: 'lost', reason: '예산 부족' })
  })

  it('accepts a lost reason of exactly 500 characters', async () => {
    const requests = mockApi({ [STAGE_URL]: { body: { ...DETAIL_DEAL, stage: 'lost' } } })
    renderApp(<StageChangeForm deal={deal} />)
    await userEvent.selectOptions(screen.getByLabelText('변경할 단계'), 'lost')

    fireEvent.change(screen.getByLabelText('실주 사유(필수)'), { target: { value: '가'.repeat(500) } })
    await userEvent.click(screen.getByRole('button', { name: '단계 변경' }))

    await waitFor(() => expect(posts(requests)).toHaveLength(1))
    expect((posts(requests)[0]!.body as { reason: string }).reason).toHaveLength(500)
  })

  it('rejects a reason longer than 500 characters with guidance and sends nothing', async () => {
    const requests = mockApi({ [STAGE_URL]: { body: { ...DETAIL_DEAL, stage: 'lost' } } })
    renderApp(<StageChangeForm deal={deal} />)
    await userEvent.selectOptions(screen.getByLabelText('변경할 단계'), 'lost')

    fireEvent.change(screen.getByLabelText('실주 사유(필수)'), { target: { value: '가'.repeat(501) } })
    await userEvent.click(screen.getByRole('button', { name: '단계 변경' }))

    expect(await screen.findByRole('alert')).toHaveTextContent('500')
    expect(posts(requests)).toHaveLength(0)
  })

  it('shows a 409 when the stage did not change', async () => {
    mockApi({ [STAGE_URL]: problem(409, 'invalid-state', '이미 같은 단계입니다') })
    renderApp(<StageChangeForm deal={deal} />)
    await userEvent.selectOptions(screen.getByLabelText('변경할 단계'), 'introduction')

    await userEvent.click(screen.getByRole('button', { name: '단계 변경' }))

    expect(await screen.findByRole('alert')).toHaveTextContent('이미 같은 단계입니다')
  })

  it('shows a 422 from the server as an error banner', async () => {
    mockApi({ [STAGE_URL]: problem(422, 'invalid-value', '실주 사유가 필요합니다') })
    renderApp(<StageChangeForm deal={deal} />)
    await userEvent.selectOptions(screen.getByLabelText('변경할 단계'), 'lost')
    await userEvent.type(screen.getByLabelText('실주 사유(필수)'), '사유')

    await userEvent.click(screen.getByRole('button', { name: '단계 변경' }))

    expect(await screen.findByRole('alert')).toHaveTextContent('실주 사유가 필요합니다')
  })

  it('starts with no stage chosen and keeps the submit button disabled', () => {
    mockApi({})

    renderApp(<StageChangeForm deal={deal} />)

    expect(screen.getByLabelText('변경할 단계')).toHaveValue('')
    expect(screen.getByRole('button', { name: '단계 변경' })).toBeDisabled()
  })

  it('does not change the stage when Enter is pressed in the reason field without choosing one', async () => {
    const requests = mockApi({ [STAGE_URL]: { body: { ...DETAIL_DEAL, stage: 'introduction' } } })
    renderApp(<StageChangeForm deal={deal} />)

    await userEvent.type(screen.getByLabelText('사유'), '메모{Enter}')

    expect(posts(requests)).toHaveLength(0)
  })

  it('sends nothing when the placeholder is chosen again after a stage', async () => {
    const requests = mockApi({ [STAGE_URL]: { body: { ...DETAIL_DEAL, stage: 'introduction' } } })
    renderApp(<StageChangeForm deal={deal} />)
    await userEvent.selectOptions(screen.getByLabelText('변경할 단계'), 'introduction')

    await userEvent.selectOptions(screen.getByLabelText('변경할 단계'), '')
    await userEvent.type(screen.getByLabelText('사유'), '{Enter}')

    expect(screen.getByRole('button', { name: '단계 변경' })).toBeDisabled()
    expect(posts(requests)).toHaveLength(0)
  })

  it('disables the submit button while the request is in flight so it cannot be sent twice', async () => {
    const requests = mockApi({ [STAGE_URL]: { body: { ...DETAIL_DEAL, stage: 'introduction' } } })
    const fastFetch = globalThis.fetch
    let release: () => void = () => {}
    const gate = new Promise<void>((resolve) => {
      release = resolve
    })
    vi.stubGlobal(
      'fetch',
      vi.fn(async (input: Request) => {
        if (input.method === 'POST') await gate
        return fastFetch(input)
      }),
    )
    renderApp(<StageChangeForm deal={deal} />)
    await userEvent.selectOptions(screen.getByLabelText('변경할 단계'), 'introduction')
    const button = screen.getByRole('button', { name: '단계 변경' })

    await userEvent.click(button)
    await waitFor(() => expect(button).toBeDisabled())
    await userEvent.click(button)
    release()

    await waitFor(() => expect(posts(requests)).toHaveLength(1))
  })
})
