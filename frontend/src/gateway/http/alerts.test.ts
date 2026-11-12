import { afterEach, describe, expect, it, vi } from 'vitest'
import { serverAlertSettings, serverUserRef } from '../../test/fixtures/serverDeal'
import { createAlertsHttp } from './alerts'
import { json, problem, stubFetch } from './testHelpers'
import { USER_ID } from '../../test/fake/seed/ids'

afterEach(() => vi.unstubAllGlobals())

describe('alert settings over HTTP', () => {
  // 경고 기준 조회는 /alert-settings를 읽고 저장한 적 없는 기본값을 옮긴다.
  // 테스트 코드: RK-065
  it('get reads /alert-settings and maps the default (never saved) settings', async () => {
    // given: 서버가 기본값(14, 저장 기록 없음)을 준다
    const { calls } = stubFetch(json(serverAlertSettings()))

    // when: 경고 기준을 조회한다
    const settings = await createAlertsHttp().get()

    // then: GET /api/v1/alert-settings를 부르고 {staleDays: 14, updatedAt: null, updatedBy: null}이 된다
    expect(calls[0]).toMatchObject({ method: 'GET', path: '/api/v1/alert-settings' })
    expect(settings).toEqual({ staleDays: 14, updatedAt: null, updatedBy: null })
  })

  // 저장 시각과 저장자를 UserRef로 옮긴다.
  // 테스트 코드: RK-065
  it('get maps the saved time and the saver to a UserRef', async () => {
    // given: 서버가 30일, 저장 시각, 저장자를 준다
    stubFetch(
      json(
        serverAlertSettings({
          stale_days: 30,
          updated_at: '2026-10-16T10:00:00+09:00',
          updated_by: serverUserRef({ id: USER_ID.root, name: '최관리', label: '최관리', role: 'admin' }),
        }),
      ),
    )

    // when: 경고 기준을 조회한다
    const settings = await createAlertsHttp().get()

    // then: staleDays·updatedAt·updatedBy가 화면 모델로 바뀐다
    expect(settings).toEqual({
      staleDays: 30,
      updatedAt: '2026-10-16T10:00:00+09:00',
      updatedBy: { id: USER_ID.root, name: '최관리', role: 'admin', status: 'active' },
    })
  })

  // 저장은 PUT {stale_days}를 보내고 저장된 값을 돌려준다.
  // 테스트 코드: RK-065
  it('save PUTs {stale_days} and returns the stored settings', async () => {
    // given: 서버가 저장 결과를 준다
    const { calls } = stubFetch(json(serverAlertSettings({ stale_days: 7, updated_at: '2026-10-17T09:00:00+09:00', updated_by: serverUserRef() })))

    // when: 7일로 저장한다
    const saved = await createAlertsHttp().save(7)

    // then: PUT /api/v1/alert-settings에 {stale_days: 7}을 보내고 결과를 옮긴다
    expect(calls[0]).toMatchObject({ method: 'PUT', path: '/api/v1/alert-settings', body: { stale_days: 7 } })
    expect(saved.staleDays).toBe(7)
    expect(saved.updatedBy).toMatchObject({ id: USER_ID.kim })
  })

  // 서버 422 문장을 메시지 그대로 넘긴다.
  // 테스트 코드: RK-065
  it('save passes the server 422 sentence through as the message (validation kind)', async () => {
    // given: 서버가 422 invalid-value와 범위 문장을 준다
    stubFetch(problem(422, 'invalid-value', '미업데이트 기준은 1~365일 사이의 정수로 입력하세요.'))

    // when·then: 0일로 저장한다 → validation 종류의 ApiError이고 메시지가 서버 문장이다
    await expect(createAlertsHttp().save(0)).rejects.toMatchObject({
      status: 422,
      kind: 'validation',
      message: '미업데이트 기준은 1~365일 사이의 정수로 입력하세요.',
    })
  })

  // 비admin 저장은 403, 세션 없음은 401의 ApiError로 넘긴다.
  // 테스트 코드: RK-065
  it('save maps 403 for a non-admin and 401 for no session', async () => {
    // given: 서버가 403, 401을 차례로 준다
    stubFetch(problem(403, 'forbidden', '권한이 없습니다.'), problem(401, 'unauthenticated', '로그인이 필요합니다.'))

    // when·then: 저장과 조회를 부른다 → 403은 forbidden, 401은 unauthorized ApiError다
    await expect(createAlertsHttp().save(10)).rejects.toMatchObject({ status: 403, kind: 'forbidden' })
    await expect(createAlertsHttp().get()).rejects.toMatchObject({ status: 401, kind: 'unauthorized' })
  })
})
