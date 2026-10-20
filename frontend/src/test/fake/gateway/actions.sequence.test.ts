import { describe, expect, it } from 'vitest'
import { SYNC_CONFLICT_MESSAGE } from '../../../shared/model/sync'
import type { ActionInput, StatusChangeRequest } from '../../../shared/model/types'
import { dealCode, expectApiError, mockAs } from '../testing'

const CLOSING = { revenueAmount: 1_800_000_000, revenueDate: '2026-10-15' }
const INVALID_FORM = '요청 형식이 올바르지 않습니다'

const input = (statusChanges?: StatusChangeRequest[]): ActionInput => ({
  type: { name: '미팅' },
  progress: '고객사 방문',
  nextAction: '견적 재전달',
  dueDate: '2026-10-22',
  memo: '',
  ...(statusChanges ? { statusChanges } : {}),
})

const status = (value: string, resolution?: StatusChangeRequest['resolution']): StatusChangeRequest => ({
  change: { field: 'statusKey', value },
  ...(resolution ? { resolution } : {}),
})
const forecast = (value: string, resolution?: StatusChangeRequest['resolution']): StatusChangeRequest => ({
  change: { field: 'forecastKey', value },
  ...(resolution ? { resolution } : {}),
})

async function snapshot(gateway: Awaited<ReturnType<typeof mockAs>>['gateway'], code: string) {
  const deal = await gateway.deals.get(code)
  return {
    sync: [deal.statusKey, deal.forecastKey],
    actions: (await gateway.actions.list(code, {})).length,
    history: (await gateway.history.list(code, {})).length,
  }
}

describe('actions.create with statusChanges (two changes)', () => {
  it('applies both changes, stores the post-change values and logs them in order before the action', async () => {
    const { gateway } = await mockAs('kim')
    const code = dealCode(1)

    const created = await gateway.actions.create(code, input([status('introduction'), forecast('best')]))

    expect(created).toMatchObject({ statusKey: 'introduction', forecastKey: 'best' })
    const deal = await gateway.deals.get(code)
    expect([deal.statusKey, deal.forecastKey]).toEqual(['introduction', 'best'])
    const newestFirst = (await gateway.history.list(code, {})).slice(0, 3).map((h) => h.category)
    expect(newestFirst).toEqual(['action', 'forecast', 'status'])
  })

  it('judges the second change after the first (reopen a won deal, then move the status)', async () => {
    const { gateway } = await mockAs('kim')
    const code = dealCode(11)

    const created = await gateway.actions.create(
      code,
      input([forecast('commit', { statusKey: 'poc_completed' }), status('introduction')]),
    )

    expect(created).toMatchObject({ statusKey: 'introduction', forecastKey: 'commit' })
  })

  it('rejects a second change that overrides the first and stores nothing', async () => {
    const { gateway } = await mockAs('kim')
    const code = dealCode(1)
    const before = await snapshot(gateway, code)

    await expectApiError(
      gateway.actions.create(code, input([status('introduction'), forecast('won', CLOSING)])),
      422,
      SYNC_CONFLICT_MESSAGE,
    )

    expect(await snapshot(gateway, code)).toEqual(before)
  })

  it('does not keep the first change when the second one fails', async () => {
    const { gateway } = await mockAs('kim')
    const code = dealCode(16) // price_negotiation / lost
    const before = await snapshot(gateway, code)

    await expectApiError(
      gateway.actions.create(code, input([status('introduction'), forecast('commit')])),
      422,
      '함께 바꿀 값을 선택하세요.',
    )

    expect(await snapshot(gateway, code)).toEqual(before)
  })

  it('checks that every code exists before judging revenue (unknown code wins over a missing revenue)', async () => {
    const { gateway } = await mockAs('kim')
    const code = dealCode(1)
    const before = await snapshot(gateway, code)

    await expectApiError(
      gateway.actions.create(code, input([status('contract_completed'), forecast('no_such_forecast')])),
      422,
      '존재하지 않는 코드입니다.',
    )

    expect(await snapshot(gateway, code)).toEqual(before)
  })

  it.each([
    ['the same field twice', [status('introduction'), status('poc_completed')]],
    ['three changes', [status('introduction'), forecast('best'), status('poc_completed')]],
  ])('rejects %s as a malformed request', async (_name, changes) => {
    const { gateway } = await mockAs('kim')
    const code = dealCode(1)
    const before = await snapshot(gateway, code)

    await expectApiError(gateway.actions.create(code, input(changes)), 422, INVALID_FORM)

    expect(await snapshot(gateway, code)).toEqual(before)
  })

  it('rejects a malformed list as a request error before looking up the deal (like server request validation)', async () => {
    const { gateway } = await mockAs('kim')

    await expectApiError(
      gateway.actions.create('NO-SUCH-DEAL', input([status('introduction'), status('proposal')])),
      422,
      INVALID_FORM,
    )
  })

  it('treats an empty list as no change', async () => {
    const { gateway } = await mockAs('kim')
    const code = dealCode(1)

    const created = await gateway.actions.create(code, input([]))

    expect(created).toMatchObject({ statusKey: 'price_negotiation', forecastKey: 'commit' })
  })
})
