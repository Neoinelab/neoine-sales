import { useMutation, useQuery } from '@tanstack/react-query'
import { gateway } from '../gateway'
import { ApiError, errorMessage } from '../shared/api/problem'
import type { ReportCatalog, ReportQueryInput, ReportResult, ReportRunFailure } from '../shared/model/reportTypes'
import { keys } from './queryKeys'
import { NO_RETRY, type Mutation, type Query } from './result'

/**
 * gateway.reports.fields(). 키 keys.reportFields.
 * 카탈로그는 서버 코드에서 오는 고정 정의라 세션 동안 다시 받지 않는다(staleTime 무한).
 */
export function useReportFields(): Query<ReportCatalog> {
  return useQuery<ReportCatalog, ApiError>({
    queryKey: keys.reportFields,
    queryFn: () => gateway.reports.fields(),
    staleTime: Infinity,
    ...NO_RETRY,
  })
}

/** gateway.reports.query(input). 버튼으로만 실행하고 저장하지 않으므로 어떤 쿼리도 무효화하지 않는다. */
export function useRunReport(): Mutation<ReportQueryInput, ReportResult> {
  return useMutation<ReportResult, ApiError, ReportQueryInput>({ mutationFn: (input) => gateway.reports.query(input) })
}

/** 조회 실패를 화면 표시용으로 가른다. 정의 위반의 위치 목록은 `problem.reportErrors`(없으면 빈 목록). */
export function reportRunFailure(error: unknown): ReportRunFailure {
  const message = errorMessage(error)
  if (!(error instanceof ApiError)) return { kind: 'other', message }
  if (error.kind === 'invalid-report') return { kind: 'invalid', message, issues: error.problem?.reportErrors ?? [] }
  if (error.kind === 'report-timeout') return { kind: 'timeout', message }
  if (error.kind === 'network') return { kind: 'network', message }
  return { kind: 'other', message }
}
