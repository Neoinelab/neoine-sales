import { useMutation, useQuery } from '@tanstack/react-query'
import { gateway } from '../gateway'
import type { ApiError } from '../shared/api/problem'
import type { ActionInput, ActionQuery, ActionUpdateInput, DealAction, NextActionStatusInput } from '../shared/model/types'
import { keys } from './queryKeys'
import { NO_RETRY, useInvalidate, type Mutation, type Query } from './result'

/** gateway.actions.list(dealCode, query). 키 keys.actionList. dealCode가 undefined면 비활성. */
export function useActions(dealCode: string | undefined, query: ActionQuery = {}): Query<DealAction[]> {
  return useQuery<DealAction[], ApiError>({
    queryKey: keys.actionList(dealCode ?? '', query),
    queryFn: () => gateway.actions.list(dealCode ?? '', query),
    enabled: dealCode !== undefined,
    ...NO_RETRY,
  })
}

/** Action 변경 공통 무효화: Action 목록, History, Deal(Next Action·최종 업데이트·Status), Forecast, 유형(새 유형·사용 수). */
function useInvalidateAction(): (dealCode: string) => Promise<void> {
  const invalidate = useInvalidate()
  return (dealCode) => invalidate(keys.actions(dealCode), keys.history(dealCode), keys.deals, keys.forecast, keys.actionTypes)
}

/** gateway.actions.create(dealCode, input). input.statusChange가 있으면 Deal도 함께 바뀐다. */
export function useCreateAction(): Mutation<{ dealCode: string; input: ActionInput }, DealAction> {
  const invalidate = useInvalidateAction()
  return useMutation<DealAction, ApiError, { dealCode: string; input: ActionInput }>({
    mutationFn: ({ dealCode, input }) => gateway.actions.create(dealCode, input),
    onSuccess: (_action, { dealCode }) => invalidate(dealCode),
  })
}

/** gateway.actions.update(actionId, input). 성공 무효화는 create와 같다(dealCode는 변수로 받는다). */
export function useUpdateAction(): Mutation<{ dealCode: string; actionId: number; input: ActionUpdateInput }, DealAction> {
  const invalidate = useInvalidateAction()
  return useMutation<DealAction, ApiError, { dealCode: string; actionId: number; input: ActionUpdateInput }>({
    mutationFn: ({ actionId, input }) => gateway.actions.update(actionId, input),
    onSuccess: (_action, { dealCode }) => invalidate(dealCode),
  })
}

/** gateway.actions.remove(actionId). 성공 무효화는 create와 같다. */
export function useRemoveAction(): Mutation<{ dealCode: string; actionId: number }> {
  const invalidate = useInvalidateAction()
  return useMutation<void, ApiError, { dealCode: string; actionId: number }>({
    mutationFn: ({ actionId }) => gateway.actions.remove(actionId),
    onSuccess: (_result, { dealCode }) => invalidate(dealCode),
  })
}

/** gateway.actions.changeNextActionStatus(actionId, input). 성공 무효화는 create와 같다(Memo·목록의 Next Action 요약이 바뀐다). */
export function useChangeNextActionStatus(): Mutation<{ dealCode: string; actionId: number; input: NextActionStatusInput }, DealAction> {
  const invalidate = useInvalidateAction()
  return useMutation<DealAction, ApiError, { dealCode: string; actionId: number; input: NextActionStatusInput }>({
    mutationFn: ({ actionId, input }) => gateway.actions.changeNextActionStatus(actionId, input),
    onSuccess: (_action, { dealCode }) => invalidate(dealCode),
  })
}
