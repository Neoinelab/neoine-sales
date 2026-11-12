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

/** Reports 데이터 훅. 조회는 버튼으로만, 무효화 없음, 카탈로그는 한 번만. */

const REQUEST: ReportQueryInput = {
  columns: [{ field: 'deal.code', group: false }],
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
  // 테스트 코드: RQ-105
  it('정의 위반은 위반 목록과 첫 문구로 분류한다', () => {
    // given: 위반 둘이 든 422 invalid-report 오류
    const issues = [
      { location: ['columns', 0, 'field'], code: 'unknown-field', message: '허용되지 않은 필드입니다: x' },
      { location: ['row_limit'], code: 'row-limit-invalid', message: '최대 행 수가 올바르지 않습니다' },
    ]

    // when: 위반 목록이 있는 invalid-report 오류를 실행 실패로 분류한다
    const actual = reportRunFailure(invalidReport(issues))
    // then: invalid 분류에 첫 위반 문구와 위반 목록이 담긴다
    expect(actual).toEqual({ kind: 'invalid', message: '허용되지 않은 필드입니다: x', issues })
  })

  // 테스트 코드: RQ-105
  it('위반 목록이 없는 정의 위반은 위반 없음으로 본다', () => {
    // given: errors가 없는 422 invalid-report 오류
    const error = new ApiError(422, { type: 'https://x/problems/invalid-report', title: 't', status: 422, detail: '정의가 올바르지 않습니다' })

    // when: 위반 목록이 없는 invalid-report 오류를 실행 실패로 분류한다
    const actual = reportRunFailure(error)
    // then: invalid 분류에 서버 문구가 담기고 위반 목록은 비어 있다
    expect(actual).toEqual({ kind: 'invalid', message: '정의가 올바르지 않습니다', issues: [] })
  })

  // 테스트 코드: RQ-105
  it('시간 초과는 서버 문구로 분류한다', () => {
    // when: 시간 초과 오류를 실행 실패로 분류한다
    const actual = reportRunFailure(reportTimeout())
    // then: timeout 분류에 서버 문구가 담긴다
    expect(actual).toEqual({ kind: 'timeout', message: reportTimeout().message })
  })

  // 테스트 코드: RQ-105
  it('연결 끊김은 연결 문구로 분류한다', () => {
    // given: 상태 0의 네트워크 오류
    const error = new ApiError(0, { type: 'https://x/problems/network', title: 'Network Error', status: 0, detail: '서버에 연결할 수 없습니다.' })

    // when: 연결 끊김(상태 0) 오류를 실행 실패로 분류한다
    const actual = reportRunFailure(error)
    // then: network 분류에 연결 문구가 담긴다
    expect(actual).toEqual({ kind: 'network', message: '서버에 연결할 수 없습니다.' })
  })

  // 테스트 코드: RQ-105
  it('그 밖의 API 오류는 그 문구로 분류한다', () => {
    // given: 500 오류
    const error = new ApiError(500, { type: 'https://x/problems/http-error', title: 't', status: 500, detail: '서버 오류' })

    // when: 서버 오류(500) ApiError를 실행 실패로 분류한다
    const actual = reportRunFailure(error)
    // then: other 분류에 서버 문구가 담긴다
    expect(actual).toEqual({ kind: 'other', message: '서버 오류' })
  })

  // 테스트 코드: RQ-105
  it('예상 밖의 오류는 일반 문구로 분류한다', () => {
    // given: 예상 밖의 TypeError
    const error = new TypeError('boom')

    // when: 예상 밖의 TypeError를 실행 실패로 분류한다
    const actual = reportRunFailure(error)
    // then: other 분류에 일반 오류 문구가 담긴다
    expect(actual).toEqual({ kind: 'other', message: errorMessage(error) })
  })
})

describe('useReportFields', () => {
  // 테스트 코드: RQ-105
  it('카탈로그를 reports 키 아래에서 읽는다', async () => {
    // given: 새 쿼리 클라이언트
    const { wrapper, queryClient } = setup()

    // when: 카탈로그 훅을 쓴다
    const { result } = renderHook(() => useReportFields(), { wrapper })

    // then: 필드 40개를 받고 reports/fields 키에 저장된다
    await waitFor(() => expect(result.current.isSuccess).toBe(true))
    expect(result.current.data?.fields).toHaveLength(40)
    expect(keys.reportFields).toEqual(['reports', 'fields'])
    expect(queryClient.getQueryData(keys.reportFields)).toBe(result.current.data)
  })

  // 테스트 코드: RQ-105
  it('거절된 요청은 다시 시도하지 않고 ApiError로 알린다', async () => {
    // given: 로그인하지 않은 상태
    resetMock({ userId: null })
    const { wrapper } = setup()

    // when: 카탈로그 훅을 쓴다
    const { result } = renderHook(() => useReportFields(), { wrapper })

    // then: 401 ApiError가 한 번에 나온다
    await waitFor(() => expect(result.current.isError).toBe(true))
    expect(result.current.error).toBeInstanceOf(ApiError)
    expect(result.current.error?.status).toBe(401)
  })
})

describe('useRunReport', () => {
  // 테스트 코드: RQ-105
  it('조회 결과를 돌려주고 요청을 기록한다', async () => {
    // given: 조회 훅
    const { wrapper } = setup()
    const { result } = renderHook(() => useRunReport(), { wrapper })

    let rows: unknown
    await act(async () => {
      // when: 조회를 실행한다
      rows = (await result.current.mutateAsync(REQUEST)).rows
    })

    // then: 결과 행 3개를 받고 서버가 요청을 받았다
    expect(rows).toHaveLength(3)
    expect(mockControl.reportQueries()).toEqual([REQUEST])
  })

  // 테스트 코드: RQ-105
  it('조회 뒤 다른 쿼리를 무효화하지 않는다', async () => {
    const { wrapper, queryClient } = setup()
    // given: 무효화를 감시하는 쿼리 클라이언트
    const invalidate = vi.spyOn(queryClient, 'invalidateQueries')
    const { result } = renderHook(() => useRunReport(), { wrapper })

    await act(async () => {
      // when: 조회를 실행한다
      await result.current.mutateAsync(REQUEST)
    })

    // then: 무효화가 일어나지 않는다
    expect(invalidate).not.toHaveBeenCalled()
  })

  // 테스트 코드: RQ-105
  it('위반이면 위반 ApiError로 거절된다', async () => {
    // given: 조회 훅과 위반을 내는 요청(행 수 7)
    const { wrapper } = setup()
    const { result } = renderHook(() => useRunReport(), { wrapper })

    let failure: unknown
    await act(async () => {
      // when: 조회를 실행한다
      failure = await result.current.mutateAsync({ ...REQUEST, rowLimit: 7 }).catch((e: unknown) => e)
    })

    // then: invalid로 분류된다
    expect(reportRunFailure(failure)).toMatchObject({ kind: 'invalid' })
  })
})
