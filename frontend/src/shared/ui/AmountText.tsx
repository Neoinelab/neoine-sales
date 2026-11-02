import { formatWon } from '../model/money'
import './ui.css'

/** 금액 표시: 원 단위 콤마 숫자(단위는 항목 이름에 표시). */
export function AmountText({ amount }: { amount: number }) {
  return <span className="amount">{formatWon(amount)}</span>
}
