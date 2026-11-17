import { useEffect, useState } from 'react'
import { useSearchParams } from 'react-router'
import type { Query } from '../../../data/result'
import type { DealAction } from '../../../shared/model/types'

export const ACTION_NOT_FOUND = 'Action을 찾을 수 없습니다.'

/**
 * 주소의 `action=<id>`(Comments 탭의 "Action 보기")를 읽어 그 Action의 상세 팝업을 열고 주소에서 지운다.
 * 목록을 받은 뒤에만 판단하며, 주소를 먼저 정리한 다음에 `open`을 부른다. 없는 id는 안내 문구를 돌려준다.
 */
export function useActionDeepLink(actions: Query<DealAction[]>, open: (action: DealAction) => void): string | null {
  const [params, setParams] = useSearchParams()
  const param = params.get('action')
  const [seen, setSeen] = useState<string | null>(null)
  const [waiting, setWaiting] = useState<DealAction | null>(null)
  const [missing, setMissing] = useState<string | null>(null)

  // 다음 링크를 받을 수 있게, 주소에서 action이 사라지면 기억을 비운다.
  if (param === null && seen !== null) setSeen(null)
  if (param !== null && param !== seen && actions.isSuccess && !actions.isFetching) {
    const id = Number(param)
    const found = Number.isSafeInteger(id) ? actions.data.find((a) => a.id === id) : undefined
    setSeen(param)
    setWaiting(found ?? null)
    setMissing(found ? null : ACTION_NOT_FOUND)
  }
  // 주소가 정리된 뒤에 팝업을 연다.
  if (param === null && waiting !== null) {
    setWaiting(null)
    open(waiting)
  }

  useEffect(() => {
    if (param === null || param !== seen) return
    setParams(
      (current) => {
        const next = new URLSearchParams(current)
        next.delete('action')
        return next
      },
      { replace: true },
    )
  }, [param, seen, setParams])

  return missing
}
