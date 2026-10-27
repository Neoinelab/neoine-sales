import { describe, expect, it } from 'vitest'
import { reportTimeout } from '../errors'
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
