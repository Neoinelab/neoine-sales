import { formatKrwFull, formatKrwShort } from '../model/money'
import './ui.css'

/** 금액 표시: 짧은 표기(180M, 1.87B)에 hover title로 전체 금액. */
export function AmountText({ amount }: { amount: number }) {
  return (
    <span className="amount" title={formatKrwFull(amount)}>
      {formatKrwShort(amount)}
    </span>
  )
}
