import { useInfiniteQuery, useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { gateway } from '../gateway'
import { ApiError } from '../shared/api/problem'
import type { Page, PartnerDealOption, PartnerMeeting, PartnerMeetingInput, PartnerMeetingQuery } from '../shared/model/types'
import { keys } from './queryKeys'
import { NO_RETRY, type Mutation, type Query } from './result'

export const MEETING_PAGE_SIZE = 10

/** 서버가 위치와 함께 알려 준 입력 위반(`problem.itemErrors`). 다른 오류이면 빈 목록. */
export function itemErrorsOf(error: unknown): readonly { location: readonly (string | number)[]; message: string }[] {
  return error instanceof ApiError ? (error.problem?.itemErrors ?? []) : []
}

/** 서버 `total`을 기준으로 다음 페이지가 있는지 본다. */
function nextOffset(last: Page<PartnerMeeting>): number | undefined {
  const next = last.offset + last.items.length
  return last.items.length > 0 && next < last.total ? next : undefined
}

/**
 * gateway.partnerMeetings.list(query, offset, 10)를 무한 스크롤로 읽는다. 키 keys.partnerMeetingList.
 * 다른 사용자의 등록으로 쪽 경계가 밀려 겹친 행은 id로 한 번만 보인다.
 */
export function usePartnerMeetings(query: PartnerMeetingQuery) {
  const result = useInfiniteQuery<Page<PartnerMeeting>, ApiError>({
    queryKey: keys.partnerMeetingList(query),
    queryFn: ({ pageParam }) => gateway.partnerMeetings.list(query, pageParam as number, MEETING_PAGE_SIZE),
    initialPageParam: 0,
    getNextPageParam: nextOffset,
    ...NO_RETRY,
  })
  const pages = result.data?.pages ?? []
  const seen = new Set<number>()
  const items: PartnerMeeting[] = []
  for (const page of pages) {
    for (const item of page.items) {
      if (seen.has(item.id)) continue
      seen.add(item.id)
      items.push(item)
    }
  }
  return { ...result, items, total: pages.at(-1)?.total ?? 0, pageCount: pages.length }
}

/** gateway.partnerMeetings.dealOptions(company). company가 비면 비활성. 키 keys.partnerDealOptions. */
export function usePartnerDealOptions(company: string): Query<PartnerDealOption[]> {
  return useQuery<PartnerDealOption[], ApiError>({
    queryKey: keys.partnerDealOptions(company),
    queryFn: () => gateway.partnerMeetings.dealOptions(company),
    enabled: company !== '',
    ...NO_RETRY,
  })
}

/** 변경 뒤 목록은 처음(첫 쪽)부터 다시 읽는다: 불러 둔 쪽을 모두 다시 받지 않도록 목록 쿼리를 초기화한다. */
function useRefreshMeetings(): () => Promise<void> {
  const queryClient = useQueryClient()
  return async () => {
    // 초기화가 활성 목록의 첫 쪽을 한 번 다시 읽는다. 무효화를 더하면 같은 요청이 두 번 나가므로 하지 않는다.
    await queryClient.resetQueries({ queryKey: keys.partnerMeetingLists })
    // 비활성 Deal 선택지는 다음에 열 때 다시 읽게 표시만 한다.
    await queryClient.invalidateQueries({ queryKey: ['partnerMeetings', 'deal-options'], refetchType: 'none' })
  }
}

/** 일괄 등록. 성공: 목록을 처음부터 다시 로드한다. */
export function useCreateMeetings(): Mutation<PartnerMeetingInput[], PartnerMeeting[]> {
  const refresh = useRefreshMeetings()
  return useMutation<PartnerMeeting[], ApiError, PartnerMeetingInput[]>({
    mutationFn: (items) => gateway.partnerMeetings.create(items),
    onSuccess: () => refresh(),
  })
}

export function useUpdateMeeting(): Mutation<{ id: number; input: PartnerMeetingInput }, PartnerMeeting> {
  const refresh = useRefreshMeetings()
  return useMutation<PartnerMeeting, ApiError, { id: number; input: PartnerMeetingInput }>({
    mutationFn: ({ id, input }) => gateway.partnerMeetings.update(id, input),
    onSuccess: () => refresh(),
  })
}

export function useRemoveMeeting(): Mutation<number> {
  const refresh = useRefreshMeetings()
  return useMutation<void, ApiError, number>({
    mutationFn: (id) => gateway.partnerMeetings.remove(id),
    onSuccess: () => refresh(),
  })
}
