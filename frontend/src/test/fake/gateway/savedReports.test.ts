import { describe, expect, it } from 'vitest'
import { forbidden, reportTimeout } from '../errors'
import { DEFAULT_REPORT_LAYOUT } from './savedReports'
import { USER_ID } from '../seed/ids'
import { expectApiError, mockAs } from '../testing'
import { BROKEN_DEFINITION, brokenStoredReport, MINE_PRIVATE, MINE_PUBLIC, OLD_PUBLIC, PARK_PRIVATE, PARK_PUBLIC, SAVED_SAMPLES, VENDOR_DEFINITION, reportInput, savedReport } from '../../savedReports'

/** 저장 리포트 Fake 자체의 규칙(계약 스위트가 다루지 않는 시드·제어 도구·기록). */

describe('저장 리포트 Fake', () => {
  it('저장한 리포트가 없으면 처음 목록은 비어 있다', async () => {
    // given: 시드가 없는 Fake(김영업 로그인)
    const { gateway } = await mockAs('kim')

    // when: 목록을 읽는다
    const list = await gateway.reports.list()

    // then: 목록이 비어 있다
    expect(list).toEqual([])
  })

  it('시드한 리포트를 최종 수정 순으로 보이고 남의 비공개는 숨긴다', async () => {
    // given: 샘플 리포트 5건을 시드한다
    const { gateway, control } = await mockAs('kim')
    control.seedSavedReports(SAVED_SAMPLES)

    // when: 김영업이 목록을 읽는다
    const list = await gateway.reports.list()

    // then: 최종 수정 시각 내림차순이고 남의 비공개는 없다
    expect(list.map((r) => r.id)).toEqual([PARK_PUBLIC.id, MINE_PUBLIC.id, MINE_PRIVATE.id, OLD_PUBLIC.id])
    expect(list.map((r) => r.id)).not.toContain(PARK_PRIVATE.id)
  })

  it('목록 항목에는 상세 필드가 없다', async () => {
    // given: 샘플 리포트를 시드한다
    const { gateway, control } = await mockAs('kim')
    control.seedSavedReports(SAVED_SAMPLES)

    // when: 목록을 읽는다
    const [first] = await gateway.reports.list()

    // then: 정의·revision·SQL이 없다
    expect(first).not.toHaveProperty('definition')
    expect(first).not.toHaveProperty('revision')
    expect(first).not.toHaveProperty('generatedSql')
  })

  it('퇴사한 만든 사람은 퇴사로 보인다', async () => {
    // given: 퇴사자가 만든 리포트를 시드한다
    const { gateway, control } = await mockAs('kim')
    control.seedSavedReports(SAVED_SAMPLES)

    // when: 상세를 읽는다
    const report = await gateway.reports.get(OLD_PUBLIC.id)

    // then: 만든 사람의 상태가 resigned다
    expect(report.owner).toEqual({ id: USER_ID.old, name: '강퇴사', role: 'sales', status: 'resigned' })
  })

  it('새 리포트 id는 시드한 id 다음부터 이어진다', async () => {
    // given: 마지막 id가 15인 시드
    const { gateway, control } = await mockAs('kim')
    control.seedSavedReports(SAVED_SAMPLES)

    // when: 리포트를 만든다
    const created = await gateway.reports.create(reportInput())

    // then: id가 16이다
    expect(created.id).toBe(16)
  })

  it('읽어 온 값을 바꿔도 저장된 리포트는 바뀌지 않는다', async () => {
    // given: 샘플 리포트를 시드한다
    const { gateway, control } = await mockAs('kim')
    control.seedSavedReports(SAVED_SAMPLES)

    // when: 상세를 읽어 그 값을 고친 뒤 다시 읽는다
    const first = await gateway.reports.get(MINE_PUBLIC.id)
    first.definition.columns.length = 0
    first.name = '바꿈'
    const second = await gateway.reports.get(MINE_PUBLIC.id)

    // then: 저장된 정의와 이름은 그대로다
    expect(second.definition.columns).toHaveLength(2)
    expect(second.name).toBe(MINE_PUBLIC.name)
  })

  it('쓰기와 실행만 요청 기록에 남고 읽기는 남지 않으며 초기화하면 지워진다', async () => {
    // given: 샘플 리포트를 시드한다
    const { gateway, control } = await mockAs('kim')
    control.seedSavedReports(SAVED_SAMPLES)

    // when: 읽기 두 번, 만들기·덮어쓰기·복제·실행·삭제를 차례로 한다
    await gateway.reports.list()
    await gateway.reports.get(MINE_PUBLIC.id)
    const created = await gateway.reports.create(reportInput({ name: '기록 시험' }))
    await gateway.reports.update(created.id, { ...reportInput({ name: '기록 시험2' }), revision: 1 })
    await gateway.reports.copy(created.id, { name: '기록 복사', description: '', visibility: 'public' })
    await gateway.reports.run(created.id)
    await gateway.reports.remove(created.id)

    // then: 쓰기·실행만 순서대로 기록되고 본문이 담긴다
    expect(control.savedReportRequests().map((r) => [r.op, r.id])).toEqual([
      ['create', null],
      ['update', created.id],
      ['copy', created.id],
      ['run', created.id],
      ['remove', created.id],
    ])
    expect(control.savedReportRequests()[0]?.body).toMatchObject({ name: '기록 시험', visibility: 'public', definition: VENDOR_DEFINITION })
    expect(control.savedReportRequests()[1]?.body).toMatchObject({ name: '기록 시험2', revision: 1 })

    // when: 데이터를 초기화한다
    control.resetData()

    // then: 기록과 목록이 비어 있다
    expect(control.savedReportRequests()).toEqual([])
    expect(await gateway.reports.list()).toEqual([])
  })

  it('거절된 쓰기도 기록에 남아 요청을 보냈는지 알 수 있다', async () => {
    // given: 샘플 리포트를 시드한다
    const { gateway, control } = await mockAs('kim')
    control.seedSavedReports(SAVED_SAMPLES)

    // when: 있는 이름으로 만들기를 요청해 409를 받는다
    await expectApiError(gateway.reports.create(reportInput({ name: MINE_PUBLIC.name })), 409)

    // then: 만들기 요청이 기록된다
    expect(control.savedReportRequests().map((r) => r.op)).toEqual(['create'])
  })

  it('저장 리포트 실행은 디자이너 조회 기록에 남지 않는다', async () => {
    // given: 샘플 리포트를 시드한다
    const { gateway, control } = await mockAs('kim')
    control.seedSavedReports(SAVED_SAMPLES)

    // when: 저장 리포트를 실행한다
    await gateway.reports.run(MINE_PUBLIC.id)

    // then: 설계 조회 기록은 비어 있다
    expect(control.reportQueries()).toEqual([])
  })

  it('실행은 테스트가 정한 처리기로 답하고 지금 규칙과 맞지 않는 저장 정의는 422다', async () => {
    // given: 정상 리포트와 지금 카탈로그에 없는 필드를 쓰는 리포트
    const { gateway, control } = await mockAs('kim')
    control.seedSavedReports([MINE_PUBLIC, savedReport({ id: 20, name: '깨진 정의', definition: BROKEN_DEFINITION })])

    // when: 맞지 않는 정의의 리포트를 실행한다
    const broken = await expectApiError(gateway.reports.run(20), 422)
    // given: 조회 처리기가 시간 초과를 던진다
    control.setReportQueryHandler(() => {
      throw reportTimeout()
    })
    // when: 정상 리포트를 실행한다
    const timeout = await expectApiError(gateway.reports.run(MINE_PUBLIC.id), 503)

    // then: 앞은 unknown-field 위반의 422, 뒤는 시간 초과 503이다
    expect(broken.kind).toBe('invalid-report')
    expect(broken.problem?.reportErrors?.[0]).toMatchObject({ code: 'unknown-field', location: ['columns', 0, 'field'] })
    expect(timeout.kind).toBe('report-timeout')
  })

  it('다른 사람이 쓰는 이름은 대소문자가 달라도 만들기·복제·이름 바꾸기 모두 거절한다', async () => {
    // given: 샘플 리포트를 시드한다
    const { gateway, control } = await mockAs('kim')
    control.seedSavedReports(SAVED_SAMPLES)

    // when: 남의 공개 리포트 이름으로 만들고, 복제하고, 덮어써 바꾼다
    const publicOfOther = await expectApiError(gateway.reports.create(reportInput({ name: PARK_PUBLIC.name.toUpperCase() })), 409)
    const copyOntoOther = await expectApiError(gateway.reports.copy(MINE_PUBLIC.id, { name: PARK_PUBLIC.name, description: '', visibility: 'public' }), 409)
    const renameOntoOther = await expectApiError(gateway.reports.update(MINE_PRIVATE.id, { ...reportInput({ name: PARK_PUBLIC.name }), revision: 1 }), 409)

    // then: 모두 409 already-exists 문구이고 리포트 수가 그대로다
    expect([publicOfOther.kind, copyOntoOther.kind, renameOntoOther.kind]).toEqual(['already-exists', 'already-exists', 'already-exists'])
    expect(publicOfOther.message).toBe('같은 이름의 리포트가 이미 있습니다.')
    expect((await gateway.reports.list()).length).toBe(4)
  })

  it('볼 수 없는 남의 비공개 리포트 이름도 거절한다', async () => {
    // given: 박영업의 비공개 리포트가 있는 시드
    const { gateway, control } = await mockAs('kim')
    control.seedSavedReports(SAVED_SAMPLES)

    // when: 그 이름으로 만든다
    const error = await expectApiError(gateway.reports.create(reportInput({ name: PARK_PRIVATE.name })), 409)

    // then: 409 already-exists다
    expect(error.kind).toBe('already-exists')
  })

  it('지금 규칙과 맞지 않는 원본의 복제는 422이고 아무것도 만들지 않는다', async () => {
    // given: 지금 카탈로그에 없는 필드를 쓰는 원본
    const { gateway, control } = await mockAs('kim')
    control.seedSavedReports([MINE_PUBLIC, savedReport({ id: 20, name: '깨진 정의', definition: BROKEN_DEFINITION })])

    // when: 복제한다
    const failed = await expectApiError(gateway.reports.copy(20, { name: '깨진 복사', description: '', visibility: 'public' }), 422)

    // then: 422 unknown-field이고 리포트 목록은 그대로다
    expect(failed.kind).toBe('invalid-report')
    expect(failed.problem?.reportErrors?.[0]).toMatchObject({ code: 'unknown-field' })
    expect((await gateway.reports.list()).map((r) => r.id)).toEqual([MINE_PUBLIC.id, 20])
  })

  it('로그인하지 않으면 모든 메서드가 401이다', async () => {
    // given: 로그인하지 않은 Fake
    const { gateway } = await mockAs(null)

    // when·then: 목록·상세·만들기·삭제가 모두 401이다
    await expectApiError(gateway.reports.list(), 401)
    await expectApiError(gateway.reports.get(1), 401)
    await expectApiError(gateway.reports.create(reportInput()), 401)
    await expectApiError(gateway.reports.remove(1), 401)
  })

  it('나중에 로그인한 사용자에게도 같은 소유 규칙을 적용한다', async () => {
    // given: han으로 로그인하고 샘플을 시드한다
    const { gateway, control } = await mockAs('han')
    control.seedSavedReports(SAVED_SAMPLES)

    // when·then: 남의 비공개 상세는 404, 남의 공개 삭제는 403이다
    await expectApiError(gateway.reports.get(MINE_PRIVATE.id), 404)
    await expectApiError(gateway.reports.remove(MINE_PUBLIC.id), 403)
    // then: 목록은 보이는 리포트만이다
    expect((await gateway.reports.list()).map((r) => r.id)).toEqual([PARK_PUBLIC.id, MINE_PUBLIC.id, OLD_PUBLIC.id])
  })
})

describe('저장 리포트 Fake: 결과 배치', () => {
  const SIDE = { view: 'chart', order: ['chart', 'table'], arrange: 'side_by_side' } as const
  const TABLE = { view: 'table', order: ['table', 'chart'], arrange: 'stacked' } as const

  it('배치 없이 만들면 기본 배치이고 배치 없이 덮어쓰면 저장된 배치가 남는다', async () => {
    // given: 배치가 CHART_SIDE인 리포트
    const { gateway, control } = await mockAs('kim')
    control.seedSavedReports([savedReport({ id: 11, layout: SIDE })])

    // when: 배치 없이 덮어쓴다
    const kept = await gateway.reports.update(11, { name: '새 이름', description: '', visibility: 'public', definition: VENDOR_DEFINITION, chart: null, revision: 1 } as never)
    // when: 배치 없이 만든다
    const created = await gateway.reports.create({ name: '배치 없는 새 리포트', description: '', visibility: 'public', definition: VENDOR_DEFINITION, chart: null } as never)

    // then: 덮어쓴 쪽은 저장된 배치, 만든 쪽은 기본 배치다
    expect(kept.layout).toEqual(SIDE)
    expect(created.layout).toEqual({ view: 'both', order: ['table', 'chart'], arrange: 'stacked' })
  })

  it('복제본은 원본의 배치를 가진다', async () => {
    // given: 배치가 CHART_SIDE인 원본
    const { gateway, control } = await mockAs('kim')
    control.seedSavedReports([savedReport({ id: 11, layout: SIDE })])

    // when: 복제한다
    const copy = await gateway.reports.copy(11, { name: '복사본', description: '', visibility: 'public' })

    // then: 복제본의 배치가 원본과 같다
    expect(copy.layout).toEqual(SIDE)
  })

  it('배치만 저장하면 서버와 같은 revision 규칙을 따르고 요청이 기록된다', async () => {
    // given: 박영업의 공개 리포트
    const { gateway, control } = await mockAs('kim')
    control.seedSavedReports([PARK_PUBLIC])

    // when: revision 1로 배치를 저장하고, 같은 revision으로 다시 저장한다
    const saved = await gateway.reports.saveReportLayout(PARK_PUBLIC.id, { layout: SIDE, revision: 1 })
    const stale = await expectApiError(gateway.reports.saveReportLayout(PARK_PUBLIC.id, { layout: TABLE, revision: 1 }), 409)

    // then: 첫 저장은 revision 2에 정의가 그대로이고 둘째는 409 invalid-state이며 요청 둘이 기록된다
    expect(saved).toMatchObject({ revision: 2, layout: SIDE, name: PARK_PUBLIC.name, updatedBy: { id: USER_ID.kim } })
    expect(saved.definition).toEqual(PARK_PUBLIC.definition)
    expect(stale.kind).toBe('invalid-state')
    expect(control.savedReportRequests().map((r) => [r.op, r.id])).toEqual([
      ['layout', PARK_PUBLIC.id],
      ['layout', PARK_PUBLIC.id],
    ])
    expect(control.savedReportRequests()[0]?.body).toEqual({ layout: SIDE, revision: 1 })
  })

  it('남의 비공개 리포트는 404이고 틀린 배치 값은 위치와 함께 422다', async () => {
    // given: 샘플 리포트를 시드한다
    const { gateway, control } = await mockAs('kim')
    control.seedSavedReports(SAVED_SAMPLES)

    // when: 남의 비공개 리포트와 틀린 배치로 배치를 저장한다
    const hidden = await expectApiError(gateway.reports.saveReportLayout(PARK_PRIVATE.id, { layout: SIDE, revision: 1 }), 404)
    const wrong = await expectApiError(gateway.reports.saveReportLayout(MINE_PUBLIC.id, { layout: { ...SIDE, order: ['table', 'table'] } as never, revision: 1 }), 422)

    // then: 404 문구와 ["layout","order"] 위반의 422다
    expect(hidden.message).toBe('리포트를 찾을 수 없습니다.')
    expect(wrong.kind).toBe('invalid-report')
    expect(wrong.problem?.reportErrors?.map((e) => e.location)).toEqual([['layout', 'order']])
  })

  it('배치 저장 응답을 관문에 잡아 두고 시도 번호를 센다', async () => {
    // given: 응답을 잡아 두는 관문을 설정한다
    const { gateway, control } = await mockAs('kim')
    control.seedSavedReports([MINE_PUBLIC])
    const attempts: number[] = []
    let release: () => void = () => undefined
    control.setLayoutSaveGate(({ attempt }) => {
      attempts.push(attempt)
      return new Promise<void>((resolve) => (release = resolve))
    })

    // when: 배치 저장을 시작한다
    const pending = gateway.reports.saveReportLayout(MINE_PUBLIC.id, { layout: SIDE, revision: 1 })
    await Promise.resolve()
    // then: 첫 시도이고 관문을 통과하기 전에는 서버에 반영되지 않는다
    expect(attempts).toEqual([1])
    expect((await gateway.reports.get(MINE_PUBLIC.id)).revision).toBe(1) // 관문을 통과하기 전에는 서버에 반영되지 않는다
    // when: 관문을 푼다
    release()
    // then: 저장이 끝나고 revision이 2다
    await pending

    expect((await gateway.reports.get(MINE_PUBLIC.id)).revision).toBe(2)
  })

  it('관문에서 실패시킨 배치 저장은 리포트를 건드리지 않고 초기화하면 관문이 사라진다', async () => {
    // given: 403으로 실패하는 관문
    const { gateway, control } = await mockAs('kim')
    control.seedSavedReports([MINE_PUBLIC])
    control.setLayoutSaveGate(() => {
      throw forbidden('안 됨')
    })

    // when·then: 배치 저장이 403이고 리포트는 그대로다
    await expectApiError(gateway.reports.saveReportLayout(MINE_PUBLIC.id, { layout: SIDE, revision: 1 }), 403)
    // then: 리포트는 그대로다
    expect(await gateway.reports.get(MINE_PUBLIC.id)).toMatchObject({ revision: 1 })
    // when: 초기화하고 다시 시드한다
    control.resetData()
    control.seedSavedReports([MINE_PUBLIC])
    // when: 배치를 저장한다
    const saved = await gateway.reports.saveReportLayout(MINE_PUBLIC.id, { layout: SIDE, revision: 1 })

    // then: 관문 없이 저장된다
    expect(saved.revision).toBe(2)
  })

  it('테스트가 다른 사용자의 저장을 흉내 내면 revision이 오르고 낡은 배치 저장은 거절된다', async () => {
    // given: 김영업이 연 리포트
    const { gateway, control } = await mockAs('kim')
    control.seedSavedReports([MINE_PUBLIC])

    // when: 다른 사용자(박영업)가 저장한 것으로 흉내 낸다
    control.touchSavedReport(MINE_PUBLIC.id, { layout: TABLE })
    // when: 낡은 revision 1로 배치를 저장한다
    const stale = await expectApiError(gateway.reports.saveReportLayout(MINE_PUBLIC.id, { layout: SIDE, revision: 1 }), 409)

    // then: 409 invalid-state이고 리포트는 박영업이 저장한 값이다
    expect(stale.kind).toBe('invalid-state')
    expect(await gateway.reports.get(MINE_PUBLIC.id)).toMatchObject({ revision: 2, layout: TABLE, updatedBy: { name: '박영업' } })
  })
})

describe('저장 리포트 Fake: 서버 규칙 맞춤(RS-R47)', () => {
  const BROKEN = brokenStoredReport({ id: 31, name: '읽을 수 없는 정의' })
  const STORED_INVALID = '저장된 리포트 정의를 읽을 수 없습니다.'

  // 테스트 코드: RS-066
  it('저장 정의를 읽을 수 없는 리포트는 목록에 데이터 없이 남고 상세·실행·복제·배치 저장은 422 stored-invalid다', async () => {
    // given: 저장 정의를 읽을 수 없는 내 리포트와 정상 리포트
    const { gateway, control } = await mockAs('kim')
    control.seedSavedReports([MINE_PUBLIC, BROKEN])
    // when: 목록을 읽고, 깨진 리포트의 상세·실행·복제·배치 저장을 한다
    const list = await gateway.reports.list()
    const failures = [
      await expectApiError(gateway.reports.get(BROKEN.id), 422),
      await expectApiError(gateway.reports.run(BROKEN.id), 422),
      await expectApiError(gateway.reports.copy(BROKEN.id, { name: '복사', description: '', visibility: 'public' }), 422),
      await expectApiError(gateway.reports.saveReportLayout(BROKEN.id, { layout: DEFAULT_REPORT_LAYOUT, revision: 1 }), 422),
    ]
    // then: 목록에는 데이터(entities) 없이 남고, 네 요청은 모두 같은 stored-invalid 위반이다
    expect(list.find((r) => r.id === BROKEN.id)?.entities).toEqual([])
    for (const error of failures) {
      expect(error.kind).toBe('invalid-report')
      expect(error.message).toBe(STORED_INVALID)
      expect(error.problem?.reportErrors).toEqual([{ location: ['definition'], code: 'stored-invalid', message: STORED_INVALID }])
    }
    expect((await gateway.reports.list()).map((r) => r.id)).toEqual(list.map((r) => r.id))
  })

  // 테스트 코드: RS-066
  it('남의 비공개 깨진 리포트는 404가 먼저이고 새 정의로 덮어쓰면 복구되며 지울 수도 있다', async () => {
    // given: 박영업의 비공개 깨진 리포트와 내 깨진 리포트
    const { gateway, control } = await mockAs('kim')
    const othersBroken = brokenStoredReport({ id: 32, name: '남의 깨짐', owner: PARK_PUBLIC.owner, visibility: 'private' })
    control.seedSavedReports([BROKEN, othersBroken])
    // when: 남의 비공개 깨진 리포트를 열려 한다
    const hidden = await expectApiError(gateway.reports.get(othersBroken.id), 404)
    // then: stored-invalid가 아니라 찾을 수 없음이다
    expect(hidden.message).toBe('리포트를 찾을 수 없습니다.')
    // when: 내 깨진 리포트를 낡은 revision으로, 이어서 맞는 revision과 새 정의로 덮어쓴다
    const stale = await expectApiError(gateway.reports.update(BROKEN.id, { ...reportInput({ name: '복구됨' }), revision: 2 }), 409)
    const repaired = await gateway.reports.update(BROKEN.id, { ...reportInput({ name: '복구됨' }), revision: 1 })
    // then: 낡은 revision은 거절되고, 맞는 revision이면 복구되어 상세가 열린다
    expect(stale.kind).toBe('invalid-state')
    expect(repaired).toMatchObject({ revision: 2, name: '복구됨' })
    expect(await gateway.reports.get(BROKEN.id)).toMatchObject({ name: '복구됨', definition: VENDOR_DEFINITION })
    // when: 깨진 채로 있는 다른 리포트를 지운다
    control.seedSavedReports([BROKEN])
    await gateway.reports.remove(BROKEN.id)
    // then: 목록에서 사라진다
    expect(await gateway.reports.list()).toEqual([])
  })

  // 테스트 코드: RS-021
  it('덮어쓰기는 404, 422, 403(공개 범위), 409(revision), 409(이름) 순서로 판정한다', async () => {
    // given: 김영업이 볼 수 있는 박영업의 비공개·공개 리포트(revision 4)와 같은 이름의 다른 리포트
    const privateReport = savedReport({ id: 41, name: '비공개 P', visibility: 'private', owner: PARK_PUBLIC.owner, revision: 4 })
    const publicReport = savedReport({ id: 42, name: '공개 R', owner: PARK_PUBLIC.owner, revision: 4 })
    const { gateway, control } = await mockAs('kim')
    control.seedSavedReports([privateReport, publicReport, savedReport({ id: 43, name: '이미 있는 이름', owner: PARK_PUBLIC.owner })])
    // when: 비공개 P를 틀린 정의·낡은 revision으로 덮어쓴다
    const hidden = await expectApiError(gateway.reports.update(41, { ...reportInput({ name: 'P', definition: BROKEN_DEFINITION }), revision: 1 }), 404)
    // then: 404다
    expect(hidden.kind).toBe('not-found')
    // when: 공개 R을 틀린 정의·다른 공개 범위·낡은 revision으로 덮어쓴다
    const invalid = await expectApiError(gateway.reports.update(42, { ...reportInput({ name: 'R', visibility: 'private', definition: BROKEN_DEFINITION }), revision: 1 }), 422)
    // then: 422 정의 위반이다
    expect(invalid.kind).toBe('invalid-report')
    // when: 공개 R을 맞는 정의·다른 공개 범위·낡은 revision으로 덮어쓴다
    const visibility = await expectApiError(gateway.reports.update(42, { ...reportInput({ name: 'R', visibility: 'private' }), revision: 1 }), 403)
    // then: 409가 아니라 공개 범위 403이다
    expect(visibility.message).toBe('공개 범위는 만든 사람 또는 admin만 바꿀 수 있습니다.')
    // when: 같은 공개 범위·낡은 revision·이미 있는 이름으로 덮어쓴다
    const stale = await expectApiError(gateway.reports.update(42, { ...reportInput({ name: '이미 있는 이름' }), revision: 1 }), 409)
    // then: 이름 중복이 아니라 revision 충돌이다
    expect(stale.kind).toBe('invalid-state')
    // when: 맞는 revision과 이미 있는 이름으로 덮어쓴다
    const duplicate = await expectApiError(gateway.reports.update(42, { ...reportInput({ name: '이미 있는 이름' }), revision: 4 }), 409)
    // then: 이름 중복이다
    expect(duplicate.kind).toBe('already-exists')
    // then: 어느 리포트도 바뀌지 않았다
    expect((await gateway.reports.get(42)).revision).toBe(4)
  })

  // 테스트 코드: RS-005
  it('이름·설명의 NUL 문자는 서버 문구로 거절하고 빈 이름·길이 문구와 섞이지 않는다', async () => {
    // given: 김영업으로 로그인한 Fake
    const { gateway } = await mockAs('kim')
    // when: 이름 전체가 NUL인 경우, 이름이 NUL이고 길이도 넘는 경우, 설명에 NUL이 든 경우로 만든다
    const onlyNul = await expectApiError(gateway.reports.create(reportInput({ name: '\0' })), 422)
    const nulAndLong = await expectApiError(gateway.reports.create(reportInput({ name: `a\0${'b'.repeat(120)}` })), 422)
    const inDescription = await expectApiError(gateway.reports.create(reportInput({ description: `${'a'.repeat(1200)}\0` })), 422)
    // then: 이름은 NUL 문구, 설명은 NUL 문구다(빈 이름·길이 문구가 아니다)
    expect(onlyNul.message).toBe('리포트 이름에는 NUL 문자를 쓸 수 없습니다')
    expect(nulAndLong.message).toBe('리포트 이름에는 NUL 문자를 쓸 수 없습니다')
    expect(inDescription.message).toBe('설명에는 NUL 문자를 쓸 수 없습니다')
  })
})
