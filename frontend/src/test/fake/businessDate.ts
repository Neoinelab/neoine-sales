import { datePart, formatWithOffset, offsetMinutes } from '../../shared/model/dates'

/** 시각(ISO)을 서버 업무 시간대(= Fake 서버 시계의 오프셋)의 달력 날짜로 바꾼다. 브라우저 시간대는 쓰지 않는다. */
export function businessDate(iso: string, serverOffset: number): string {
  return datePart(formatWithOffset(Date.parse(iso), serverOffset))
}

/** Fake 서버 시계가 가리키는 오늘의 업무 날짜. */
export function businessToday(now: string): string {
  return businessDate(now, offsetMinutes(now))
}
