import { useUpdateDeal } from '../../../data/deals'
import type { DealPatch } from '../../../shared/model/types'

/**
 * 필드 하나(또는 연락처 블록 하나)의 변경을 Deal 수정으로 저장하고 성공 알림을 남긴다.
 * 실패는 그대로 던져 InlineEdit이 오류를 보이고 편집을 유지하게 한다(재시도 가능).
 */
export function useDealPatch(code: string, onNotice: (message: string) => void) {
  const update = useUpdateDeal()
  return {
    pending: update.isPending,
    async save(patch: DealPatch, message: string) {
      await update.mutateAsync({ code, patch })
      onNotice(message)
    },
  }
}
