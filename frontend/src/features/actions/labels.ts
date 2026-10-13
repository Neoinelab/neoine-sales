import type { Schemas } from '../../shared/api/client'

export type ActionType = Schemas['ActionType']

export const ACTION_TYPES: { value: ActionType; label: string }[] = [
  { value: 'call', label: '통화' },
  { value: 'meeting', label: '미팅' },
  { value: 'email', label: '이메일' },
  { value: 'demo', label: '데모' },
  { value: 'proposal', label: '제안' },
  { value: 'negotiation', label: '협상' },
  { value: 'contract', label: '계약' },
  { value: 'other', label: '기타' },
]

export function actionLabel(type: ActionType): string {
  return ACTION_TYPES.find((t) => t.value === type)?.label ?? type
}

export const ACTION_SORTS: { value: Schemas['DealActionSort']; label: string }[] = [
  { value: 'acted_at_desc', label: '진행일 최신순' },
  { value: 'due_date_asc', label: '계획일 빠른순' },
  { value: 'due_date_desc', label: '계획일 늦은순' },
]
