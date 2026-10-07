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
