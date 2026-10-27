import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { act, renderHook, waitFor } from '@testing-library/react'
import type { ReactNode } from 'react'
import { beforeEach, describe, expect, it } from 'vitest'
import { ApiError } from '../shared/api/problem'
import { mockControl, resetMock } from '../test/fake/default'
import { alreadyExists, forbidden, invalidReport, invalidState, notFound, validation } from '../test/fake/errors'
import { USER_ID } from '../test/fake/seed/ids'
import { TEST_NOW } from '../test/fake/testing'
import { BROKEN_DEFINITION, MINE_PUBLIC, PARK_PRIVATE, PARK_PUBLIC, SAVED_SAMPLES, reportInput } from '../test/savedReports'
import { keys } from './queryKeys'
import { saveFailure, useCreateReport, useDeleteReport, useReportFields, useRunSavedReport, useSavedReport, useSavedReports } from './reports'

/** 저장 리포트 데이터 훅(Reports 3단계 P6, AC13·15·17). */

function setup() {
  const queryClient = new QueryClient()
  const wrapper = ({ children }: { children: ReactNode }) => <QueryClientProvider client={queryClient}>{children}</QueryClientProvider>
  return { queryClient, wrapper }
}

beforeEach(() => {
  resetMock({ now: TEST_NOW, userId: USER_ID.kim })
  mockControl.seedSavedReports(SAVED_SAMPLES)
})

describe('saveFailure', () => {
  it('maps save failures by kind', () => {
    const issues = [{ location: ['columns', 0, 'field'], code: 'unknown-field', message: '허용되지 않은 필드입니다: x' }]

    expect(saveFailure(alreadyExists('같은 이름의 리포트가 이미 있습니다.'))).toMatchObject({
      kind: 'name',
      message: '같은 이름의 리포트가 이미 있습니다.',
    })
    expect(saveFailure(invalidState('다른 사용자가 먼저 이 리포트를 저장했습니다.'))).toMatchObject({
      kind: 'conflict',
      message: '다른 사용자가 먼저 이 리포트를 저장했습니다.',
    })
    expect(saveFailure(invalidReport(issues))).toMatchObject({ kind: 'invalid', message: '허용되지 않은 필드입니다: x', issues })
    expect(saveFailure(forbidden('공개 범위는 만든 사람 또는 admin만 바꿀 수 있습니다.'))).toMatchObject({
      kind: 'forbidden',
      message: '공개 범위는 만든 사람 또는 admin만 바꿀 수 있습니다.',
    })
    expect(saveFailure(notFound('리포트를 찾을 수 없습니다.'))).toMatchObject({ kind: 'notFound', message: '리포트를 찾을 수 없습니다.' })
  })

  it('treats other errors as other with their message', () => {
    expect(saveFailure(validation('리포트 이름은 100자 이내로 입력하세요.'))).toMatchObject({
      kind: 'other',
      message: '리포트 이름은 100자 이내로 입력하세요.',
    })
    expect(saveFailure(new ApiError(500, { type: 'https://x/problems/http-error', title: 't', status: 500, detail: '서버 오류' }))).toMatchObject({
      kind: 'other',
      message: '서버 오류',
    })
    expect(saveFailure(new TypeError('boom')).kind).toBe('other')
  })

  it('gives an invalid report without items an empty issue list', () => {
    const error = new ApiError(422, { type: 'https://x/problems/invalid-report', title: 't', status: 422, detail: '정의가 올바르지 않습니다' })

    expect(saveFailure(error)).toMatchObject({ kind: 'invalid', issues: [] })
  })
})

describe('query keys', () => {
  it('keeps saved reports apart from the field catalog so a save never refetches the catalog', () => {
    expect(keys.savedReports).toEqual(['reports', 'saved'])
    expect(keys.savedReport(12)).toEqual(['reports', 'saved', 12])
    expect(keys.savedReportRun(12)).toEqual(['reports', 'run', 12])
    expect(keys.reportFields).toEqual(['reports', 'fields'])
  })
})

describe('useSavedReports and useSavedReport', () => {
  it('loads the visible reports under the saved reports key', async () => {
    const { wrapper, queryClient } = setup()

    const { result } = renderHook(() => useSavedReports(), { wrapper })

    await waitFor(() => expect(result.current.isSuccess).toBe(true))
    expect(result.current.data?.map((r) => r.id)).toEqual([13, 11, 12, 15])
    expect(queryClient.getQueryData(keys.savedReports)).toBe(result.current.data)
  })

  it('loads one report with its definition under its own key', async () => {
    const { wrapper, queryClient } = setup()

    const { result } = renderHook(() => useSavedReport(MINE_PUBLIC.id), { wrapper })

    await waitFor(() => expect(result.current.isSuccess).toBe(true))
    expect(result.current.data).toMatchObject({ id: 11, revision: 1, definition: MINE_PUBLIC.definition })
    expect(queryClient.getQueryData(keys.savedReport(11))).toBe(result.current.data)
  })

  it('reports a hidden report as not found without retrying', async () => {
    const { wrapper } = setup()

    const { result } = renderHook(() => useSavedReport(PARK_PRIVATE.id), { wrapper })

    await waitFor(() => expect(result.current.isError).toBe(true))
    expect(result.current.error).toBeInstanceOf(ApiError)
    expect(result.current.error?.status).toBe(404)
  })
})

describe('useRunSavedReport', () => {
  it('runs the stored definition and returns the result', async () => {
    const { wrapper } = setup()

    const { result } = renderHook(() => useRunSavedReport(PARK_PUBLIC.id), { wrapper })

    await waitFor(() => expect(result.current.isSuccess).toBe(true))
    expect(result.current.data?.columns.map((c) => c.field)).toEqual(['deal.code', 'action.action'])
    expect(mockControl.savedReportRequests()).toEqual([{ op: 'run', id: 13 }])
  })

  it('runs again each time it is mounted because the data is never fresh', async () => {
    const { wrapper } = setup()
    const first = renderHook(() => useRunSavedReport(MINE_PUBLIC.id), { wrapper })
    await waitFor(() => expect(first.result.current.isSuccess).toBe(true))
    first.unmount()

    const second = renderHook(() => useRunSavedReport(MINE_PUBLIC.id), { wrapper })
    await waitFor(() => expect(second.result.current.isSuccess).toBe(true))

    await waitFor(() => expect(mockControl.savedReportRequests().filter((r) => r.op === 'run')).toHaveLength(2))
  })

  it('fails with the violations of a stored definition the catalog no longer accepts', async () => {
    mockControl.seedSavedReports([{ ...MINE_PUBLIC, definition: BROKEN_DEFINITION }])
    const { wrapper } = setup()

    const { result } = renderHook(() => useRunSavedReport(MINE_PUBLIC.id), { wrapper })

    await waitFor(() => expect(result.current.isError).toBe(true))
    expect(result.current.error?.kind).toBe('invalid-report')
    expect(mockControl.savedReportRequests().filter((r) => r.op === 'run')).toHaveLength(1)
  })
})

describe('useCreateReport and useDeleteReport', () => {
  it('refreshes the list, caches the new detail and leaves the field catalog alone', async () => {
    const { wrapper, queryClient } = setup()
    const fields = renderHook(() => useReportFields(), { wrapper })
    await waitFor(() => expect(fields.result.current.isSuccess).toBe(true))
    const list = renderHook(() => useSavedReports(), { wrapper })
    await waitFor(() => expect(list.result.current.isSuccess).toBe(true))
    const { result } = renderHook(() => useCreateReport(), { wrapper })

    let created: { id: number } | undefined
    await act(async () => {
      created = await result.current.mutateAsync(reportInput({ name: '새로 저장' }))
    })

    expect(created?.id).toBe(16)
    await waitFor(() => expect(list.result.current.data?.map((r) => r.name)).toContain('새로 저장'))
    expect(queryClient.getQueryData(keys.savedReport(16))).toMatchObject({ id: 16, name: '새로 저장', revision: 1 })
    expect(queryClient.getQueryState(keys.reportFields)?.isInvalidated).toBe(false)
  })

  it('rejects with the ApiError of a duplicate name', async () => {
    const { wrapper } = setup()
    const { result } = renderHook(() => useCreateReport(), { wrapper })

    let failure: unknown
    await act(async () => {
      failure = await result.current.mutateAsync(reportInput({ name: MINE_PUBLIC.name.toLowerCase() })).catch((e: unknown) => e)
    })

    expect(failure).toBeInstanceOf(ApiError)
    expect(saveFailure(failure).kind).toBe('name')
  })

  it('removes the report from the list and drops its detail and run caches', async () => {
    const { wrapper, queryClient } = setup()
    const list = renderHook(() => useSavedReports(), { wrapper })
    await waitFor(() => expect(list.result.current.isSuccess).toBe(true))
    queryClient.setQueryData(keys.savedReport(11), MINE_PUBLIC)
    queryClient.setQueryData(keys.savedReportRun(11), { rows: [] })
    const { result } = renderHook(() => useDeleteReport(), { wrapper })

    await act(async () => {
      await result.current.mutateAsync(MINE_PUBLIC.id)
    })

    await waitFor(() => expect(list.result.current.data?.map((r) => r.id)).not.toContain(11))
    expect(queryClient.getQueryData(keys.savedReport(11))).toBeUndefined()
    expect(queryClient.getQueryData(keys.savedReportRun(11))).toBeUndefined()
  })
})
