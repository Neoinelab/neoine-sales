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

/** Action 변경 공통 무효화: Action 목록, History, Deal(Next Action·최종 업데이트·Status), Forecast, Comment(등록·종료 Comment, Action 삭제 시 함께 삭제), 유형(새 유형·사용 수). */
function useInvalidateAction(): (dealCode: string) => Promise<void> {
  const invalidate = useInvalidate()
  return (dealCode) => invalidate(keys.actions(dealCode), keys.history(dealCode), keys.comments(dealCode), keys.deals, keys.forecast, keys.actionTypes, keys.licenseContracts)
}

/** gateway.actions.create(dealCode, input). input.statusChange가 있으면 Deal도 함께 바뀐다. */
export function useCreateAction(): Mutation<{ dealCode: string; input: ActionInput }, DealAction> {
  const invalidate = useInvalidateAction()
  return useMutation<DealAction, ApiError, { dealCode: string; input: ActionInput }>({
    mutationFn: ({ dealCode, input }) => gateway.actions.create(dealCode, input),
    onSuccess: (_action, { dealCode }) => invalidate(dealCode),
    // 기준 행이 그사이 바뀐 409·403 뒤에는 Action 목록을 다시 받아, 대화상자를 다시 열면 최신 기준 행이 보이게 한다(입력은 폼 상태라 유지된다).
    onError: (error, { dealCode }) => {
      if (error.status === 409 || error.status === 403) void invalidate(dealCode)
    },
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

export function useUpdateActionDueDate(): Mutation<{ dealCode: string; actionId: number; dueDate: string }, DealAction> {
  const invalidate = useInvalidateAction()
  return useMutation<DealAction, ApiError, { dealCode: string; actionId: number; dueDate: string }>({
    mutationFn: async ({ dealCode, actionId, dueDate }) => {
      const action = (await gateway.actions.list(dealCode, {})).find((item) => item.id === actionId)
      if (!action) throw new Error('Action을 찾을 수 없습니다.')
      if (!action.nextAction) throw new Error('Next Action 없이 Due Date를 입력할 수 없습니다.')
      return gateway.actions.update(actionId, {
        type: { id: action.typeId },
        progress: action.progress ?? '',
        nextAction: action.nextAction,
        dueDate,
      })
    },
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

/** gateway.actions.changeNextActionStatus(actionId, input). 성공 무효화는 create와 같다(종료 Comment·목록의 Next Action 요약이 바뀐다). */
export function useChangeNextActionStatus(): Mutation<{ dealCode: string; actionId: number; input: NextActionStatusInput }, DealAction> {
  const invalidate = useInvalidateAction()
  return useMutation<DealAction, ApiError, { dealCode: string; actionId: number; input: NextActionStatusInput }>({
    mutationFn: ({ actionId, input }) => gateway.actions.changeNextActionStatus(actionId, input),
    onSuccess: (_action, { dealCode }) => invalidate(dealCode),
  })
}
