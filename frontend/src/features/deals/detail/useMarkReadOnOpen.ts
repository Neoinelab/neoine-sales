import { useEffect, useRef, useState } from 'react'
import { useMarkCommentsRead } from '../../../data/comments'
import type { Query } from '../../../data/result'
import type { DealComment } from '../../../shared/model/types'

const NONE: ReadonlySet<number> = new Set()

/**
 * Deal Owner가 Comment 목록을 열 때 읽지 않던 Comment를 한 번만 읽음 처리한다(열람당 1회, 화면이 다시 열리면 다시).
 * 목록을 새로 받은 뒤에만 보내고, 실패는 알리지 않는다(읽지 않음이 그대로이니 다음 열람에서 다시 보낸다).
 * 돌려주는 집합은 이번 열람에서 읽지 않다가 읽음 처리된 Comment id로, 화면이 "NEW"를 붙이는 데 쓴다.
 */
export function useMarkReadOnOpen(dealCode: string, comments: Query<DealComment[]>, isOwner: boolean): ReadonlySet<number> {
  const mark = useMarkCommentsRead()
  const sent = useRef(false)
  // null: 아직 목록을 받지 못했다. 처음 받은 순간의 읽지 않은 id를 한 번만 기록한다.
  const [unread, setUnread] = useState<ReadonlySet<number> | null>(null)
  const { data, isFetching } = comments

  if (isOwner && unread === null && data !== undefined && !isFetching) {
    setUnread(new Set(data.filter((c) => c.readAt === null).map((c) => c.id)))
  }

  useEffect(() => {
    if (unread === null || unread.size === 0 || sent.current) return
    sent.current = true
    mark.mutate({ dealCode, commentIds: [...unread] })
  }, [unread, dealCode, mark])

  return unread ?? NONE
}
