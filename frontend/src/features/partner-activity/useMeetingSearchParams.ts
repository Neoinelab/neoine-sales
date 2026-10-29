import { useCallback, useMemo } from 'react'
import { useSearchParams } from 'react-router'
import { isDateValue } from '../../shared/model/dateText'
import { parseId } from '../../shared/model/ids'
import type { PartnerMeetingQuery, PartnerMeetingSort, SortOrder } from '../../shared/model/types'

const SORTS: readonly PartnerMeetingSort[] = ['meetingDate', 'partner', 'deal', 'content', 'author']

/** 화면에 쓰는 검색 조건(날짜는 올바른 값만 담는다). */
export interface MeetingConditions {
  partner: string
  deal: string
  content: string
  from: string
  to: string
  author: string
}

export const NO_CONDITIONS: MeetingConditions = { partner: '', deal: '', content: '', from: '', to: '', author: '' }

function sortOf(value: string | null): PartnerMeetingSort {
  return SORTS.find((s) => s === value) ?? 'meetingDate'
}

/** 조건·정렬은 URL이 진실이다. 기본값(미팅 날짜 내림차순)과 빈 조건은 쓰지 않는다. */
export function useMeetingSearchParams() {
  const [params, setParams] = useSearchParams()
  const conditions = useMemo<MeetingConditions>(() => {
    const from = params.get('from') ?? ''
    const to = params.get('to') ?? ''
    return {
      partner: params.get('partner') ?? '',
      deal: params.get('deal') ?? '',
      content: params.get('content') ?? '',
      from: isDateValue(from) ? from : '',
      to: isDateValue(to) ? to : '',
      author: parseId(params.get('author')) === undefined ? '' : (params.get('author') ?? ''),
    }
  }, [params])
  const sort = sortOf(params.get('sort'))
  const order: SortOrder = params.get('order') === 'asc' ? 'asc' : 'desc'

  const query = useMemo<PartnerMeetingQuery>(() => {
    const authorId = parseId(conditions.author)
    return {
      ...(conditions.partner.trim() && { partner: conditions.partner.trim() }),
      ...(conditions.deal.trim() && { deal: conditions.deal.trim() }),
      ...(conditions.content.trim() && { content: conditions.content.trim() }),
      ...(conditions.from && { dateFrom: conditions.from }),
      ...(conditions.to && { dateTo: conditions.to }),
      ...(authorId !== undefined && { authorId }),
      sort,
      order,
    }
  }, [conditions, sort, order])

  /** 주소를 새로 쓴다(조건 + 정렬). 기본값·빈 값은 생략한다. */
  const write = useCallback(
    (next: MeetingConditions, nextSort: PartnerMeetingSort, nextOrder: SortOrder) => {
      const out = new URLSearchParams()
      const text = { partner: next.partner.trim(), deal: next.deal.trim(), content: next.content.trim() }
      if (text.partner) out.set('partner', text.partner)
      if (text.deal) out.set('deal', text.deal)
      if (next.from) out.set('from', next.from)
      if (next.to) out.set('to', next.to)
      if (text.content) out.set('content', text.content)
      if (next.author) out.set('author', next.author)
      if (nextSort !== 'meetingDate') out.set('sort', nextSort)
      if (nextOrder === 'asc') out.set('order', 'asc')
      setParams(out)
    },
    [setParams],
  )

  const search = useCallback((next: MeetingConditions) => write(next, sort, order), [write, sort, order])
  const reset = useCallback(() => setParams(new URLSearchParams()), [setParams])
  /** 같은 열이면 방향을 바꾸고, 새 열은 오름차순부터. */
  const toggleSort = useCallback(
    (column: PartnerMeetingSort) => write(conditions, column, column === sort ? (order === 'asc' ? 'desc' : 'asc') : 'asc'),
    [write, conditions, sort, order],
  )

  return { conditions, query, sort, order, search, reset, toggleSort }
}
