import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { gateway } from '../gateway'
import { ApiError, errorMessage } from '../shared/api/problem'
import type {
  ReportCatalog,
  ReportIssue,
  ReportLayout,
  ReportQueryInput,
  ReportResult,
  ReportRunFailure,
  SavedReport,
  SavedReportInput,
  SavedReportMeta,
  SavedReportSummary,
} from '../shared/model/reportTypes'
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

/** gateway.reports.list(). 키 keys.savedReports(카탈로그 키와 따로라 저장·삭제가 카탈로그를 다시 받게 하지 않는다). */
export function useSavedReports(): Query<SavedReportSummary[]> {
  // 'all': 렌더 밖에서 result.current.data를 읽는 훅 테스트가 갱신을 보도록 모든 변경에 다시 그린다(화면은 렌더 중 읽어 기본 추적으로도 충분).
  return useQuery<SavedReportSummary[], ApiError>({ queryKey: keys.savedReports, queryFn: () => gateway.reports.list(), notifyOnChangeProps: 'all', ...NO_RETRY })
}

/** gateway.reports.get(id). 키 keys.savedReport(id). id가 없으면(주소가 잘못됨) 요청하지 않는다. */
export function useSavedReport(id: number | undefined): Query<SavedReport> {
  return useQuery<SavedReport, ApiError>({
    queryKey: keys.savedReport(id ?? 0),
    queryFn: () => gateway.reports.get(id as number),
    enabled: id !== undefined,
    ...NO_RETRY,
  })
}

/**
 * gateway.reports.run(id). POST지만 읽기 전용이라 useQuery로 둔다. 데이터는 항상 낡은 것으로 보아
 * 마운트마다 다시 실행하고(오늘 날짜 기준 상대 기간), 창 포커스로는 다시 실행하지 않는다.
 */
export function useRunSavedReport(id: number | undefined): Query<ReportResult> {
  return useQuery<ReportResult, ApiError>({
    queryKey: keys.savedReportRun(id ?? 0),
    queryFn: () => gateway.reports.run(id as number),
    enabled: id !== undefined,
    staleTime: 0,
    refetchOnWindowFocus: false,
    ...NO_RETRY,
  })
}

/**
 * 저장·수정·복제 성공 공통: 받은 상세를 캐시에 넣어 이동한 화면이 다시 받지 않게 하고, 목록을 다시 받는다.
 * 카탈로그(keys.reportFields)는 건드리지 않는다.
 */
function useCacheSaved(): (saved: SavedReport) => Promise<void> {
  const queryClient = useQueryClient()
  return async (saved) => {
    queryClient.setQueryData(keys.savedReport(saved.id), saved)
    queryClient.removeQueries({ queryKey: keys.savedReportRun(saved.id) })
    // 목록만 다시 받는다(exact): 방금 넣은 상세를 무효화해 다시 받게 하지 않는다.
    await queryClient.invalidateQueries({ queryKey: keys.savedReports, exact: true })
  }
}

/** gateway.reports.create. 변수 = SavedReportInput. 성공: 목록 무효화 + 상세 캐시. */
export function useCreateReport(): Mutation<SavedReportInput, SavedReport> {
  const cache = useCacheSaved()
  return useMutation<SavedReport, ApiError, SavedReportInput>({
    mutationFn: (input) => gateway.reports.create(input),
    onSuccess: async (saved) => cache(saved),
  })
}

/** gateway.reports.update(덮어쓰기). 변수 = { id, input(revision 포함) }. */
export function useUpdateReport(): Mutation<{ id: number; input: SavedReportInput & { revision: number } }, SavedReport> {
  const cache = useCacheSaved()
  return useMutation<SavedReport, ApiError, { id: number; input: SavedReportInput & { revision: number } }>({
    mutationFn: ({ id, input }) => gateway.reports.update(id, input),
    onSuccess: async (saved) => cache(saved),
  })
}

/** gateway.reports.copy. 변수 = { id(원본), meta }. */
export function useCopyReport(): Mutation<{ id: number; meta: SavedReportMeta }, SavedReport> {
  const cache = useCacheSaved()
  return useMutation<SavedReport, ApiError, { id: number; meta: SavedReportMeta }>({
    mutationFn: ({ id, meta }) => gateway.reports.copy(id, meta),
    onSuccess: async (saved) => cache(saved),
  })
}

/**
 * gateway.reports.saveReportLayout. 변수 = { id, layout, revision }. 성공: 상세 캐시를 응답으로 바꾸고 목록을 다시 받는다.
 * 실행 결과 캐시는 건드리지 않는다(배치만 바뀌었으므로 다시 조회하지 않는다). 보기 화면의 배치 자동 저장이 쓴다.
 */
export function useSaveReportLayout(): Mutation<{ id: number; layout: ReportLayout; revision: number }, SavedReport> {
  const queryClient = useQueryClient()
  return useMutation<SavedReport, ApiError, { id: number; layout: ReportLayout; revision: number }>({
    mutationFn: ({ id, layout, revision }) => gateway.reports.saveReportLayout(id, { layout, revision }),
    onSuccess: async (saved) => {
      queryClient.setQueryData(keys.savedReport(saved.id), saved)
      await queryClient.invalidateQueries({ queryKey: keys.savedReports, exact: true })
    },
  })
}

/**
 * 저장 리포트 상세를 서버에서 다시 읽어 캐시에 넣고 돌려준다(화면의 `useSavedReport`도 새 값으로 바뀐다).
 * 읽지 못하면 던진다. 보기 화면 자동 저장이 충돌(409)·권한 변경(403) 뒤 최신 값을 가져오는 데 쓴다.
 */
export function useReloadSavedReport(): (id: number) => Promise<SavedReport> {
  const queryClient = useQueryClient()
  return (id) => queryClient.fetchQuery({ queryKey: keys.savedReport(id), queryFn: () => gateway.reports.get(id), staleTime: 0 })
}

/** gateway.reports.remove(id). 성공: 목록 무효화, 그 리포트의 상세·실행 캐시 제거. */
export function useDeleteReport(): Mutation<number> {
  const queryClient = useQueryClient()
  return useMutation<void, ApiError, number>({
    mutationFn: (id) => gateway.reports.remove(id),
    onSuccess: async (_data, id) => {
      queryClient.removeQueries({ queryKey: keys.savedReport(id), exact: true })
      queryClient.removeQueries({ queryKey: keys.savedReportRun(id), exact: true })
      await queryClient.invalidateQueries({ queryKey: keys.savedReports, exact: true })
    },
  })
}

/** 저장 실패를 화면 표시용으로 가른다(이름 중복 / 저장 충돌 / 정의 위반 / 권한 / 없음 / 그 밖). */
export type SaveFailure =
  | { kind: 'name' | 'conflict' | 'forbidden' | 'notFound' | 'other'; message: string }
  | { kind: 'invalid'; message: string; issues: ReportIssue[] }

export function saveFailure(error: unknown): SaveFailure {
  const message = errorMessage(error)
  if (!(error instanceof ApiError)) return { kind: 'other', message }
  switch (error.kind) {
    case 'already-exists':
      return { kind: 'name', message }
    case 'invalid-state':
      return { kind: 'conflict', message }
    case 'invalid-report':
      return { kind: 'invalid', message, issues: error.problem?.reportErrors ?? [] }
    case 'forbidden':
      return { kind: 'forbidden', message }
    case 'not-found':
      return { kind: 'notFound', message }
    default:
      return { kind: 'other', message }
  }
}

/** 저장 직후 편집 화면이 이어 받는 것: 방금 조회한 결과와 저장 전에 선택돼 있던 디자이너 탭. */
export interface ReportHandoff {
  result: ReportResult
  tab: 'design' | 'result'
}

/**
 * 저장 직후 이동하는 편집 화면이 방금 조회한 결과를 이어 받는 통로(같은 설계라 다시 조회하지 않는다).
 * `peek`은 지우지 않고 읽고, 편집 화면이 쓴 뒤 `drop`한다.
 */
export function useReportHandoff(): {
  stash: (id: number, result: ReportResult, tab?: ReportHandoff['tab']) => void
  peek: (id: number) => ReportHandoff | undefined
  drop: (id: number) => void
} {
  const queryClient = useQueryClient()
  return {
    stash: (id, result, tab = 'design') => queryClient.setQueryData<ReportHandoff>(keys.savedReportHandoff(id), { result, tab }),
    peek: (id) => queryClient.getQueryData<ReportHandoff>(keys.savedReportHandoff(id)),
    drop: (id) => queryClient.removeQueries({ queryKey: keys.savedReportHandoff(id), exact: true }),
  }
}
