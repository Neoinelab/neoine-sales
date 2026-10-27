import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { act, renderHook, waitFor } from '@testing-library/react'
import type { ReactNode } from 'react'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import { ApiError, errorMessage } from '../shared/api/problem'
import type { ReportQueryInput } from '../shared/model/reportTypes'
import { mockControl, resetMock } from '../test/fake/default'
import { invalidReport, reportTimeout } from '../test/fake/errors'
import { USER_ID } from '../test/fake/seed/ids'
import { TEST_NOW } from '../test/fake/testing'
import { keys } from './queryKeys'
import { reportRunFailure, useReportFields, useRunReport } from './reports'

/** Reports 데이터 훅(Reports 2단계 P25). 조회는 버튼으로만, 무효화 없음, 카탈로그는 한 번만. */

const REQUEST: ReportQueryInput = {
  columns: [{ field: 'deal.code', format: 'as_is', group: false }],
  conditions: [],
  combine: 'and',
  rowLimit: 100,
}

function setup(retry?: boolean) {
  const queryClient = new QueryClient({
    defaultOptions: retry === undefined ? undefined : { queries: { retry }, mutations: { retry } },
  })
  const wrapper = ({ children }: { children: ReactNode }) => <QueryClientProvider client={queryClient}>{children}</QueryClientProvider>
  return { queryClient, wrapper }
}

beforeEach(() => {
  resetMock({ now: TEST_NOW, userId: USER_ID.han })
})

describe('reportRunFailure', () => {
  it('maps an invalid report to its issues and the first message', () => {
    const issues = [
      { location: ['columns', 0, 'field'], code: 'unknown-field', message: '허용되지 않은 필드입니다: x' },
      { location: ['row_limit'], code: 'row-limit-invalid', message: '최대 행 수가 올바르지 않습니다' },
    ]

    expect(reportRunFailure(invalidReport(issues))).toEqual({ kind: 'invalid', message: '허용되지 않은 필드입니다: x', issues })
  })

  it('treats an invalid report without issue items as no issues', () => {
    const error = new ApiError(422, { type: 'https://x/problems/invalid-report', title: 't', status: 422, detail: '정의가 올바르지 않습니다' })

    expect(reportRunFailure(error)).toEqual({ kind: 'invalid', message: '정의가 올바르지 않습니다', issues: [] })
  })

  it('maps a report timeout to the server message', () => {
    expect(reportRunFailure(reportTimeout())).toEqual({ kind: 'timeout', message: reportTimeout().message })
  })

  it('maps a lost connection to the connection message', () => {
    const error = new ApiError(0, { type: 'https://x/problems/network', title: 'Network Error', status: 0, detail: '서버에 연결할 수 없습니다.' })

    expect(reportRunFailure(error)).toEqual({ kind: 'network', message: '서버에 연결할 수 없습니다.' })
  })

  it('maps any other API error to its message', () => {
    const error = new ApiError(500, { type: 'https://x/problems/http-error', title: 't', status: 500, detail: '서버 오류' })

    expect(reportRunFailure(error)).toEqual({ kind: 'other', message: '서버 오류' })
  })

  it('maps an unexpected error to the generic message', () => {
    const error = new TypeError('boom')

    expect(reportRunFailure(error)).toEqual({ kind: 'other', message: errorMessage(error) })
  })
})

describe('useReportFields', () => {
  it('loads the catalog under the reports key', async () => {
    const { wrapper, queryClient } = setup()

    const { result } = renderHook(() => useReportFields(), { wrapper })

    await waitFor(() => expect(result.current.isSuccess).toBe(true))
    expect(result.current.data?.fields).toHaveLength(40)
    expect(keys.reportFields).toEqual(['reports', 'fields'])
    expect(queryClient.getQueryData(keys.reportFields)).toBe(result.current.data)
  })

  it('reports a rejected request as an ApiError without retrying', async () => {
    resetMock({ userId: null })
    const { wrapper } = setup()

    const { result } = renderHook(() => useReportFields(), { wrapper })

    await waitFor(() => expect(result.current.isError).toBe(true))
    expect(result.current.error).toBeInstanceOf(ApiError)
    expect(result.current.error?.status).toBe(401)
  })
})

describe('useRunReport', () => {
  it('returns the result and records the request', async () => {
    const { wrapper } = setup()
    const { result } = renderHook(() => useRunReport(), { wrapper })

    let rows: unknown
    await act(async () => {
      rows = (await result.current.mutateAsync(REQUEST)).rows
    })

    expect(rows).toHaveLength(3)
    expect(mockControl.reportQueries()).toEqual([REQUEST])
  })

  it('does not refresh any query after a run', async () => {
    const { wrapper, queryClient } = setup()
    const invalidate = vi.spyOn(queryClient, 'invalidateQueries')
    const { result } = renderHook(() => useRunReport(), { wrapper })

    await act(async () => {
      await result.current.mutateAsync(REQUEST)
    })

    expect(invalidate).not.toHaveBeenCalled()
  })

  it('rejects with the ApiError of a violation', async () => {
    const { wrapper } = setup()
    const { result } = renderHook(() => useRunReport(), { wrapper })

    let failure: unknown
    await act(async () => {
      failure = await result.current.mutateAsync({ ...REQUEST, rowLimit: 7 }).catch((e: unknown) => e)
    })

    expect(reportRunFailure(failure)).toMatchObject({ kind: 'invalid' })
  })
})
