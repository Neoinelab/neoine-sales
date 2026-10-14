import type { Deal } from '../features/deals/hooks'
import { userRef } from './authFixtures'

/** 딜 상세 화면 테스트가 함께 쓰는 API 응답 예시(생성된 스키마의 필드 이름과 같다). */
export const DETAIL_DEAL = {
  id: 'd-1',
  code: 'DEAL-001',
  name: 'ERP 구축',
  owner: userRef('u-2', '박영업'),
  vendor: 'SAP',
  solution: 'S/4',
  revenue_amount: '150000000',
  revenue_currency: 'KRW',
  revenue_date: '2026-06-30',
  customer_id: 'c-1',
  partner_id: 'p-1',
  stage: 'prospecting',
  created_at: '2026-01-01T00:00:00Z',
  updated_at: '2026-01-01T00:00:00Z',
} satisfies Deal

export const DETAIL_CUSTOMER = {
  id: 'c-1',
  company_name: '네오인',
  contact_name: '김고객',
  contact_title: '부장',
  email: 'kim@neoine.example',
  phone: '02-1234-5678',
  employee_count: 120,
  notes: '',
  created_at: '2026-01-01T00:00:00Z',
  updated_at: '2026-01-01T00:00:00Z',
}

export const DETAIL_PARTNER = {
  id: 'p-1',
  company_name: '한빛',
  contact_name: '이파트',
  contact_title: '이사',
  email: 'lee@hanbit.example',
  phone: '031-987-6543',
  created_at: '2026-01-01T00:00:00Z',
  updated_at: '2026-01-01T00:00:00Z',
}

export const stageChange = (over: Record<string, unknown> = {}) => ({
  id: 'h-1',
  deal_id: 'd-1',
  from_stage: 'prospecting',
  to_stage: 'introduction',
  reason: null,
  changed_by: userRef('u-2', '개발 사용자(sales)'),
  changed_at: '2026-03-02T01:00:00Z',
  ...over,
})

export const listPage = (items: unknown[], limit = 20) => ({ body: { items, offset: 0, limit } })
