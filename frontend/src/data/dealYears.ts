import { useQuery } from '@tanstack/react-query'
import { gateway } from '../gateway'
import type { ApiError } from '../shared/api/problem'
import { selectableYears } from '../shared/model/yearOptions'
import type { DealYears } from '../shared/model/types'
import { keys } from './queryKeys'
import { NO_RETRY, type Query } from './result'
import { useToday } from './today'

/** gateway.deals.years(). 키 keys.dealYears(['deals'] 아래라 Deal 변경 때 함께 갱신된다). */
export function useDealYears(): Query<DealYears> {
  return useQuery<DealYears, ApiError>({ queryKey: keys.dealYears, queryFn: () => gateway.deals.years(), ...NO_RETRY })
}

/** 세 화면 공용: 연도 선택지(올해는 앱 시계)와 연도 조회 오류. 로딩·오류 때는 올해·내년(+current). */
export function useYearOptions(current?: number): { years: number[]; error: ApiError | null } {
  const { year } = useToday()
  const query = useDealYears()
  return { years: selectableYears(year, query.data?.earliestYear, current), error: query.error }
}
