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

/** 저장 리포트 화면 데이터 계층: 캐시 키, 읽기 훅, 만들기·삭제 뒤 캐시 정리, 저장 실패 분류. */

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
  // 테스트 코드: RS-106
  it('저장 실패를 서버 kind별로 분류한다', () => {
    // given: 위반 목록 하나
    const issues = [{ location: ['columns', 0, 'field'], code: 'unknown-field', message: '허용되지 않은 필드입니다: x' }]

    // when: 이름 중복·다른 사용자가 먼저 저장한 오류를 저장 실패로 분류한다
    const actual = saveFailure(alreadyExists('같은 이름의 리포트가 이미 있습니다.'))
    const actual2 = saveFailure(invalidState('다른 사용자가 먼저 이 리포트를 저장했습니다.'))
    const actual3 = saveFailure(invalidReport(issues))
    const actual4 = saveFailure(forbidden('공개 범위는 만든 사람 또는 admin만 바꿀 수 있습니다.'))
    const actual5 = saveFailure(notFound('리포트를 찾을 수 없습니다.'))
    // then: 이름 중복은 name, 충돌은 conflict, 정의 위반은 invalid(항목 포함), 권한은 forbidden, 없음은 notFound로 나뉜다
    expect(actual).toMatchObject({
      kind: 'name',
      message: '같은 이름의 리포트가 이미 있습니다.',
    })
    expect(actual2).toMatchObject({
      kind: 'conflict',
      message: '다른 사용자가 먼저 이 리포트를 저장했습니다.',
    })
    expect(actual3).toMatchObject({ kind: 'invalid', message: '허용되지 않은 필드입니다: x', issues })
    expect(actual4).toMatchObject({
      kind: 'forbidden',
      message: '공개 범위는 만든 사람 또는 admin만 바꿀 수 있습니다.',
    })
    expect(actual5).toMatchObject({ kind: 'notFound', message: '리포트를 찾을 수 없습니다.' })
  })

  // 테스트 코드: RS-106
  it('그 밖의 오류는 other로 분류하고 문구를 그대로 쓴다', () => {
    // when: 이름 길이 검증 오류와 서버 오류(500)를 저장 실패로 분류한다
    const actual = saveFailure(validation('리포트 이름은 100자 이내로 입력하세요.'))
    const actual2 = saveFailure(new ApiError(500, { type: 'https://x/problems/http-error', title: 't', status: 500, detail: '서버 오류' }))
    const actual3 = saveFailure(new TypeError('boom')).kind
    // then: 값 오류·500 오류·일반 예외 모두 other이고 서버 문구를 담는다
    expect(actual).toMatchObject({
      kind: 'other',
      message: '리포트 이름은 100자 이내로 입력하세요.',
    })
    expect(actual2).toMatchObject({
      kind: 'other',
      message: '서버 오류',
    })
    expect(actual3).toBe('other')
  })

  // 테스트 코드: RS-106
  it('항목이 없는 정의 위반은 빈 위반 목록으로 본다', () => {
    // given: errors가 없는 invalid-report 422
    const error = new ApiError(422, { type: 'https://x/problems/invalid-report', title: 't', status: 422, detail: '정의가 올바르지 않습니다' })

    // when: errors가 없는 invalid-report 오류를 저장 실패로 분류한다
    const actual = saveFailure(error)
    // then: invalid이고 위반 목록이 비어 있다
    expect(actual).toMatchObject({ kind: 'invalid', issues: [] })
  })
})

describe('query keys', () => {
  // 테스트 코드: RS-106
  it('저장 리포트 캐시 키는 필드 카탈로그 키와 분리되어 저장해도 카탈로그를 다시 받지 않는다', () => {
    // when: 리포트 12의 저장 리포트·실행 캐시 키를 만든다
    const actual = keys.savedReports
    const actual2 = keys.savedReport(12)
    const actual3 = keys.savedReportRun(12)
    const actual4 = keys.reportFields
    // then: 저장 리포트·상세·실행 키가 reports/saved, reports/run 아래이고 카탈로그 키와 다르다
    expect(actual).toEqual(['reports', 'saved'])
    expect(actual2).toEqual(['reports', 'saved', 12])
    expect(actual3).toEqual(['reports', 'run', 12])
    expect(actual4).toEqual(['reports', 'fields'])
  })
})

describe('useSavedReports and useSavedReport', () => {
  // 테스트 코드: RS-106
  it('볼 수 있는 리포트 목록을 저장 리포트 키 아래에 읽는다', async () => {
    // given: 샘플 리포트를 시드한 Fake와 새 쿼리 클라이언트
    const { wrapper, queryClient } = setup()

    // when: 목록 훅을 마운트한다
    const { result } = renderHook(() => useSavedReports(), { wrapper })

    // then: 볼 수 있는 리포트 id가 최근 수정 순이고 캐시 키에 담긴다
    await waitFor(() => expect(result.current.isSuccess).toBe(true))
    expect(result.current.data?.map((r) => r.id)).toEqual([13, 11, 12, 15])
    expect(queryClient.getQueryData(keys.savedReports)).toBe(result.current.data)
  })

  // 테스트 코드: RS-106
  it('리포트 하나를 정의와 함께 자기 키 아래에 읽는다', async () => {
    // given: 샘플 리포트를 시드한 Fake
    const { wrapper, queryClient } = setup()

    // when: 상세 훅을 마운트한다
    const { result } = renderHook(() => useSavedReport(MINE_PUBLIC.id), { wrapper })

    // then: 정의가 담긴 상세가 그 리포트 키에 담긴다
    await waitFor(() => expect(result.current.isSuccess).toBe(true))
    expect(result.current.data).toMatchObject({ id: 11, revision: 1, definition: MINE_PUBLIC.definition })
    expect(queryClient.getQueryData(keys.savedReport(11))).toBe(result.current.data)
  })

  // 테스트 코드: RS-106
  it('숨긴 리포트는 다시 시도하지 않고 찾을 수 없음으로 알린다', async () => {
    // given: 남의 비공개 리포트
    const { wrapper } = setup()

    // when: 상세 훅을 마운트한다
    const { result } = renderHook(() => useSavedReport(PARK_PRIVATE.id), { wrapper })

    // then: 한 번 만에 404 ApiError가 된다
    await waitFor(() => expect(result.current.isError).toBe(true))
    expect(result.current.error).toBeInstanceOf(ApiError)
    expect(result.current.error?.status).toBe(404)
  })
})

describe('useRunSavedReport', () => {
  // 테스트 코드: RS-106
  it('저장된 정의를 실행해 결과를 돌려준다', async () => {
    // given: 박영업의 공개 리포트
    const { wrapper } = setup()

    // when: 실행 훅을 마운트한다
    const { result } = renderHook(() => useRunSavedReport(PARK_PUBLIC.id), { wrapper })

    // then: 정의의 컬럼으로 결과가 오고 실행 요청이 한 번 기록된다
    await waitFor(() => expect(result.current.isSuccess).toBe(true))
    expect(result.current.data?.columns.map((c) => c.field)).toEqual(['deal.code', 'action.action'])
    expect(mockControl.savedReportRequests()).toEqual([{ op: 'run', id: 13 }])
  })

  // 테스트 코드: RS-106
  it('실행 결과는 항상 낡은 것으로 보아 마운트할 때마다 다시 실행한다', async () => {
    // given: 한 번 실행하고 언마운트한 훅
    const { wrapper } = setup()
    const first = renderHook(() => useRunSavedReport(MINE_PUBLIC.id), { wrapper })
    await waitFor(() => expect(first.result.current.isSuccess).toBe(true))
    first.unmount()

    // when: 같은 훅을 다시 마운트한다
    const second = renderHook(() => useRunSavedReport(MINE_PUBLIC.id), { wrapper })
    await waitFor(() => expect(second.result.current.isSuccess).toBe(true))

    // then: 실행 요청이 두 번 기록된다
    await waitFor(() => expect(mockControl.savedReportRequests().filter((r) => r.op === 'run')).toHaveLength(2))
  })

  // 테스트 코드: RS-106
  it('지금 규칙과 맞지 않는 저장 정의는 위반으로 실패한다', async () => {
    // given: 지금 카탈로그에 없는 필드를 쓰는 저장 리포트, 새 쿼리 클라이언트
    mockControl.seedSavedReports([{ ...MINE_PUBLIC, definition: BROKEN_DEFINITION }])
    const { wrapper } = setup()

    // when: 실행 훅을 마운트한다
    const { result } = renderHook(() => useRunSavedReport(MINE_PUBLIC.id), { wrapper })

    // then: invalid-report 오류이고 다시 시도하지 않는다
    await waitFor(() => expect(result.current.isError).toBe(true))
    expect(result.current.error?.kind).toBe('invalid-report')
    expect(mockControl.savedReportRequests().filter((r) => r.op === 'run')).toHaveLength(1)
  })
})

describe('useCreateReport and useDeleteReport', () => {
  // 테스트 코드: RS-106
  it('저장하면 목록을 다시 받고 새 상세를 캐시에 넣으며 필드 카탈로그는 건드리지 않는다', async () => {
    // given: 카탈로그와 목록이 채워진 캐시
    const { wrapper, queryClient } = setup()
    const fields = renderHook(() => useReportFields(), { wrapper })
    await waitFor(() => expect(fields.result.current.isSuccess).toBe(true))
    const list = renderHook(() => useSavedReports(), { wrapper })
    await waitFor(() => expect(list.result.current.isSuccess).toBe(true))
    const { result } = renderHook(() => useCreateReport(), { wrapper })

    // when: 리포트를 만든다
    let created: { id: number } | undefined
    await act(async () => {
      created = await result.current.mutateAsync(reportInput({ name: '새로 저장' }))
    })

    // then: 새 id를 받고 목록이 다시 받아져 새 이름이 있으며 새 상세가 캐시에 있고 카탈로그는 무효화되지 않았다
    expect(created?.id).toBe(16)
    await waitFor(() => expect(list.result.current.data?.map((r) => r.name)).toContain('새로 저장'))
    expect(queryClient.getQueryData(keys.savedReport(16))).toMatchObject({ id: 16, name: '새로 저장', revision: 1 })
    expect(queryClient.getQueryState(keys.reportFields)?.isInvalidated).toBe(false)
  })

  // 테스트 코드: RS-106
  it('같은 이름으로 만들면 이름 중복 ApiError로 거절된다', async () => {
    // given: 새 쿼리 클라이언트
    const { wrapper } = setup()
    const { result } = renderHook(() => useCreateReport(), { wrapper })

    // when: 이미 있는 이름(소문자)으로 만든다
    let failure: unknown
    await act(async () => {
      failure = await result.current.mutateAsync(reportInput({ name: MINE_PUBLIC.name.toLowerCase() })).catch((e: unknown) => e)
    })

    // then: ApiError이고 saveFailure가 name으로 분류한다
    expect(failure).toBeInstanceOf(ApiError)
    expect(saveFailure(failure).kind).toBe('name')
  })

  // 테스트 코드: RS-106
  it('삭제하면 목록에서 빼고 그 상세·실행 캐시를 지운다', async () => {
    // given: 목록과 그 리포트의 상세·실행 캐시가 채워진 상태
    const { wrapper, queryClient } = setup()
    const list = renderHook(() => useSavedReports(), { wrapper })
    await waitFor(() => expect(list.result.current.isSuccess).toBe(true))
    queryClient.setQueryData(keys.savedReport(11), MINE_PUBLIC)
    queryClient.setQueryData(keys.savedReportRun(11), { rows: [] })
    // when: 리포트를 삭제한다
    const { result } = renderHook(() => useDeleteReport(), { wrapper })

    await act(async () => {
      await result.current.mutateAsync(MINE_PUBLIC.id)
    })

    // then: 목록에서 빠지고 상세·실행 캐시가 비워진다
    await waitFor(() => expect(list.result.current.data?.map((r) => r.id)).not.toContain(11))
    expect(queryClient.getQueryData(keys.savedReport(11))).toBeUndefined()
    expect(queryClient.getQueryData(keys.savedReportRun(11))).toBeUndefined()
  })
})
