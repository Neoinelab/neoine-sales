import { describe, expect, it } from 'vitest'
import { forbidden, reportTimeout } from '../errors'
import { USER_ID } from '../seed/ids'
import { expectApiError, mockAs } from '../testing'
import { BROKEN_DEFINITION, MINE_PRIVATE, MINE_PUBLIC, OLD_PUBLIC, PARK_PRIVATE, PARK_PUBLIC, SAVED_SAMPLES, VENDOR_DEFINITION, reportInput, savedReport } from '../../savedReports'

/** 저장 리포트 Fake 자체의 규칙(계약 스위트가 다루지 않는 시드·제어 도구·기록). */

describe('saved reports Fake', () => {
  it('starts without saved reports', async () => {
    const { gateway } = await mockAs('kim')

    expect(await gateway.reports.list()).toEqual([])
  })

  it('serves the seeded reports to the viewer in last-change order and hides the private one of someone else', async () => {
    const { gateway, control } = await mockAs('kim')
    control.seedSavedReports(SAVED_SAMPLES)

    const list = await gateway.reports.list()

    expect(list.map((r) => r.id)).toEqual([PARK_PUBLIC.id, MINE_PUBLIC.id, MINE_PRIVATE.id, OLD_PUBLIC.id])
    expect(list.map((r) => r.id)).not.toContain(PARK_PRIVATE.id)
  })

  it('does not put the detail fields in the list items', async () => {
    const { gateway, control } = await mockAs('kim')
    control.seedSavedReports(SAVED_SAMPLES)

    const [first] = await gateway.reports.list()

    expect(first).not.toHaveProperty('definition')
    expect(first).not.toHaveProperty('revision')
    expect(first).not.toHaveProperty('generatedSql')
  })

  it('shows a resigned owner as resigned', async () => {
    const { gateway, control } = await mockAs('kim')
    control.seedSavedReports(SAVED_SAMPLES)

    const report = await gateway.reports.get(OLD_PUBLIC.id)

    expect(report.owner).toEqual({ id: USER_ID.old, name: '강퇴사', role: 'sales', status: 'resigned' })
  })

  it('continues the ids after the seeded ones', async () => {
    const { gateway, control } = await mockAs('kim')
    control.seedSavedReports(SAVED_SAMPLES)

    const created = await gateway.reports.create(reportInput())

    expect(created.id).toBe(16)
  })

  it('gives a copy that callers may change without touching the stored report', async () => {
    const { gateway, control } = await mockAs('kim')
    control.seedSavedReports(SAVED_SAMPLES)

    const first = await gateway.reports.get(MINE_PUBLIC.id)
    first.definition.columns.length = 0
    first.name = '바꿈'
    const second = await gateway.reports.get(MINE_PUBLIC.id)

    expect(second.definition.columns).toHaveLength(2)
    expect(second.name).toBe(MINE_PUBLIC.name)
  })

  it('records writes and runs but not reads, and clears them on reset', async () => {
    const { gateway, control } = await mockAs('kim')
    control.seedSavedReports(SAVED_SAMPLES)

    await gateway.reports.list()
    await gateway.reports.get(MINE_PUBLIC.id)
    const created = await gateway.reports.create(reportInput({ name: '기록 시험' }))
    await gateway.reports.update(created.id, { ...reportInput({ name: '기록 시험2' }), revision: 1 })
    await gateway.reports.copy(created.id, { name: '기록 복사', description: '', visibility: 'public' })
    await gateway.reports.run(created.id)
    await gateway.reports.remove(created.id)

    expect(control.savedReportRequests().map((r) => [r.op, r.id])).toEqual([
      ['create', null],
      ['update', created.id],
      ['copy', created.id],
      ['run', created.id],
      ['remove', created.id],
    ])
    expect(control.savedReportRequests()[0]?.body).toMatchObject({ name: '기록 시험', visibility: 'public', definition: VENDOR_DEFINITION })
    expect(control.savedReportRequests()[1]?.body).toMatchObject({ name: '기록 시험2', revision: 1 })

    control.resetData()

    expect(control.savedReportRequests()).toEqual([])
    expect(await gateway.reports.list()).toEqual([])
  })

  it('records a rejected write too so a test can see that a request was sent', async () => {
    const { gateway, control } = await mockAs('kim')
    control.seedSavedReports(SAVED_SAMPLES)

    await expectApiError(gateway.reports.create(reportInput({ name: MINE_PUBLIC.name })), 409)

    expect(control.savedReportRequests().map((r) => r.op)).toEqual(['create'])
  })

  it('keeps run out of the designer query log', async () => {
    const { gateway, control } = await mockAs('kim')
    control.seedSavedReports(SAVED_SAMPLES)

    await gateway.reports.run(MINE_PUBLIC.id)

    expect(control.reportQueries()).toEqual([])
  })

  it('answers a run with the handler the test set and turns a broken stored definition into 422', async () => {
    const { gateway, control } = await mockAs('kim')
    control.seedSavedReports([MINE_PUBLIC, savedReport({ id: 20, name: '깨진 정의', definition: BROKEN_DEFINITION })])

    const broken = await expectApiError(gateway.reports.run(20), 422)
    control.setReportQueryHandler(() => {
      throw reportTimeout()
    })
    const timeout = await expectApiError(gateway.reports.run(MINE_PUBLIC.id), 503)

    expect(broken.kind).toBe('invalid-report')
    expect(broken.problem?.reportErrors?.[0]).toMatchObject({ code: 'unknown-field', location: ['columns', 0, 'field'] })
    expect(timeout.kind).toBe('report-timeout')
  })

  it('rejects a name that another user already uses, including a private report and a different case', async () => {
    const { gateway, control } = await mockAs('kim')
    control.seedSavedReports(SAVED_SAMPLES)

    const publicOfOther = await expectApiError(gateway.reports.create(reportInput({ name: PARK_PUBLIC.name.toUpperCase() })), 409)
    const copyOntoOther = await expectApiError(gateway.reports.copy(MINE_PUBLIC.id, { name: PARK_PUBLIC.name, description: '', visibility: 'public' }), 409)
    const renameOntoOther = await expectApiError(gateway.reports.update(MINE_PRIVATE.id, { ...reportInput({ name: PARK_PUBLIC.name }), revision: 1 }), 409)

    expect([publicOfOther.kind, copyOntoOther.kind, renameOntoOther.kind]).toEqual(['already-exists', 'already-exists', 'already-exists'])
    expect(publicOfOther.message).toBe('같은 이름의 리포트가 이미 있습니다.')
    expect((await gateway.reports.list()).length).toBe(4)
  })

  it('rejects the name of a private report that the viewer cannot see', async () => {
    const { gateway, control } = await mockAs('kim')
    control.seedSavedReports(SAVED_SAMPLES)

    const error = await expectApiError(gateway.reports.create(reportInput({ name: PARK_PRIVATE.name })), 409)

    expect(error.kind).toBe('already-exists')
  })

  it('turns a copy of a source that no longer fits the catalog into 422 and creates nothing', async () => {
    const { gateway, control } = await mockAs('kim')
    control.seedSavedReports([MINE_PUBLIC, savedReport({ id: 20, name: '깨진 정의', definition: BROKEN_DEFINITION })])

    const failed = await expectApiError(gateway.reports.copy(20, { name: '깨진 복사', description: '', visibility: 'public' }), 422)

    expect(failed.kind).toBe('invalid-report')
    expect(failed.problem?.reportErrors?.[0]).toMatchObject({ code: 'unknown-field' })
    expect((await gateway.reports.list()).map((r) => r.id)).toEqual([MINE_PUBLIC.id, 20])
  })

  it('requires a login for every method', async () => {
    const { gateway } = await mockAs(null)

    await expectApiError(gateway.reports.list(), 401)
    await expectApiError(gateway.reports.get(1), 401)
    await expectApiError(gateway.reports.create(reportInput()), 401)
    await expectApiError(gateway.reports.remove(1), 401)
  })

  it('judges the same ownership rule for a user that logs in later', async () => {
    const { gateway, control } = await mockAs('han')
    control.seedSavedReports(SAVED_SAMPLES)

    await expectApiError(gateway.reports.get(MINE_PRIVATE.id), 404)
    await expectApiError(gateway.reports.remove(MINE_PUBLIC.id), 403)
    expect((await gateway.reports.list()).map((r) => r.id)).toEqual([PARK_PUBLIC.id, MINE_PUBLIC.id, OLD_PUBLIC.id])
  })
})

describe('saved reports Fake: result layout (작성/결과 탭 분리)', () => {
  const SIDE = { view: 'chart', order: ['chart', 'table'], arrange: 'side_by_side' } as const
  const TABLE = { view: 'table', order: ['table', 'chart'], arrange: 'stacked' } as const

  it('gives the default layout to a report created without one and keeps the stored one on an update without one', async () => {
    const { gateway, control } = await mockAs('kim')
    control.seedSavedReports([savedReport({ id: 11, layout: SIDE })])

    const kept = await gateway.reports.update(11, { name: '새 이름', description: '', visibility: 'public', definition: VENDOR_DEFINITION, chart: null, revision: 1 } as never)
    const created = await gateway.reports.create({ name: '배치 없는 새 리포트', description: '', visibility: 'public', definition: VENDOR_DEFINITION, chart: null } as never)

    expect(kept.layout).toEqual(SIDE)
    expect(created.layout).toEqual({ view: 'both', order: ['table', 'chart'], arrange: 'stacked' })
  })

  it('copies the layout of the source report', async () => {
    const { gateway, control } = await mockAs('kim')
    control.seedSavedReports([savedReport({ id: 11, layout: SIDE })])

    const copy = await gateway.reports.copy(11, { name: '복사본', description: '', visibility: 'public' })

    expect(copy.layout).toEqual(SIDE)
  })

  it('saves only the layout with the revision rules of the server and records the request', async () => {
    const { gateway, control } = await mockAs('kim')
    control.seedSavedReports([PARK_PUBLIC])

    const saved = await gateway.reports.saveReportLayout(PARK_PUBLIC.id, { layout: SIDE, revision: 1 })
    const stale = await expectApiError(gateway.reports.saveReportLayout(PARK_PUBLIC.id, { layout: TABLE, revision: 1 }), 409)

    expect(saved).toMatchObject({ revision: 2, layout: SIDE, name: PARK_PUBLIC.name, updatedBy: { id: USER_ID.kim } })
    expect(saved.definition).toEqual(PARK_PUBLIC.definition)
    expect(stale.kind).toBe('invalid-state')
    expect(control.savedReportRequests().map((r) => [r.op, r.id])).toEqual([
      ['layout', PARK_PUBLIC.id],
      ['layout', PARK_PUBLIC.id],
    ])
    expect(control.savedReportRequests()[0]?.body).toEqual({ layout: SIDE, revision: 1 })
  })

  it('hides a private report of someone else and rejects a wrong layout value at its location', async () => {
    const { gateway, control } = await mockAs('kim')
    control.seedSavedReports(SAVED_SAMPLES)

    const hidden = await expectApiError(gateway.reports.saveReportLayout(PARK_PRIVATE.id, { layout: SIDE, revision: 1 }), 404)
    const wrong = await expectApiError(gateway.reports.saveReportLayout(MINE_PUBLIC.id, { layout: { ...SIDE, order: ['table', 'table'] } as never, revision: 1 }), 422)

    expect(hidden.message).toBe('리포트를 찾을 수 없습니다.')
    expect(wrong.kind).toBe('invalid-report')
    expect(wrong.problem?.reportErrors?.map((e) => e.location)).toEqual([['layout', 'order']])
  })

  it('holds the response of a layout save at the gate and numbers the attempts', async () => {
    const { gateway, control } = await mockAs('kim')
    control.seedSavedReports([MINE_PUBLIC])
    const attempts: number[] = []
    let release: () => void = () => undefined
    control.setLayoutSaveGate(({ attempt }) => {
      attempts.push(attempt)
      return new Promise<void>((resolve) => (release = resolve))
    })

    const pending = gateway.reports.saveReportLayout(MINE_PUBLIC.id, { layout: SIDE, revision: 1 })
    await Promise.resolve()
    expect(attempts).toEqual([1])
    expect((await gateway.reports.get(MINE_PUBLIC.id)).revision).toBe(1) // 관문을 통과하기 전에는 서버에 반영되지 않는다
    release()
    await pending

    expect((await gateway.reports.get(MINE_PUBLIC.id)).revision).toBe(2)
  })

  it('fails a layout save at the gate without touching the report, and clears the gate on reset', async () => {
    const { gateway, control } = await mockAs('kim')
    control.seedSavedReports([MINE_PUBLIC])
    control.setLayoutSaveGate(() => {
      throw forbidden('안 됨')
    })

    await expectApiError(gateway.reports.saveReportLayout(MINE_PUBLIC.id, { layout: SIDE, revision: 1 }), 403)
    expect(await gateway.reports.get(MINE_PUBLIC.id)).toMatchObject({ revision: 1 })
    control.resetData()
    control.seedSavedReports([MINE_PUBLIC])
    const saved = await gateway.reports.saveReportLayout(MINE_PUBLIC.id, { layout: SIDE, revision: 1 })

    expect(saved.revision).toBe(2)
  })

  it('lets a test play another user saving the report: the revision goes up and the stale layout save is refused', async () => {
    const { gateway, control } = await mockAs('kim')
    control.seedSavedReports([MINE_PUBLIC])

    control.touchSavedReport(MINE_PUBLIC.id, { layout: TABLE })
    const stale = await expectApiError(gateway.reports.saveReportLayout(MINE_PUBLIC.id, { layout: SIDE, revision: 1 }), 409)

    expect(stale.kind).toBe('invalid-state')
    expect(await gateway.reports.get(MINE_PUBLIC.id)).toMatchObject({ revision: 2, layout: TABLE, updatedBy: { name: '박영업' } })
  })
})
