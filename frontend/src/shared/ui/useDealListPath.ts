import { useLocation } from 'react-router'
import { useMe } from '../../data/auth'
import { rememberedListPath, sanitizeListSearch } from '../model/dealListMemory'

/**
 * 화면 안에서 목록으로 돌아갈 경로. 이동할 때마다 다시 읽어 최신 기억을 반영한다.
 * 목록 화면(`/deals`) 안에서는 저장된 기억 대신 현재 URL 조건을 쓴다.
 */
export function useDealListPath(): string {
  const { pathname, search } = useLocation()
  const userId = useMe().data?.id
  if (pathname === '/deals') {
    const clean = sanitizeListSearch(search)
    return clean === '' ? '/deals' : `/deals?${clean}`
  }
  return rememberedListPath(userId)
}
