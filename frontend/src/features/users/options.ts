import { useQuery } from '@tanstack/react-query'
import { useState } from 'react'
import { api, type Schemas } from '../../shared/api/client'
import { call } from '../../shared/api/problem'
import { useMe } from '../auth/hooks'

export type UserRef = Schemas['UserRef']

/** 사용자 선택 후보. 기본은 재직자만, 검색 필터는 퇴사자까지(includeResigned). */
export function useUserOptions(includeResigned: boolean) {
  const query = includeResigned ? { include_resigned: true } : {}
  return useQuery({
    queryKey: ['user-options', query],
    queryFn: () => call(api.GET('/api/v1/user-options', { params: { query } })),
    staleTime: 30_000,
  })
}

/**
 * 담당자·활동자 선택값. 기존 값(initialId)이 있으면 그 값, 아직 고르지 않았고 기존 값도 없으면
 * 로그인한 사용자(me.user_id)로 채운다. me가 늦게 도착해도 사용자가 고른 뒤에는 덮어쓰지 않는다.
 */
export function useUserChoice(initialId?: string) {
  const me = useMe()
  const [chosen, setChosen] = useState<string | null>(null)
  const value = chosen ?? initialId ?? me.data?.user_id ?? ''
  return [value, setChosen] as const
}
