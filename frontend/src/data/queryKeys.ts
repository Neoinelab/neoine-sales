import type {
  ActionQuery,
  ContactKind,
  ContactListQuery,
  CodeKind,
  DealListQuery,
  ForecastQuery,
  HistoryQuery,
  UserListFilter,
  UserOptionsQuery,
} from '../shared/model/types'

/**
 * TanStack Query 키(A-0 계약, 본문 확정). 무효화 규칙은 각 변경 훅의 주석을 따른다.
 * 계층: ['deals', ...]를 무효화하면 목록·상세·impact가 모두 갱신된다.
 */
export const keys = {
  me: ['me'] as const,
  authConfig: ['auth', 'config'] as const,
  setup: ['setup'] as const,
  deals: ['deals'] as const,
  dealList: (q: DealListQuery) => ['deals', 'list', q] as const,
  deal: (code: string) => ['deals', 'detail', code] as const,
  dealImpact: (code: string) => ['deals', 'impact', code] as const,
  contacts: ['contacts'] as const,
  contactCompanies: (kind: ContactKind) => ['contacts', 'companies', kind] as const,
  contactsByCompany: (kind: ContactKind, company: string) => ['contacts', 'by-company', kind, company] as const,
  contactList: (q: ContactListQuery) => ['contacts', 'list', q] as const,
  actions: (dealCode: string) => ['actions', dealCode] as const,
  actionList: (dealCode: string, q: ActionQuery) => ['actions', dealCode, q] as const,
  historyAll: ['history'] as const,
  history: (dealCode: string) => ['history', dealCode] as const,
  historyList: (dealCode: string, q: HistoryQuery) => ['history', dealCode, q] as const,
  attachments: (dealCode: string) => ['attachments', dealCode] as const,
  codes: ['codes'] as const,
  codeSet: ['codes', 'all'] as const,
  codeList: (kind: CodeKind) => ['codes', 'list', kind] as const,
  labels: ['labels'] as const,
  vendors: ['vendors'] as const,
  forecast: ['forecast'] as const,
  forecastSummary: (q: ForecastQuery) => ['forecast', q] as const,
  users: ['users'] as const,
  userList: (f: UserListFilter) => ['users', 'list', f] as const,
  userOptions: (q: UserOptionsQuery) => ['users', 'options', q] as const,
  directory: ['settings', 'directory'] as const,
  storage: ['settings', 'storage'] as const,
  alerts: ['alerts'] as const,
}
