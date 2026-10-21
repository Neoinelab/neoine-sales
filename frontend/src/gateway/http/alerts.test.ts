import { afterEach, describe, expect, it, vi } from 'vitest'
import { serverAlertSettings, serverUserRef } from '../../test/fixtures/serverDeal'
import { createAlertsHttp } from './alerts'
import { json, problem, stubFetch } from './testHelpers'
import { USER_ID } from '../../test/fake/seed/ids'

afterEach(() => vi.unstubAllGlobals())

describe('alert settings over HTTP', () => {
  it('get reads /alert-settings and maps the default (never saved) settings', async () => {
    const { calls } = stubFetch(json(serverAlertSettings()))

    const settings = await createAlertsHttp().get()

    expect(calls[0]).toMatchObject({ method: 'GET', path: '/api/v1/alert-settings' })
    expect(settings).toEqual({ staleDays: 14, updatedAt: null, updatedBy: null })
  })

  it('get maps the saved time and the saver to a UserRef', async () => {
    stubFetch(
      json(
        serverAlertSettings({
          stale_days: 30,
          updated_at: '2026-10-16T10:00:00+09:00',
          updated_by: serverUserRef({ id: USER_ID.root, name: '최관리', label: '최관리', role: 'admin' }),
        }),
      ),
    )

    const settings = await createAlertsHttp().get()

    expect(settings).toEqual({
      staleDays: 30,
      updatedAt: '2026-10-16T10:00:00+09:00',
      updatedBy: { id: USER_ID.root, name: '최관리', role: 'admin', status: 'active' },
    })
  })

  it('save PUTs {stale_days} and returns the stored settings', async () => {
    const { calls } = stubFetch(json(serverAlertSettings({ stale_days: 7, updated_at: '2026-10-17T09:00:00+09:00', updated_by: serverUserRef() })))

    const saved = await createAlertsHttp().save(7)

    expect(calls[0]).toMatchObject({ method: 'PUT', path: '/api/v1/alert-settings', body: { stale_days: 7 } })
    expect(saved.staleDays).toBe(7)
    expect(saved.updatedBy).toMatchObject({ id: USER_ID.kim })
  })

  it('save passes the server 422 sentence through as the message (validation kind)', async () => {
    stubFetch(problem(422, 'invalid-value', '미업데이트 기준은 1~365일 사이의 정수로 입력하세요.'))

    await expect(createAlertsHttp().save(0)).rejects.toMatchObject({
      status: 422,
      kind: 'validation',
      message: '미업데이트 기준은 1~365일 사이의 정수로 입력하세요.',
    })
  })

  it('save maps 403 for a non-admin and 401 for no session', async () => {
    stubFetch(problem(403, 'forbidden', '권한이 없습니다.'), problem(401, 'unauthenticated', '로그인이 필요합니다.'))

    await expect(createAlertsHttp().save(10)).rejects.toMatchObject({ status: 403, kind: 'forbidden' })
    await expect(createAlertsHttp().get()).rejects.toMatchObject({ status: 401, kind: 'unauthorized' })
  })
})
