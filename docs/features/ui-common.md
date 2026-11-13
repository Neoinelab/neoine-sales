# 공통 입력·표시 컴포넌트   (feature 코드: UI, 상태: 확정(2026-11-11 사용자 확인))

> 이 문서는 **이미 구현된 동작**을 정본 명세로 옮긴 것입니다(2026-11-11). 근거는 작업 트리의 코드(`shared/ui/{DateInput,AmountInput,AmountText,ComboBox,MultiCheckSelect,Modal,ConfirmDialog,Pager,useInfiniteScroll,SortableHeader,Tabs,Notice,useLocationNotice,fields}.tsx|.ts`, `shared/ui/kvGrid.css`, `index.css`의 `.content`, `shared/model/{dateText,money}.ts`)와 가드 테스트(`test/dateInputGuard.test.ts`·`moneyUnitGuard.test.ts`), 빈 첫 실행 교차 화면 테스트(`test/emptyState.test.tsx`), 안내서(`docs/user-guide.html` 5.1 "날짜 입력" 상자, 금액 입력 설명)이며 문구·속성은 코드에서 그대로 옮겼습니다. 배경은 하네스 이력 2026-10-28 "공통 날짜 입력" 행과 2026-11-03 "금액 원 단위 통일" 행입니다. 범위 경계·소유는 2026-11-11 사용자 결정으로 정했습니다: 주인 없는 shared 부품(확인 대화상자·탭·알림·화면 이동 알림·금액 표시·기본 필드·CSS·빈 첫 실행)은 UI가 가지고 `UserSelect`·`PeriodField` 등은 원래 feature가 가지며, 금액 판정·문구 정본은 UI-R13·R14, 차트 축 금액은 UI-R16, 빈 첫 실행은 UI-R36, CSS 정적 점검은 UI-059·060, 확인 대화상자의 진행 중 취소·Esc 허용은 현행대로(UI-R29)입니다. 결정 목록은 계획(`artifacts/10-analysis/ui-plan.md`)에 있습니다.

## 1. 개요

- 목적: 여러 화면이 함께 쓰는 입력·표시 부품의 동작을 한 곳에 정한다. 각 화면 feature는 "이 칸은 `DateInput`(UI-R1~R11)"처럼 이 문서의 규칙 번호를 가리키고, 그 칸의 필수 여부·문구·저장 시점만 자기 문서에 둔다.
- 사용자(역할): 로그인한 모든 역할(부품 자체에는 권한이 없다). 가드 규칙(UI-R11, UI-R17)의 행위자는 개발자·CI다.
- 범위
  - 날짜 입력 `DateInput`과 규칙 함수 `shared/model/dateText.ts`, native 날짜 칸 사용 금지 가드
  - 금액 입력 `AmountInput`, 금액 표시 `AmountText`, 금액 함수 `shared/model/money.ts`(읽기·검증 문구·표시·차트 축 단축·항목 이름), 천원 잔재 가드
  - 콤보박스 `ComboBox`, 다중 선택 `MultiCheckSelect`
  - 모달 `Modal`(포커스·Esc·Tab·겹친 모달), 확인 대화상자 `ConfirmDialog`
  - 페이저 `Pager`, 무한 스크롤 `useInfiniteScroll`, 정렬 머리글 `SortableHeader`
  - 탭 `Tabs`, 알림 줄 `Notice`, 화면 이동 알림 `useLocationNotice`
  - 기본 입력 필드 `fields.tsx`(`TextField`·`TextArea`·`SelectField`·`CheckboxField`)
  - 키·값 격자 `kvGrid.css`, 본문 영역 여백(`index.css` `.content`)
  - 업무 데이터가 없는 첫 실행에서 화면들이 오류 없이 빈 상태를 보이는 것(교차 화면 확인)
- 범위 밖(다른 feature)
  - 각 화면이 부품을 쓰는 규칙(필수 여부, 칸 이름, 저장·검색·URL 반영 시점, 화면 고유 문구) → 각 feature(예: DE-R26, DD-R31, DL-R25, AC-R24·R25, NA-R26, PA-R31·PA-R33~R39, RQ-R46·R47)
  - 빈 상태 문구 자체("등록된 Deal이 없습니다." 등) → 그 화면의 feature(DL, FC, CT, CD, CL, US, DE, AC, AT, DD). UI는 "데이터가 없어도 화면이 오류 없이 뜬다"만 가진다(UI-R36)
  - 오류 배너 `ErrorBanner`·문제 응답 해석 → PL(PL-R37, PL-R39), 상단 메뉴·`Layout` → PL, 사용자 메뉴 `UserMenu` → ME
  - 사용자 선택 `UserSelect` → DE·US, 기간 선택 `PeriodField`·`periodChoice` → NA, 경고·코드 배지(`Badges`·`RiskBadge`) → RK, 키워드 검색 줄 `KeywordSearchBar` → CT
  - 업무 날짜·서버 시계·시각 표기(`shared/format.ts`, `useToday`) → TM
  - `shared/model`의 업무 규칙 파일(`risk`·`sync`·`history`·`forecastKeys`·`quarterSet`·`dealListMemory`·`yearOptions`·`catalogChoice`·`contactRules`·`permissions` 등) → 각 소유 feature
- 관련 화면·메뉴: 메뉴 없음(모든 화면에서 쓰는 부품). backend 대상 없음.

## 2. 명세 (SDD)

### 2.1 용어

| 용어 | 뜻 |
| --- | --- |
| 날짜 칸 글자 | 텍스트 칸에 보이는 `yyyy.mm.dd` 모양 글자(입력 중에는 `2026.1`처럼 덜 친 모양일 수 있음) |
| ISO 값 | `YYYY-MM-DD` 문자열. 부모 컴포넌트·API가 쓰는 날짜 값 |
| 확정 | 날짜 칸을 벗어나거나(blur) Enter를 눌러 글자를 정리하는 순간 |
| 숨은 날짜 칸 | 달력을 띄우려고 `DateInput` 안에 둔 브라우저 `type="date"` 칸 |
| 금액 글자 | 금액 칸에 보이는 원 단위 콤마 숫자(`1,234,567`) |
| 안전 정수 상한 | 2^53−1 = 9,007,199,254,740,991(`Number.MAX_SAFE_INTEGER`, 서버 금액 상한과 같음) |
| 맨 위 모달 | 열린 모달 중 다른 열린 모달을 안에 품지 않은 것 가운데 가장 늦게 연 것 |
| 표지(sentinel) | 무한 스크롤 목록 아래에 둔 빈 요소. 화면 가까이 오면 다음 페이지를 읽는다 |

### 2.2 데이터 모델

저장 데이터 없음(화면 부품). 함수 결과 모양:
- `DateParse` = `{kind: 'empty'}` | `{kind: 'valid', iso}` | `{kind: 'incomplete'}` | `{kind: 'invalid'}` | `{kind: 'out_of_range'}`
- `formatAmountInput(raw, caret)` → `{text, caret}`
- `ComboOption` = `{value, label?, description?, id?}`

### 2.3 비즈니스 규칙

날짜 입력 (`DateInput`, `dateText.ts`)
- **UI-R1** 모양: 텍스트 칸은 `type="text"`, `inputmode="numeric"`, placeholder `yyyymmdd`, `autocomplete="off"`이고 `maxlength`가 없다(붙여넣기를 브라우저가 자르지 않게). 옆에 달력 버튼(`type="button"`, 이름 "<칸 이름> 달력 열기", 칸 이름이 없으면 "달력 열기". 칸 이름은 `aria-label` 또는 바깥 `<label>` 글자)과 숨은 날짜 칸(`tabindex=-1`, `aria-hidden="true"`, `min="1900-01-01"`, `max="2999-12-31"`, 클래스 `date-input-native`, `display:none` 아님)이 있다. 받은 `id`·`name`·`required`는 텍스트 칸에, `disabled`는 텍스트 칸·달력 버튼·숨은 칸 모두에 준다. `inputRef`는 텍스트 칸을 가리키고, `autoFocus`면 텍스트 칸에 `data-autofocus`를 붙인다(모달이 이 칸에 먼저 포커스, UI-R26). 바깥 `<label for>`로 칸을 찾을 수 있다. 텍스트 칸을 벗어나면(확정 뒤) `onBlur`를 부른다.
- **UI-R2** 입력 정리: 칠 때마다(붙여넣기 포함) 글자를 연(4)·월(2)·일(2) 칸으로 다시 만든다. 숫자는 지금 칸에 넣고, 칸이 차면 다음 칸으로 넘긴다(월 칸에 세 번째 숫자를 치면 일 칸으로: `2026.123` → `2026.12.3`). 일 칸이 찬 뒤의 숫자는 버린다(`2026112099` → `2026.11.20`). `.`·`-`·`/`는 지금 칸이 비어 있지 않을 때 다음 칸으로 넘기고 이어진 구분자는 하나로 본다(`2026..11` → `2026.11`). 그 밖의 글자(공백·문자)는 버린다(`2026a11` → `2026.11`, ` 2026-11-20` → `2026.11.20`, `2026. 11. 20.` → `2026.11.20`, `  2026 / 11 / 20  ` → `2026.11.20`). 마지막이 구분자이고 채운 칸이 1~2개면 끝의 `.`를 남긴다(`2026.` → `2026.`, `2026.1.` → `2026.1.`). 한 자리 월 뒤에 일을 이어 치려면 구분자를 넣거나 월을 두 자리로 친다(안내서 5.1).
- **UI-R3** 캐럿: 글자를 다시 만든 뒤 캐럿은 다시 만들기 전 캐럿 앞에 있던 숫자 개수만큼의 숫자 뒤에 둔다(끝이었으면 끝). 그래서 가운데에 숫자를 넣거나 점을 Backspace로 지워도 캐럿이 끝으로 튀지 않는다.
- **UI-R4** 확정 정리: 확정할 때 글자가 `연4자리.월1~2자리.일1~2자리`면 월·일을 두 자리로 채운다(`2026.1.5` → `2026.01.05`, `2026.11.5` → `2026.11.05`). 그 밖의 모양(`2026.1`, `2026`, `2026.`, `2026.1.`, `26.1.5`, 빈 글자)은 그대로 둔다.
- **UI-R5** 판정: 앞뒤 공백을 뺀 글자가 비면 `empty`, 정확히 `dddd.dd.dd`가 아니면 `incomplete`, 월이 1~12가 아니거나 일이 그 달 일수(2월은 윤년 29일 — 4로 나누어지고 100으로 나누어지지 않거나 400으로 나누어지는 해 — 아니면 28일, 4·6·9·11월 30일, 그 밖 31일)를 벗어나면 `invalid`, 연이 1900~2999 밖이면 `out_of_range`, 그 밖은 `valid`(ISO 값)다. 없는 날짜 판정이 범위 판정보다 먼저다. `isDateValue(value)`는 값이 정확히 `YYYY-MM-DD`이고 `valid`일 때만 참이다(빈 값, `2026.11.20`, `2026-1-5`, 끝 공백은 거짓).
- **UI-R6** 부모에게 넘기는 값: 칠 때마다와 확정 때, 글자가 `valid`면 ISO 값, `empty`면 `''`, 그 밖이면 **글자 그대로**를 `onChange`로 넘긴다(넘길 값이 지금 `value`와 같으면 부르지 않는다). 그래서 부모는 `isDateValue(value)`가 거짓이고 값이 비어 있지 않으면 덜 쳤거나 틀린 날짜임을 알고 저장·검색·URL 반영을 막는다(막는 시점과 칸별 규칙은 각 feature). `dateValueError(value)`는 부모용 문구 함수로, 빈 값·올바른 ISO는 null, 그 밖은 UI-R7과 같은 문구다(ISO 모양도 점 표기로 바꿔 판정: `2026-02-30` → "없는 날짜입니다."). `isoToDateText`는 ISO를 점 표기로 바꾸고 그 밖 글자는 그대로 둔다.
- **UI-R7** 칸 문구: 확정한 뒤에만 보이고 다시 치기 시작하면 숨긴다. `incomplete` "날짜를 yyyymmdd 형식으로 입력하세요.", `invalid` "없는 날짜입니다.", `out_of_range` "1900.01.01부터 2999.12.31 사이로 입력하세요.", `empty`는 문구 없음. 문구는 칸 아래 `role="alert"` 문단이고 텍스트 칸은 `aria-invalid="true"`, `aria-describedby`는 부모가 준 설명 id와 문구 id를 함께 담는다. 부모가 `error`를 주면 자체 문구가 없을 때 그 문구를 같은 자리에 보인다(자체 문구가 우선). `quiet`면 자체 문구와 그로 인한 `aria-invalid`를 내지 않고, 부모가 `invalid`로 `aria-invalid`를 켠다(부모가 문구를 따로 보이는 화면용).
- **UI-R8** Enter: 텍스트 칸에서 Enter를 누르면 먼저 `onKeyDown`을 부르고, 확정(UI-R4·R6)한 뒤 `onEnter`가 있으면 폼 기본 동작(제출)을 막고 `onEnter(확정한 값)`을 부른다(올바른 날짜는 ISO, 틀린 날짜는 글자 그대로, 빈 칸은 `''` — 다음 칸으로 넘길지는 부모가 정한다). `onEnter`가 없으면 폼 기본 동작을 그대로 둔다. 한글 등 입력 조합 중의 Enter는 무시한다.
- **UI-R9** 달력: 달력 버튼을 누르면 숨은 날짜 칸의 `showPicker()`를 부른다. 함수가 없거나 예외를 던지면 숨은 칸에 포커스를 주고 클릭한다. 버튼을 누르는 동안 텍스트 칸의 포커스를 빼앗지 않는다(마우스 누름 기본 동작 막음). 숨은 칸의 값은 글자가 `valid`일 때 그 ISO 값, 아니면 빈 값이다(달력이 현재 값으로 열림). 달력에서 날짜를 고르면 글자를 `yyyy.mm.dd`로 바꾸고 `onChange(ISO)`, 텍스트 칸으로 포커스, `onPicked(ISO)` 순이다. 고른 값이 비면 글자를 비우고 `onChange('')`다. 1900~2999 밖 등 `isDateValue`가 거짓인 값은 무시한다.
- **UI-R10** 부모 값 따라가기: 부모가 `value`를 바꾸면, 지금 글자가 넘길 값(UI-R6)과 새 값이 다를 때만 글자를 새 값으로 바꾼다(ISO는 점 표기, 그 밖 글자는 그대로 — 예: `2026.13.4`). 그래서 부모가 받은 값을 되돌려 줘도 입력 중인 글자(`2026.1`, `2026.1.5`)는 그대로이고, 부모가 비우거나 다른 날짜로 바꾸면 따라간다.
- **UI-R11** native 날짜 칸 금지(가드): 앱 소스(`` 아래 `.ts`·`.tsx`, 테스트 파일과 `test/` 제외)에서 native 날짜 칸은 `shared/ui/DateInput.tsx`에만 있다. 금지: `<input>`의 리터럴 `type="date"`(`'date'`, `{'date'}`, `{"date"}`, `` {`date`} ``, 화살표 함수 속성 뒤 포함), 검토 목록 밖의 동적 `type={…}`, 객체 리터럴 `type: 'date'`, 명시한 날짜 아닌 `type` 없이 spread한 `<input {...props}>`. 검토 목록(`features/admin/contacts/ContactForm.tsx`, `features/deals/detail/InlineControl.tsx`, `features/deals/form/FormField.tsx`, `shared/ui/fields.tsx`)은 동적 `type`을 쓸 수 있으나 `'date'`를 언급하면 `<DateInput`도 있어야 한다. 가드는 100개 넘는 실제 소스를 검사한다.

금액 (`AmountInput`, `AmountText`, `money.ts`)
- **UI-R12** 금액 입력: `AmountInput`은 `type="text"`, `inputmode="numeric"`이고 단위 글자를 그리지 않는다(단위는 항목 이름 — UI-R15). 칠 때마다(붙여넣기 포함) 숫자 아닌 글자를 버리고, 앞자리 0을 지우되(`007` → `7`) `0` 하나는 남기며, 세 자리마다 콤마를 넣은 글자를 `onChange`로 넘긴다(`1234567` → `1,234,567`, `12a3.4 5` → `12,345`, `1,500,000.50` → `150,000,050`). 캐럿은 캐럿 앞 숫자 개수(지운 앞자리 0만큼 뺌)만큼의 숫자 뒤에 둔다: `1,234`의 첫 숫자 뒤에 `9`를 치면 `19,234`·캐럿 2, 콤마만 Backspace로 지우면 글자 `1,234` 그대로·캐럿 1, 버리는 글자(`x`)를 치면 글자·캐럿 그대로다.
- **UI-R13** 금액 읽기(`parseAmountInput`): 앞뒤 공백과 콤마를 뺀 글자가 숫자만이고 1 이상 안전 정수 상한 이하이면 그 원 값, 아니면 null이다(빈 값, 공백, `0`, `1.5`, `-3`, `abc`, `1 000`, `1e3`, `9007199254740992`는 null). `isValidAmount(value)`는 숫자형이고 안전 정수이며 1 이상일 때만 참이다(`'3'`, `1.2`, `0`, 상한+2는 거짓).
- **UI-R14** 금액 문구(`amountInputError`): 읽을 수 있으면 null. 0이 아닌 숫자만인데 상한을 넘으면 "매출금액은 9,007,199,254,740,991원 이하로 입력하세요.", 그 밖(빈 값·0·형식)은 "매출금액은 1원 이상의 정수를 입력하세요.". 금액 판정(UI-R13)과 이 문구의 정본은 UI이고 화면 문서(DE-R26 등)는 이 번호를 가리킨다(2026-11-11 결정).
- **UI-R15** 금액 표시: `formatWon`은 원 값을 반올림 없이 세 자리 콤마로 보인다(`1870000000` → `1,870,000,000`, `0` → `0`, 상한 → `9,007,199,254,740,991`). `AmountText`는 같은 글자를 `amount` 클래스로 보인다. 항목 이름 상수는 금액 `금액(단위:원)`, 매출 확정 금액 `매출금액(단위:원, 실제 값)`이고 상한 상수는 안전 정수 상한이다.
- **UI-R16** 차트 축 금액(`formatWonAxis`): 0(−0 포함)은 `0`. 절댓값 1억 이상은 억 단위 소수 1자리(`1870000000` → `18.7억`, `123400000000` → `1,234억`), 1만 이상은 만 단위 소수 1자리(`50000000` → `5,000만`, `15000` → `1.5만`)이되 만 단위로 반올림한 값이 10,000만이 되면 억으로 올린다(`99999999` → `1억`, `99995000` → `9,999.5만`, `9999999` → `1,000만`). 1만 미만은 콤마 숫자(`9999` → `9,999`). 음수는 같은 규칙에 `-`를 붙인다. Dashboard·Reports 차트가 함께 쓰는 함수이고 정본은 이 규칙이다(2026-11-11 결정).
- **UI-R17** 천원 잔재 금지(가드): 앱 소스(테스트 파일, `test/`, `gateway/contract/` 제외, 생성 타입 `shared/api/schema.d.ts` 포함)에 `천원`, `toThousandWon`, `formatThousandWon`, `isThousandWonColumn`, `THOUSAND_WON_MAX`, `isSameShownAmount`, `krw_thousand`가 없다. `money.ts`는 천원 함수를 내보내지 않는다.

콤보박스 (`ComboBox`)
- **UI-R18** 모양: 라벨(`visibleLabel`이 있으면 보이는 글자는 그것이고 접근 이름은 `label`), 입력 칸 `role="combobox"`·`aria-autocomplete="list"`·`aria-expanded`·`aria-controls`·`autocomplete="off"`, 열렸을 때 목록 `role="listbox"`(이름 `label`)과 항목 `role="option"`(글자는 `label`, 없으면 `value`, `description`은 오른쪽 보조 글자). `error`가 있으면 칸 아래 `role="alert"` 문구와 `aria-invalid`·`aria-describedby`, `hint`가 있으면 칸 아래 안내 문구. `inputRef`는 입력 칸을 가리킨다. `visibleLabel`이 없으면 입력 칸에 `aria-label`을 두지 않는다. `required`면 입력 칸에 `required` 속성을 두고 루트(`field combo`)에 `required` 클래스를 붙인다(`*` 표시는 쓰는 화면의 CSS가 그린다 — 예: Deal 폼 DE-R22, 2026-11-12). `required`가 없으면 둘 다 없다.
- **UI-R19** 열기·닫기: 포커스(`openOnFocus` 기본 참), 클릭(이미 포커스가 있어도), 입력, ↑·↓(닫혀 있으면 열기만)로 연다. `openOnFocus`가 거짓이면 포커스만으로는 열지 않는다(모달 첫 칸 등). 보일 후보가 0개면 목록을 그리지 않는다. 칸을 벗어나면 닫는다.
- **UI-R20** 후보: 입력이 비었거나 입력이 어떤 후보의 `value`와 대소문자 무시로 같으면 전체 후보(원래 순서), 아니면 표시 글자에 입력이 대소문자 무시로 들어 있는 후보만 보인다.
- **UI-R21** 고르기·직접 입력: 항목을 마우스로 누르거나 ↑·↓로 옮긴 뒤(끝에서 처음으로 돈다, `aria-activedescendant`가 그 항목) Enter를 누르면 `onChange(value)`, `onSelectOption(항목)`을 부르고 닫는다. 직접 친 글자는 `transform`(있으면)을 거쳐 `onChange`만 부르고 `onSelectOption`은 부르지 않는다(목록에 없는 값도 그대로 입력된다). 목록이 열린 채 Esc를 누르면 목록만 닫고 이벤트 전파를 막는다(감싼 모달이 닫히지 않음). 목록이 닫혀 있을 때의 Esc는 막지 않는다.

다중 선택 (`MultiCheckSelect`)
- **UI-R22** 모양: 라벨 글자와 버튼(접근 이름 "<라벨> <요약>", `aria-expanded`, 열린 동안만 `aria-controls` = 패널 id, `aria-haspopup` 없음). 처음엔 닫혀 있다. `hint`가 있으면 버튼 아래 늘 보이는 안내이고 버튼 `aria-describedby`가 가리킨다(`describedBy`와 함께). 열리면 패널 `role="group"`(이름 라벨) 안에 후보 순서대로 체크박스(`name`, `value`, 선택된 것만 체크)와 끝에 지우기 버튼(글자 `clearLabel`, 기본 "전체"). 후보가 비면 체크박스가 없다.
- **UI-R23** 동작: 체크박스를 누르면 `onToggle(value, 새 체크 상태)`를 부르고 패널은 열린 채다. 지우기 버튼은 `onClear`만 부른다. 버튼을 다시 누르거나, Esc(닫고 포커스를 버튼으로), 컴포넌트 밖 포인터 누름, 포커스가 컴포넌트 밖으로 나감(포커스는 간 곳에 둠)으로 닫힌다. 패널 안 포인터 누름·포커스 이동으로는 닫히지 않는다.
- **UI-R24** 소유: 선택 목록과 버튼 요약 글자(`summary`)는 호출자가 정한다(요약 문구 규칙은 각 feature, 예: Deal 목록 Forecast 요약은 DL). 다중 선택은 열림 상태만 가진다. Esc는 이벤트 전파를 막지 않는다(모달 안에서 쓰는 곳이 없다).

모달 (`Modal`, `ConfirmDialog`)
- **UI-R25** 모양: 배경(`modal-backdrop`) 안에 `role="dialog"`, `aria-modal="true"`, 이름 = 제목(h2), `footer`가 있으면 아래 버튼 영역, `wide`면 넓은 폭. 모달은 스스로 사라지지 않는다(호출자가 `onClose`에서 상태를 바꿔 없앤다). 배경을 눌러도 닫히지 않는다.
- **UI-R26** 포커스: 열 때 `data-autofocus`가 붙은 요소, 없으면 첫 포커스 가능 요소(링크, 비활성 아닌 버튼·입력·선택·여러 줄 칸, `tabindex`가 −1이 아닌 요소), 그것도 없으면 대화상자 자체로 포커스를 옮긴다. 닫히면(사라지면) 열기 전 포커스가 있던 요소로 돌려준다.
- **UI-R27** Esc와 겹친 모달: Esc는 맨 위 모달만 받아 `onClose`를 부르고 전파를 막는다. 안쪽 모달이 바깥 모달의 DOM 안에 그려져도 안쪽이 맨 위다. 안쪽이 닫히면 다음 Esc는 바깥이 받는다. 사라진 모달은 목록에서 빠져, 뒤에 연 모달의 Esc가 그대로 동작한다.
- **UI-R28** Tab 가두기: 맨 위 모달 안에서 마지막 요소의 Tab은 첫 요소로, 첫 요소의 Shift+Tab은 마지막 요소로 돈다. 포커스가 모달 밖에 있으면 Tab은 첫 요소로 간다. 포커스 가능 요소가 없으면 Tab을 막는다. 바깥 모달의 요소로는 가지 않는다.
- **UI-R29** 확인 대화상자: `Modal` 위에 문구와 추가 내용(`children`), 버튼 "취소"(`cancelLabel`)와 확인(`confirmLabel`, 기본 "확인", `danger`면 위험 스타일 `danger`, 아니면 `primary`). `busy` 또는 `confirmDisabled`면 확인 버튼만 비활성이고 "취소" 버튼과 Esc는 계속 `onCancel`이다. 진행 중에 닫기를 막을지는 호출 화면이 정한다(현행 문서화, 2026-11-11 결정).

목록 넘기기
- **UI-R30** 페이저: `nav`(이름 "페이지") 안에 "이전", "<번호> 페이지"(번호 = ⌊offset/limit⌋+1), "다음". "이전"은 offset 0이면 비활성이고 누르면 `onChange(max(0, offset−limit))`. "다음"은 `total`이 있으면 `offset+limit ≥ total`일 때, 없으면 받은 건수 `count`(없으면 0)가 `limit`보다 작을 때 비활성이고 누르면 `onChange(offset+limit)`.
- **UI-R31** 무한 스크롤: 돌려준 ref를 붙인 표지가 화면에서 200px 안으로 들어오면, 그 순간의 최신 상태로 다음 페이지가 있고 읽는 중이 아닐 때만 `fetchNextPage`를 한 번 부른다. 불러온 페이지 수가 바뀌면 관찰을 다시 걸어 화면에 남아 있는 표지가 한 번 더 신호를 낸다. 화면을 떠나면 관찰을 끊는다. 브라우저에 `IntersectionObserver`가 없으면 아무것도 하지 않는다(오류 없음).
- **UI-R32** 정렬 머리글: `th`(`scope="col"`). `onSort`가 있으면 글자는 버튼(클래스 `th-sort`)이고 누르면 `onSort`를 부른다. 정렬 중인 열(`active`)이면 `aria-sort`(`ascending`/`descending`)와 버튼 `data-dir`(`asc`/`desc`)을 둔다. 정렬 중이 아니거나 `onSort`가 없으면 `aria-sort`가 없고, `onSort`가 없으면 버튼 없이 글자만이다.

탭·알림
- **UI-R33** 탭: `tablist`(이름 `label`) 안 탭 버튼마다 `aria-selected`, 선택된 탭만 `tabindex=0`(나머지 −1), 패널 `tabpanel`의 이름은 선택된 탭이다. 탭을 누르거나 → / ←(끝에서 처음으로 돈다)·Home·End를 누르면 그 탭을 선택하고 포커스를 옮긴다. 아이콘은 `aria-hidden`이라 이름에 들어가지 않는다.
- **UI-R34** 알림 줄: `kind`가 `error`면 `role="alert"`, 그 밖(`info` 기본, `success`, `warning`)은 `role="status"`. `onClose`가 있을 때만 "닫기" 버튼이 있고 누르면 `onClose`.
- **UI-R35** 화면 이동 알림: 다른 화면이 이동 상태 `{notice: 문자열}`로 넘긴 알림을 돌려주고, 곧바로 기록 상태를 비운다(경로·검색어는 그대로 replace) — 새로 고침·뒤로 가기에서 다시 나오지 않는다. 문자열이 아니거나 빈 문자열이면 알림이 없다. 같은 화면에 새 알림이 오면 그것으로 바꾼다. 돌려주는 설정 함수로 화면의 다른 알림과 같은 자리를 쓴다.

빈 첫 실행·레이아웃·기본 필드
- **UI-R36** 업무 데이터가 없는 첫 실행(로그인 계정·기본 코드·기본 BANT Label만 있음)에서도 화면이 오류 없이 빈 상태를 보이고 첫 업무를 시작할 수 있다: Deal 목록(전체 연도 / 기본 연도), Forecast, 연락처 관리, Deal 관리(기본 코드·Label), 사용자 관리, Deal 등록 → Action 추가 → 첨부 → Deal History. 각 문구는 소유 feature 규칙이다. 교차 화면 빈 상태 확인(UI-056~058)은 UI가 가진다(2026-11-11 결정).
- **UI-R37** 키·값 격자(`kvGrid.css`): 글자 크기를 선언하지 않는다. 격자는 `repeat(auto-fill, …/ 3)`로 최대 3열이고 좁으면 1열로 접힌다. 행(`.kv-row`·`.field`)은 `var(--kv-label-w) minmax(0, 1fr)` 두 열, `align-items: baseline`, `min-width: 0`이고 값(`dd`)은 `overflow-wrap: anywhere`다. 콤보 목록에 `grid-column`을 주는 선택자는 `.kv-grid > `로 시작하는 것뿐이다(값 칸 안 콤보에는 주지 않음).
- **UI-R38** 본문 영역 여백(2026-10-26): `.content`의 좌우 여백은 모든 화면 너비 규칙에서 5%이고(`padding: <n>px 5%`) 최대 너비 제한이 없다.
- **UI-R39** 기본 필드(`fields.tsx`): `TextField`·`TextArea`·`SelectField`·`CheckboxField`는 라벨 글자가 칸의 접근 이름이고 값이 바뀌면 `onChange(새 값)`(체크박스는 체크 상태)를 부른다. `TextField`의 `type="date"`는 native 칸이 아니라 `DateInput`(id `<name>-date`, `aria-label` = 라벨)이다. `invalid`면 `aria-invalid`를 켠다. `TextArea`는 3줄이다.

### 2.4 상태와 전이

- `DateInput` 문구: 숨김 →(확정, 글자가 비지 않고 `valid` 아님)→ 보임 →(다시 입력)→ 숨김.
- `ComboBox`·`MultiCheckSelect`: 닫힘 ⇄ 열림(UI-R19·R21·R23).
- 모달 스택: 열림 순서 목록. 맨 위만 Esc·Tab을 받는다(UI-R27).

### 2.5 권한

권한 판정 없음(부품은 역할과 무관). 화면별 가드는 PL(PL-R29)과 각 feature 2.5.

### 2.6 API 계약

없음(frontend 전용, 서버 호출 없음).

### 2.7 화면 동작

UI-R1~UI-R39.

### 2.8 오류와 메시지

| 상황 | 문구 | 규칙 |
| --- | --- | --- |
| 날짜를 덜 침(확정 뒤) | 날짜를 yyyymmdd 형식으로 입력하세요. | UI-R7 |
| 없는 날짜 | 없는 날짜입니다. | UI-R7 |
| 1900~2999 밖 | 1900.01.01부터 2999.12.31 사이로 입력하세요. | UI-R7 |
| 금액 빈 값·0·형식 | 매출금액은 1원 이상의 정수를 입력하세요. | UI-R14 |
| 금액 상한 초과 | 매출금액은 9,007,199,254,740,991원 이하로 입력하세요. | UI-R14 |

화면 글자: "달력 열기", "<칸 이름> 달력 열기", placeholder "yyyymmdd", "전체"(다중 선택 지우기 기본), "확인"·"취소", "이전"·"다음"·"<n> 페이지"(nav "페이지"), "닫기", 항목 이름 "금액(단위:원)"·"매출금액(단위:원, 실제 값)".

## 3. Business use case

### UI-UC1 날짜 넣기
- 행위자: 로그인한 모든 역할(날짜 칸이 있는 화면)
- 사전 조건: 화면에 `DateInput` 칸이 있음
- 기본 흐름: `20261120`을 친다 → `2026.11.20`으로 보이고 부모는 `2026-11-20`을 받는다(UI-R2, R6) → Enter로 다음 칸으로 가거나 칸을 벗어난다(UI-R4, R8)
- 대안: 구분자를 넣거나 붙여넣는다(UI-R2), 달력 버튼으로 고른다(UI-R9), 한 자리 월·일은 확정 때 채워진다(UI-R4)
- 예외: 덜 쳤거나 없는 날짜·범위 밖이면 확정 뒤 문구가 보이고 부모는 그 값을 쓰지 않는다(UI-R5~R7)
- 결과: 부모가 올바른 ISO 값 또는 빈 값만 저장·검색·URL에 쓴다

### UI-UC2 금액 넣기
- 행위자: 로그인한 모든 역할(금액 칸이 있는 화면)
- 사전 조건: 화면에 `AmountInput` 칸이 있음
- 기본 흐름: 숫자를 친다 → 콤마가 자동으로 들어가고 캐럿이 제자리다(UI-R12) → 저장 때 부모가 원 값으로 읽는다(UI-R13)
- 대안: 콤마·문자가 섞인 글자를 붙여넣으면 숫자만 남는다(UI-R12)
- 예외: 0·빈 값·상한 초과면 부모가 문구를 보인다(UI-R14)
- 결과: 원 단위 정수가 저장된다. 표시는 콤마 숫자, 차트 축은 억·만 단축(UI-R15, R16)

### UI-UC3 목록에서 고르거나 직접 입력하기
- 행위자: 로그인한 모든 역할
- 사전 조건: 화면에 `ComboBox` 칸이 있음
- 기본 흐름: 칸을 누르면 후보가 보인다 → 글자를 치면 후보가 걸러진다 → 마우스나 ↑↓·Enter로 고른다(UI-R18~R21)
- 대안: 목록에 없는 값을 그대로 친다, Esc로 목록만 닫는다(모달은 유지)
- 결과: 칸 값이 정해지고 고른 경우 호출자가 고른 항목을 안다

### UI-UC4 여러 값 고르기
- 행위자: 로그인한 모든 역할
- 기본 흐름: 버튼을 눌러 패널을 연다 → 체크박스를 켜고 끈다 → 바깥을 누르거나 Esc로 닫는다(UI-R22~R24)
- 대안: 지우기 버튼으로 모두 지운다
- 결과: 호출자가 선택 목록과 버튼 요약을 바꾼다

### UI-UC5 대화상자에서 확인·입력하기
- 행위자: 로그인한 모든 역할
- 기본 흐름: 대화상자가 열리고 첫 칸에 포커스 → Tab은 대화상자 안에서만 돈다 → 확인 또는 취소·Esc → 연 버튼으로 포커스가 돌아온다(UI-R25~R29)
- 대안: 대화상자 위에 다른 대화상자가 열리면 Esc는 위의 것만 닫는다(UI-R27)
- 예외: 진행 중이거나 호출자 조건이 맞지 않으면 확인 버튼이 꺼져 있다(UI-R29)

### UI-UC6 긴 목록 넘기기·정렬하기
- 행위자: 로그인한 모든 역할
- 기본 흐름: 페이저로 이전·다음 페이지(UI-R30) 또는 끝까지 스크롤해 다음 묶음(UI-R31), 머리글을 눌러 정렬(UI-R32)
- 결과: 호출자가 offset·페이지·정렬을 바꿔 다시 읽는다

### UI-UC7 탭과 알림 보기
- 행위자: 로그인한 모든 역할
- 기본 흐름: 탭을 누르거나 화살표로 옮긴다(UI-R33), 저장 결과 알림을 보고 닫는다(UI-R34), 다른 화면에서 넘어온 알림을 한 번 본다(UI-R35)

### UI-UC8 데이터가 없는 첫 실행
- 행위자: 최초 설정을 마친 사용자
- 사전 조건: 업무 데이터 없음(계정·기본 코드·기본 Label만)
- 기본 흐름: 목록·Forecast·관리 화면이 오류 없이 빈 상태를 보인다 → 첫 Deal을 등록하고 Action·첨부를 더한다(UI-R36)

### UI-UC9 공통 부품 사용 지키기
- 행위자: 개발자·CI(단위 테스트 게이트)
- 기본 흐름: 소스를 검사해 native 날짜 칸이 `DateInput` 밖에 없고(UI-R11) 천원 잔재가 없음을(UI-R17) 확인한다
- 예외: 위반 파일이 있으면 테스트가 그 파일 이름과 규칙 이름으로 실패한다

## 4. BDD 테스트 케이스

예시 칸 이름 "견적일", 금액 칸 "금액", 콤보 후보 한빛상사·하나솔루션·대한소프트(보조 글자 "3명"), 다중 선택 라벨 "Forecast"와 후보 Pipeline·Best·Commit. 모든 케이스는 Vitest 화면·함수 테스트이며, 부품을 감싸는 작은 호스트 컴포넌트(부모 상태)와 `vi.fn` 콜백을 쓰고 서버 통신이 없다(빈 첫 실행 케이스만 Fake 게이트웨이 `seed: 'empty'`). 콜백 호출 여부·인자는 부품의 결과(부모에게 넘기는 값)라 단언한다.

| 코드 | 케이스 | 규칙·UC | 층 | 테스트 위치 |
| --- | --- | --- | --- | --- |
| UI-001 | yyyymmdd 8자리를 치면 yyyy.mm.dd로 보이고 ISO 값을 넘긴다 | UI-R2, UI-R6, UI-UC1 | frontend | `shared/model/dateText.test.ts`, `shared/ui/DateInput.test.tsx` |
| UI-002 | 구분자를 넣어 치거나 붙여넣은 날짜는 공백·끝 점을 버리고 같은 표기로 정리된다 | UI-R2, UI-UC1 | frontend | `shared/model/dateText.test.ts`, `shared/ui/DateInput.test.tsx` |
| UI-003 | 칸을 넘친 숫자는 다음 칸으로 가고 일 칸을 넘친 숫자·문자·겹친 구분자는 버린다 | UI-R2, UI-UC1 | frontend | `shared/model/dateText.test.ts` |
| UI-004 | 덜 친 날짜·없는 날짜는 글자 그대로, 지운 칸은 빈 값으로 넘긴다 | UI-R6, UI-UC1 | frontend | `shared/ui/DateInput.test.tsx` |
| UI-005 | 확정하면 한 자리 월·일을 0으로 채우고 다른 모양은 그대로 둔다 | UI-R4, UI-UC1 | frontend | `shared/model/dateText.test.ts`, `shared/ui/DateInput.test.tsx` |
| UI-006 | 날짜 판정은 경계·윤년·없는 날짜·범위 밖·덜 친 모양·빈 값을 구분한다 | UI-R5, UI-UC1 | frontend | `shared/model/dateText.test.ts` |
| UI-007 | 입력 중에는 문구가 없고 덜 친 날짜로 칸을 벗어나면 형식 문구와 aria-invalid가 보인다 | UI-R7, UI-UC1 | frontend | `shared/ui/DateInput.test.tsx` |
| UI-008 | 없는 날짜·범위 밖 날짜는 칸을 벗어나거나 Enter를 누르면 각 문구를 보인다 | UI-R7, UI-UC1 | frontend | `shared/ui/DateInput.test.tsx` |
| UI-009 | 날짜를 고치면 문구가 사라지고 빈 칸에는 문구가 없다 | UI-R7, UI-UC1 | frontend | `shared/ui/DateInput.test.tsx` |
| UI-010 | 부모 오류 문구는 자체 문구가 없을 때만 보이고 부모 설명과 함께 칸에 연결된다 | UI-R7, UI-UC1 | frontend | `shared/ui/DateInput.test.tsx` |
| UI-011 | quiet이면 자체 문구를 내지 않고 부모 invalid로만 aria-invalid가 켜진다 | UI-R7, UI-UC1 | frontend | `shared/ui/DateInput.test.tsx` |
| UI-012 | 부모용 dateValueError는 칸과 같은 문구를 돌려준다 | UI-R6, UI-R7, UI-UC1 | frontend | `shared/model/dateText.test.ts` |
| UI-013 | Enter는 확정한 값으로 onEnter를 부르고 폼을 제출하지 않으며 onEnter가 없으면 제출된다 | UI-R8, UI-UC1 | frontend | `shared/ui/DateInput.test.tsx` |
| UI-014 | 입력 조합 중의 Enter는 확정·onEnter를 하지 않는다 | UI-R8, UI-UC1 | frontend | `shared/ui/DateInput.test.tsx` |
| UI-015 | 달력 버튼은 숨은 칸의 달력을 열고 지원하지 않거나 거부되면 숨은 칸을 눌러 연다 | UI-R9, UI-UC1 | frontend | `shared/ui/DateInput.test.tsx` |
| UI-016 | 달력에서 고른 날짜는 칸에 보이고 값·포커스·onPicked로 이어지며 달력은 현재 값으로 열린다 | UI-R9, UI-UC1 | frontend | `shared/ui/DateInput.test.tsx` |
| UI-017 | 달력이 범위 밖 값을 주면 무시하고 빈 값을 주면 칸을 비운다 | UI-R9, UI-UC1 | frontend | `shared/ui/DateInput.test.tsx` |
| UI-018 | 숨은 칸은 Tab 순서·접근성 트리 밖이고 달력 버튼은 칸 이름을 따르며 폼을 제출하지 않는다 | UI-R1, UI-R9, UI-UC1 | frontend | `shared/ui/DateInput.test.tsx` |
| UI-019 | 부모가 값을 바꾸거나 비우면 표시가 따라가고 입력 중 글자·틀린 글자는 그대로 둔다 | UI-R10, UI-UC1 | frontend | `shared/ui/DateInput.test.tsx` |
| UI-020 | 글자를 다시 만들어도 캐럿은 입력한 숫자 뒤에 남는다 | UI-R3, UI-UC1 | frontend | `shared/ui/DateInput.test.tsx` |
| UI-021 | 날짜 텍스트 칸의 속성과 id·name·required·disabled·바깥 label·inputRef·autoFocus·onBlur | UI-R1, UI-UC1 | frontend | `shared/ui/DateInput.test.tsx` |
| UI-022 | native 날짜 칸은 DateInput 밖 소스에 없다(가드) | UI-R11, UI-UC9 | frontend | `test/dateInputGuard.test.ts` |
| UI-023 | 금액 칸은 치는 동안 세 자리 콤마를 넣고 숫자 아닌 글자를 버린다 | UI-R12, UI-UC2 | frontend | `shared/ui/AmountInput.test.tsx` |
| UI-024 | 콤마를 다시 넣어도 캐럿은 같은 숫자 뒤에 남는다 | UI-R12, UI-UC2 | frontend | `shared/model/money.test.ts`, `shared/ui/AmountInput.test.tsx` |
| UI-025 | 앞자리 0은 지우고 붙여넣은 소수점 금액은 숫자만 남는다 | UI-R12, UI-UC2 | frontend | `shared/model/money.test.ts`, `shared/ui/AmountInput.test.tsx` |
| UI-026 | 금액 칸에는 단위 글자가 없고 항목 이름이 원 단위를 가진다 | UI-R12, UI-R15, UI-UC2 | frontend | `shared/model/money.test.ts`, `shared/ui/AmountInput.test.tsx` |
| UI-027 | 금액 읽기는 1~2^53−1 정수만 원으로 읽고 나머지는 거절한다 | UI-R13, UI-UC2 | frontend | `shared/model/money.test.ts` |
| UI-028 | 금액 문구는 상한 초과와 그 밖의 위반을 구분한다 | UI-R14, UI-UC2 | frontend | `shared/model/money.test.ts` |
| UI-029 | 금액 표시는 반올림 없는 콤마 숫자다 | UI-R15, UI-UC2 | frontend | `shared/model/money.test.ts`, `shared/ui/AmountText.test.tsx` |
| UI-030 | 차트 축 금액은 반올림 뒤 억·만 단위를 정해 줄인다 | UI-R16, UI-UC2 | frontend | `shared/model/money.test.ts` |
| UI-031 | 천원 표기·변환의 잔재가 소스에 없다(가드) | UI-R17, UI-UC9 | frontend | `test/moneyUnitGuard.test.ts` |
| UI-032 | 콤보박스는 접근 이름이 있고 포커스·클릭에 후보 목록을 연다 | UI-R18, UI-R19, UI-UC3 | frontend | `shared/ui/ComboBox.test.tsx` |
| UI-033 | openOnFocus가 거짓이면 포커스만으로 열지 않고 클릭·입력·↓로 연다 | UI-R19, UI-UC3 | frontend | `shared/ui/ComboBox.test.tsx` |
| UI-034 | 입력으로 후보를 대소문자 무시 부분 일치로 거르고 후보와 같은 값이면 전체를 보인다 | UI-R20, UI-UC3 | frontend | `shared/ui/ComboBox.test.tsx` |
| UI-035 | 마우스나 ↑↓·Enter로 고르면 값을 채우고 선택을 알리고 닫으며 직접 입력은 선택 알림이 없다 | UI-R21, UI-UC3 | frontend | `shared/ui/ComboBox.test.tsx` |
| UI-036 | 모달 안 콤보박스의 Esc는 열린 목록만 닫고 모달은 남는다 | UI-R21, UI-R27, UI-UC3 | frontend | `shared/ui/ComboBox.test.tsx` |
| UI-037 | 콤보박스의 오류·안내·보이는 라벨·transform·inputRef | UI-R18, UI-R21, UI-UC3 | frontend | `shared/ui/ComboBox.test.tsx` |
| UI-038 | 다중 선택 버튼은 라벨+요약 이름으로 닫혀 있고 열면 후보 순서의 체크박스와 지우기 버튼이다 | UI-R22, UI-R24, UI-UC4 | frontend | `shared/ui/MultiCheckSelect.test.tsx` |
| UI-039 | 체크·해제는 onToggle로 알리고 패널이 남으며 지우기는 onClear이고 글자를 바꿀 수 있다 | UI-R22, UI-R23, UI-UC4 | frontend | `shared/ui/MultiCheckSelect.test.tsx` |
| UI-040 | 다중 선택은 Esc·바깥 누름·포커스 이탈·버튼 재클릭으로 닫히고 패널 안 이동으로는 닫히지 않는다 | UI-R23, UI-UC4 | frontend | `shared/ui/MultiCheckSelect.test.tsx` |
| UI-041 | 다중 선택의 aria-expanded·aria-controls·안내 문구 연결 | UI-R22, UI-UC4 | frontend | `shared/ui/MultiCheckSelect.test.tsx` |
| UI-042 | 모달은 제목 이름의 aria-modal 대화상자로 열리고 data-autofocus 또는 첫 칸에 포커스한다 | UI-R25, UI-R26, UI-UC5 | frontend | `shared/ui/Modal.test.tsx` |
| UI-043 | Esc로 닫으면 연 버튼으로 포커스가 돌아오고 배경을 눌러도 닫히지 않는다 | UI-R25, UI-R26, UI-R27, UI-UC5 | frontend | `shared/ui/Modal.test.tsx` |
| UI-044 | Tab·Shift+Tab은 모달 안에서 돈다 | UI-R28, UI-UC5 | frontend | `shared/ui/Modal.test.tsx` |
| UI-045 | 겹친 모달에서 Esc·Tab은 맨 위만 받고 안쪽이 닫히면 바깥이 받는다 | UI-R27, UI-R28, UI-UC5 | frontend | `shared/ui/Modal.test.tsx` |
| UI-046 | 확인 대화상자는 문구·확인·취소를 보이고 Esc는 취소이며 busy·confirmDisabled면 확인만 꺼진다 | UI-R29, UI-UC5 | frontend | `shared/ui/Modal.test.tsx` |
| UI-047 | 페이저는 첫 페이지에서 이전이 꺼지고 페이지 번호와 이전·다음 offset을 낸다 | UI-R30, UI-UC6 | frontend | `shared/ui/Pager.test.tsx` |
| UI-048 | 페이저는 total이 있으면 그것으로, 없으면 받은 건수로 마지막 페이지를 정한다 | UI-R30, UI-UC6 | frontend | `shared/ui/Pager.test.tsx` |
| UI-049 | 표지가 200px 안에 들어오면 다음 페이지를 한 번 요청한다 | UI-R31, UI-UC6 | frontend | `shared/ui/useInfiniteScroll.test.tsx` |
| UI-050 | 다음 페이지가 없거나 읽는 중이면 요청하지 않고 교차 순간의 최신 상태를 쓴다 | UI-R31, UI-UC6 | frontend | `shared/ui/useInfiniteScroll.test.tsx` |
| UI-051 | 페이지가 늘면 다시 관찰하고 떠나면 끊으며 IntersectionObserver가 없어도 오류가 없다 | UI-R31, UI-UC6 | frontend | `shared/ui/useInfiniteScroll.test.tsx` |
| UI-052 | 정렬 머리글은 정렬 중인 열에만 aria-sort·방향을 두고 누르면 onSort, onSort가 없으면 글자만이다 | UI-R32, UI-UC6 | frontend | `shared/ui/SortableHeader.test.tsx` |
| UI-053 | 탭은 선택 상태·패널 이름을 갖고 클릭·화살표·Home·End로 옮기며 선택 탭만 Tab 순서에 든다 | UI-R33, UI-UC7 | frontend | `shared/ui/Tabs.test.tsx` |
| UI-054 | 알림 줄은 오류만 alert이고 onClose가 있을 때만 닫기 버튼이 있다 | UI-R34, UI-UC7 | frontend | `shared/ui/Notice.test.tsx` |
| UI-055 | 화면 이동 알림은 한 번 보이고 기록 상태를 비우며 주소는 그대로이고 문자열이 아니면 없다 | UI-R35, UI-UC7 | frontend | `shared/ui/useLocationNotice.test.tsx` |
| UI-056 | 데이터가 없으면 Deal 목록은 전체 연도에서 등록 안내와 등록 링크, 기본 연도에서는 조건 문구다 | UI-R36, UI-UC8 | frontend | `test/emptyState.test.tsx` |
| UI-057 | 데이터가 없어도 Forecast·연락처는 빈 문구이고 기본 코드·Label·로그인 계정은 보인다 | UI-R36, UI-UC8 | frontend | `test/emptyState.test.tsx` |
| UI-058 | 빈 상태에서 첫 Deal 등록 → Action 추가 → 첨부 → History가 이어진다 | UI-R36, UI-UC8 | frontend | `test/emptyState.test.tsx` |
| UI-059 | 키·값 격자 CSS는 글자 크기 없이 최대 3열·라벨 고정 열·긴 값 줄바꿈을 선언한다 | UI-R37 | frontend | `shared/ui/kvGrid.test.ts` |
| UI-060 | 본문 영역은 모든 너비에서 좌우 5% 여백이고 최대 너비가 없다 | UI-R38 | frontend | `shared/ui/layoutStyle.test.ts` |
| UI-061 | 기본 필드는 라벨이 접근 이름이고 TextField 날짜 형식은 DateInput이다 | UI-R39, UI-UC1 | frontend | `shared/ui/fields.test.tsx` |
| UI-062 | required 콤보박스는 입력 칸 required 속성과 루트 required 클래스를 가진다 | UI-R18, UI-UC1 | frontend | `shared/ui/ComboBox.required.test.tsx` |
### UI-001 yyyymmdd 8자리를 치면 yyyy.mm.dd로 보이고 ISO 값을 넘긴다
- Given 빈 "견적일" 날짜 칸(부모 상태와 연결)
- When `20261120`을 친다(또는 `20270601`을 쳐서 부모 상태를 화면에 보인다)
- Then 칸에 `2026.11.20`이 보이고 부모가 마지막으로 받은 값은 `2026-11-20`이다(부모 상태 표시는 `2027-06-01`). 함수 기준: `2026` → `2026`, `20261` → `2026.1`, `202611` → `2026.11`, `2026112` → `2026.11.2`, `20261120` → `2026.11.20`

### UI-002 구분자를 넣어 치거나 붙여넣은 날짜는 공백·끝 점을 버리고 같은 표기로 정리된다
- Given 빈 "견적일" 칸
- When `2026-11-20`, `2026/11/20`, `2026.11.20`, ` 2026-11-20`, `2026. 11. 20.`, `2026-11-20 `, `  2026 / 11 / 20  `를 각각 붙여넣는다
- Then 모두 `2026.11.20`으로 보이고 부모는 `2026-11-20`을 받는다. 함수 기준 `2026.` → `2026.`, `2026.1.` → `2026.1.`, `2026.1.5` → `2026.1.5`

### UI-003 칸을 넘친 숫자는 다음 칸으로 가고 일 칸을 넘친 숫자·문자·겹친 구분자는 버린다
- When 글자 `202611201`, `2026112099`, `2026.123`, `2026a11`, `2026..11`, 빈 글자를 정리한다
- Then 각각 `2026.11.20`, `2026.11.20`, `2026.12.3`, `2026.11`, `2026.11`, 빈 글자다

### UI-004 덜 친 날짜·없는 날짜는 글자 그대로, 지운 칸은 빈 값으로 넘긴다
- Given 빈 칸, 그리고 값이 `2026-11-20`인 칸
- When 빈 칸에 `202611`을, 다른 빈 칸에 `20261304`를 치고, 값이 있는 칸을 모두 지운다
- Then 부모가 받은 값은 `2026.11`, `2026.13.04`(칸 표시도 같음), `''`이다

### UI-005 확정하면 한 자리 월·일을 0으로 채우고 다른 모양은 그대로 둔다
- Given 빈 칸
- When `2026.1.5`를 친 뒤 Tab으로 칸을 벗어난다
- Then 치는 동안은 `2026.1.5`, 벗어난 뒤 `2026.01.05`이고 부모는 `2026-01-05`를 받는다. 함수 기준 `2026.11.5` → `2026.11.05`, `2026.11.20`은 그대로, `2026.1`·`2026`·`2026.`·`2026.1.`·빈 글자·`26.1.5`는 그대로

### UI-006 날짜 판정은 경계·윤년·없는 날짜·범위 밖·덜 친 모양·빈 값을 구분한다
- When 다음 글자를 판정한다
- Then `2026.11.20`·`1900.01.01`·`2999.12.31`·`2024.02.29`는 valid(ISO), `2025.02.29`·`2026.02.30`·`2026.13.01`·`2026.00.10`·`2026.10.00`·`2026.04.31`은 invalid, `1899.12.31`·`3000.01.01`은 out_of_range, `2026.1`·`2026.11.2`·`2026`·`2026.`·`2026.11.`·`202`는 incomplete, 빈 글자·공백만은 empty다. `isDateValue`는 `2026-11-20`·`1900-01-01`·`2999-12-31`·`2024-02-29`만 참이고 빈 값·`2026-13-01`·`2025-02-29`·`1899-12-31`·`3000-01-01`·`2026.11.20`·`2026-1-5`·`2026-11-20 `·`abc`는 거짓이다

### UI-007 입력 중에는 문구가 없고 덜 친 날짜로 칸을 벗어나면 형식 문구와 aria-invalid가 보인다
- Given 빈 칸
- When `2026.1`을 친 상태를 보고, 이어서 Tab으로 벗어난다
- Then 치는 동안 alert와 `aria-invalid`가 없고, 벗어난 뒤 "날짜를 yyyymmdd 형식으로 입력하세요."와 `aria-invalid="true"`다

### UI-008 없는 날짜·범위 밖 날짜는 칸을 벗어나거나 Enter를 누르면 각 문구를 보인다
- When `20261304`를 치고 벗어나고, `18991231`을 치고 벗어나고, `20260230`을 치고 Enter를 누른다
- Then 각각 "없는 날짜입니다.", "1900.01.01부터 2999.12.31 사이로 입력하세요.", "없는 날짜입니다."가 보인다

### UI-009 날짜를 고치면 문구가 사라지고 빈 칸에는 문구가 없다
- Given `20260230`을 치고 벗어나 문구가 보이는 칸, 그리고 빈 칸
- When 앞 칸을 지우고 `20260228`을 친 뒤 벗어나고, 빈 칸은 포커스만 줬다가 벗어난다
- Then 앞 칸의 문구와 `aria-invalid`가 사라지고, 빈 칸에는 문구가 없다

### UI-010 부모 오류 문구는 자체 문구가 없을 때만 보이고 부모 설명과 함께 칸에 연결된다
- Given 부모 `error` "견적 제출일을 입력하세요."인 칸, 부모 `error` "부모 오류"인 칸, 부모 설명 id `hint`인 칸
- When 첫 칸은 그대로 보고, 둘째 칸에 `2026.1`을 치고 벗어나고, 셋째 칸에 `2026.1`을 치고 벗어난다
- Then 첫 칸은 부모 문구와 `aria-invalid="true"`, 둘째 칸은 자체 형식 문구만 보이고 "부모 오류"는 없으며, 셋째 칸의 `aria-describedby`에는 `hint`와 문구 요소 id가 모두 있다

### UI-011 quiet이면 자체 문구를 내지 않고 부모 invalid로만 aria-invalid가 켜진다
- Given `quiet`인 칸 A, `quiet`이고 `invalid`인 칸 B
- When 둘 다 `2026.1`을 치고 벗어난다
- Then 두 칸 모두 alert 문구가 없고, A는 `aria-invalid`가 없으며 B는 `aria-invalid="true"`다

### UI-012 부모용 dateValueError는 칸과 같은 문구를 돌려준다
- When 값 `''`, `2026-11-20`, `2026.1`, `2026.11.2`, `2026.13.04`, `2026-02-30`, `1899.12.31`, `3000-01-01`을 판정한다
- Then 앞 둘은 null, 다음 둘은 "날짜를 yyyymmdd 형식으로 입력하세요.", 다음 둘은 "없는 날짜입니다.", 마지막 둘은 "1900.01.01부터 2999.12.31 사이로 입력하세요."다. `isoToDateText`는 `2026-11-20` → `2026.11.20`, 빈 값·`2026.13.4`·`abc`는 그대로다

### UI-013 Enter는 확정한 값으로 onEnter를 부르고 폼을 제출하지 않으며 onEnter가 없으면 제출된다
- Given 폼 안의 `onEnter`가 있는 칸, `onEnter`만 있는 칸 둘, 폼 안의 `onEnter`가 없는 칸
- When 첫 칸에 `2026.1.5` + Enter, 둘째 칸에 `2026.13.04` + Enter, 셋째 빈 칸에서 Enter, 넷째 칸에 `20261120` + Enter
- Then 첫 칸은 `2026.01.05`로 보이고 `onEnter('2026-01-05')`가 한 번 불리며 폼 제출이 없다. 둘째는 `onEnter('2026.13.04')`, 셋째는 `onEnter('')`, 넷째는 폼이 한 번 제출된다

### UI-014 입력 조합 중의 Enter는 확정·onEnter를 하지 않는다
- Given `onEnter`가 있는 칸에 `2026.1.5`를 친 상태
- When 입력 조합 중(`isComposing`) Enter 키 이벤트가 온다
- Then 칸은 `2026.1.5` 그대로이고 `onEnter`는 불리지 않는다

### UI-015 달력 버튼은 숨은 칸의 달력을 열고 지원하지 않거나 거부되면 숨은 칸을 눌러 연다
- Given (가) `showPicker`가 있는 브라우저 (나) 없는 브라우저 (다) `showPicker`가 `NotAllowedError`를 던지는 브라우저
- When 각각 "견적일 달력 열기"를 누른다
- Then (가) 숨은 날짜 칸의 `showPicker`가 한 번 불린다, (나) 숨은 칸이 포커스를 받고 클릭이 한 번 일어난다, (다) 숨은 칸 클릭이 한 번 일어난다

### UI-016 달력에서 고른 날짜는 칸에 보이고 값·포커스·onPicked로 이어지며 달력은 현재 값으로 열린다
- Given `onPicked`가 있는 빈 칸, 값 `2026-11-20`인 칸, `2026.1`을 친 칸
- When 첫 칸의 숨은 칸에서 `2026-12-01`을 고른다
- Then 첫 칸은 `2026.12.01`이고 부모는 `2026-12-01`, `onPicked('2026-12-01')`, 포커스는 텍스트 칸이다. 둘째 칸의 숨은 칸 값은 `2026-11-20`, 셋째 칸은 빈 값이다

### UI-017 달력이 범위 밖 값을 주면 무시하고 빈 값을 주면 칸을 비운다
- Given 값 `2026-11-20`인 칸
- When 숨은 칸 값이 `3000-01-01`로 바뀌고, 이어서 빈 값으로 바뀐다
- Then 첫 변경에서 칸은 `2026.11.20` 그대로이고 `onChange`가 불리지 않으며, 둘째 변경에서 칸이 비고 부모는 `''`을 받는다

### UI-018 숨은 칸은 Tab 순서·접근성 트리 밖이고 달력 버튼은 칸 이름을 따르며 폼을 제출하지 않는다
- Given 이름 "견적일" 칸, `aria-label` "Due Date" 칸, 이름 없는 칸, 바깥 `<label for>` "Due Date" 칸, 폼 안의 칸
- When 화면을 보고 폼 안 칸의 달력 버튼을 누른다
- Then 숨은 칸은 `tabindex=-1`·`aria-hidden="true"`·`min 1900-01-01`·`max 2999-12-31`·`date-input-native`이고 `display:none`이 아니다. 버튼 이름은 "견적일 달력 열기", "Due Date 달력 열기", "달력 열기", "Due Date 달력 열기"이고 `type="button"`이며 폼 제출이 없다

### UI-019 부모가 값을 바꾸거나 비우면 표시가 따라가고 입력 중 글자·틀린 글자는 그대로 둔다
- Given 값 `2026-11-20`인 칸, 부모 상태와 연결된 빈 칸
- When 부모가 값을 `2027-01-05`로, 다시 `''`로 바꾸고, 연결된 칸에 `2026.1`·`2026.1.5`를 친다. 별도로 부모가 값 `2026.13.4`를 준다
- Then 칸은 `2027.01.05`, 빈 칸 순으로 바뀌고, 치는 칸은 `2026.1`·`2026.1.5` 그대로이며, `2026.13.4`는 그대로 보인다

### UI-020 글자를 다시 만들어도 캐럿은 입력한 숫자 뒤에 남는다
- Given 값 `2026-11-20`인 칸, 값 `2026-11-02`인 칸
- When (가) 캐럿 5에서 Backspace (나) 둘째 칸 캐럿 6에서 `2`를 친다 (다) 첫 칸 캐럿 2에서 `9`를 친다
- Then (가) 캐럿은 3~5 사이이고 선택 범위가 없다 (나) 캐럿 7 (다) 캐럿 3이다

### UI-021 날짜 텍스트 칸의 속성과 id·name·required·disabled·바깥 label·inputRef·autoFocus·onBlur
- Given `id="d1"`, `name="due"`, `disabled`인 칸, `required` 칸, `autoFocus` 칸, `inputRef`·`onBlur`를 받은 칸, 바깥 `<label for="due">Due Date</label>` 칸
- When 화면을 보고 `onBlur` 칸에서 Tab으로 벗어난다
- Then 텍스트 칸은 `type="text"`·`inputmode="numeric"`·placeholder `yyyymmdd`·`autocomplete="off"`이고 `maxlength`가 없다. 첫 칸은 텍스트 칸·달력 버튼이 비활성이고 id·name이 있다. `required`, `data-autofocus`가 붙고, `inputRef`는 텍스트 칸이며, `onBlur`가 불리고, 바깥 라벨 "Due Date"로 칸을 찾는다

### UI-022 native 날짜 칸은 DateInput 밖 소스에 없다(가드)
- Given 판정 함수에 넣는 가짜 소스: 리터럴 `type="date"`(다섯 가지 철자, 화살표 속성 뒤 포함), 검토 목록 밖 동적 `type`, 객체 리터럴 `type: 'date'`, `type` 없는 spread, 그리고 허용 예(`type="text"` spread, 체크박스, `<DateInput>`, `DateInput.tsx` 자신), `'date'`를 언급하는 검토 파일(`<DateInput` 있음/없음)
- When 가짜 소스와 실제 `` 소스(100개 넘음, `FormField.tsx`·`DateInput.tsx` 포함)를 검사한다
- Then 금지 예는 각 규칙 이름으로 걸리고 허용 예와 `<DateInput`이 있는 검토 파일은 통과하며, 실제 소스에는 위반이 없고 `DateInput.tsx`에는 native 날짜 칸이 있다

### UI-023 금액 칸은 치는 동안 세 자리 콤마를 넣고 숫자 아닌 글자를 버린다
- Given 빈 "금액" 칸(부모 상태와 연결)
- When `1234567`을 치고, 다른 빈 칸에 `12a3.4 5`를 친다
- Then 첫 칸은 `1,234,567`이고 부모가 마지막으로 받은 글자도 `1,234,567`, 둘째 칸은 `12,345`다

### UI-024 콤마를 다시 넣어도 캐럿은 같은 숫자 뒤에 남는다
- Given 값 `1,234`인 칸
- When (가) 캐럿 1에서 `9`를 친다 (나) 캐럿 2(콤마 뒤)에서 Backspace (다) 캐럿 1에서 `x`를 친다
- Then (가) `19,234`·캐럿 2 (나) `1,234`·캐럿 1 (다) `1,234`·캐럿 1이다. 함수 기준 (`12345`,5)→(`12,345`,6), (`1,2345`,6)→(`12,345`,6), (`1,9234`,3)→(`19,234`,2), (`1234`,1)→(`1,234`,1), (`,234`,0)→(`234`,0)

### UI-025 앞자리 0은 지우고 붙여넣은 소수점 금액은 숫자만 남는다
- When 글자·캐럿 (`007`,3), (`0`,1), (`1a2.3`,5), (빈 글자,0), (`1,500,000.50`,12)를 정리한다
- Then (`7`,1), (`0`,1), (`123`,3), (빈 글자,0), (`150,000,050`,11)이다

### UI-026 금액 칸에는 단위 글자가 없고 항목 이름이 원 단위를 가진다
- Given 값 `1,234`인 금액 칸
- When 화면과 항목 이름 상수를 본다
- Then 입력 칸 하나뿐이고 "천원" 등 단위 글자가 없으며, 항목 이름은 `금액(단위:원)`·`매출금액(단위:원, 실제 값)`, 상한 상수는 `Number.MAX_SAFE_INTEGER`다

### UI-027 금액 읽기는 1~2^53−1 정수만 원으로 읽고 나머지는 거절한다
- When `1,870,000,000`, ` 500 `, `9,007,199,254,740,991`과 `''`, `' '`, `0`, `1.5`, `-3`, `abc`, `1 000`, `1e3`, `9007199254740992`를 읽고, 숫자 `1`, `0`, `1.2`, 문자 `'3'`, 상한+2를 `isValidAmount`로 판정한다
- Then 앞 셋은 1870000000, 500, 9007199254740991이고 나머지는 null이다. `isValidAmount`는 `1`만 참이다

### UI-028 금액 문구는 상한 초과와 그 밖의 위반을 구분한다
- When `''`, `0`, `9,007,199,254,740,992`, `1`, `9,007,199,254,740,991`의 문구를 구한다
- Then 앞 둘은 "매출금액은 1원 이상의 정수를 입력하세요.", 셋째는 "매출금액은 9,007,199,254,740,991원 이하로 입력하세요.", 뒤 둘은 null이다

### UI-029 금액 표시는 반올림 없는 콤마 숫자다
- When 1870000000, 150000000, 1234567, 1234499, 1500, 300, 1, 0, 9007199254740991을 표시하고, `AmountText`에 1234567을 준다
- Then `1,870,000,000`, `150,000,000`, `1,234,567`, `1,234,499`, `1,500`, `300`, `1`, `0`, `9,007,199,254,740,991`이고 `AmountText`는 `1,234,567`을 보인다. 천원 함수(`toThousandWon` 등)는 내보내지 않는다

### UI-030 차트 축 금액은 반올림 뒤 억·만 단위를 정해 줄인다
- When 1870000000, 100000000, 123400000000, 50000000, 15000, 9000, 0, −50000000, 99999999, 99999500, 99995000, 9999999, 10000, 9999, −99999999, −99999500, −9999999, −9999, −0을 줄인다
- Then `18.7억`, `1억`, `1,234억`, `5,000만`, `1.5만`, `9,000`, `0`, `-5,000만`, `1억`, `1억`, `9,999.5만`, `1,000만`, `1만`, `9,999`, `-1억`, `-1억`, `-1,000만`, `-9,999`, `0`이다

### UI-031 천원 표기·변환의 잔재가 소스에 없다(가드)
- Given 금지어 일곱 개 각각을 담은 가짜 소스와 원 단위 가짜 소스(`금액(단위:원)`, `formatWon(1)`, `unit: 'krw'`)
- When 가짜 소스와 실제 `` 소스(100개 넘음, `shared/model/money.ts`·`shared/api/schema.d.ts` 포함)를 검사한다
- Then 가짜 금지 소스는 그 단어로 걸리고 원 단위 소스는 통과하며, 실제 소스에는 위반 파일이 없다

### UI-032 콤보박스는 접근 이름이 있고 포커스·클릭에 후보 목록을 연다
- Given 라벨 "회사명"·후보 3개인 콤보박스
- When 칸을 누르고, (다른 화면에서) Tab으로 포커스만 주고, Esc로 닫은 뒤 포커스가 있는 칸을 다시 누른다
- Then 누르면 목록(`listbox`)에 항목 3개, Tab 포커스로도 목록이 열리며, 닫힌 뒤 다시 누르면 다시 열린다

### UI-033 openOnFocus가 거짓이면 포커스만으로 열지 않고 클릭·입력·↓로 연다
- Given `openOnFocus={false}`인 콤보박스
- When Tab으로 포커스 → 클릭 → Esc → ↓ → Esc → `하` 입력
- Then 포커스만으로는 목록이 없고, 클릭·↓·입력에는 각각 목록이 열린다(`openOnFocus` 생략·참이면 포커스로 열림)

### UI-034 입력으로 후보를 대소문자 무시 부분 일치로 거르고 후보와 같은 값이면 전체를 보인다
- Given 후보 한빛상사·하나솔루션·대한소프트, 그리고 후보 `Alpha`·`alphabet`·`Beta`인 콤보박스
- When 첫 칸에 `하`를 치고, 둘째 칸에 `ALP`를 치고, 둘째 칸 값을 `alpha`로 두고 연다
- Then `하` → 하나솔루션만, `ALP` → Alpha·alphabet, `alpha`(후보 값과 대소문자 무시로 같음) → 후보 3개 전부다

### UI-035 마우스나 ↑↓·Enter로 고르면 값을 채우고 선택을 알리고 닫으며 직접 입력은 선택 알림이 없다
- Given 후보 3개인 콤보박스(`onSelectOption` 연결)
- When (가) 열고 대한소프트를 누른다 (나) 열고 ↓↓ 후 Enter (다) `새회사`를 친다
- Then (가) 값 `대한소프트`, `onSelectOption(대한소프트 항목)`, 목록 닫힘 (나) 두 번째 ↓ 뒤 `aria-activedescendant`가 둘째 항목이고 Enter로 값 `하나솔루션`·`onSelectOption(하나솔루션 항목)` (다) 값 `새회사`이고 `onSelectOption`은 불리지 않는다

### UI-036 모달 안 콤보박스의 Esc는 열린 목록만 닫고 모달은 남는다
- Given 모달 "Action 추가" 안 콤보박스의 목록이 열린 상태
- When Esc를 누르고, 목록이 닫힌 상태에서 Esc를 한 번 더 누른다
- Then 첫 Esc 뒤 목록은 닫히고 모달 `onClose`는 불리지 않으며, 두 번째 Esc에 `onClose`가 한 번 불린다

### UI-037 콤보박스의 오류·안내·보이는 라벨·transform·inputRef
- Given `error` "회사명을 입력하세요." 칸, `hint` 칸, `label` "고객 회사명"·`visibleLabel` "회사" 칸, `visibleLabel` 없는 칸, 공백 제거 `transform` 칸, `inputRef` 칸
- When 화면을 보고, transform 칸에 `a b c`를 치고, ref로 포커스를 준다
- Then 오류 칸은 alert 문구와 invalid 상태, hint 칸은 안내 문구, 셋째 칸은 보이는 라벨 "회사"·접근 이름 "고객 회사명"이고 목록 이름도 "고객 회사명", `visibleLabel` 없는 칸은 라벨 "회사명"이고 `aria-label`이 없으며, transform 칸 값은 `abc`, ref 칸은 포커스를 받는다

### UI-038 다중 선택 버튼은 라벨+요약 이름으로 닫혀 있고 열면 후보 순서의 체크박스와 지우기 버튼이다
- Given 라벨 "Forecast", 호출자가 준 요약 "2개 선택", 후보 Pipeline·Best·Commit, 선택 `best`
- When 화면을 보고 버튼을 누른다. 별도로 후보가 빈 다중 선택을 연다
- Then 처음 버튼 이름 "Forecast 2개 선택"·`aria-expanded="false"`·패널 없음, 라벨 "Forecast"로 버튼을 찾는다. 열면 그룹 "Forecast" 안 체크박스 값 순서 `pipeline, best, commit`·`name` `forecast`·Best만 체크, 버튼 "전체"가 있다. 후보가 비면 체크박스가 없다

### UI-039 체크·해제는 onToggle로 알리고 패널이 남으며 지우기는 onClear이고 글자를 바꿀 수 있다
- Given 연 다중 선택(선택 없음 / 선택 `best`), `clearLabel` "선택 해제"인 다중 선택
- When Best를 체크하고, 선택된 Best를 해제하고, "전체"를 누르고, 셋째 것을 연다
- Then `onToggle('best', true)` 한 번·패널 유지, `onToggle('best', false)`, "전체"는 `onClear` 한 번이고 `onToggle`은 없으며, 셋째 패널의 지우기 버튼 글자는 "선택 해제"다

### UI-040 다중 선택은 Esc·바깥 누름·포커스 이탈·버튼 재클릭으로 닫히고 패널 안 이동으로는 닫히지 않는다
- Given 연 다중 선택과 바깥 버튼 "바깥", 뒤에 "다음 입력란"
- When (가) Best 체크 뒤 Esc (나) "바깥" 누름 (다) 패널 안 글자 Pipeline 누름 (라) 버튼 재클릭 (마) "전체" 버튼에서 Tab (바) Pipeline 체크박스에서 Tab
- Then (가) 닫히고 `aria-expanded="false"`·포커스는 버튼 (나) 닫힘 (다) 열림 유지 (라) 닫힘 (마) 닫히고 포커스는 "다음 입력란" (바) 포커스는 Best, 열림 유지

### UI-041 다중 선택의 aria-expanded·aria-controls·안내 문구 연결
- Given 안내 "연도가 전체이면 올해(2026) 기준입니다."인 다중 선택, 안내 없는 다중 선택
- When 닫힌 상태와 연 상태를 본다
- Then `aria-haspopup`은 없고 `aria-expanded`가 열림을 따른다. `aria-controls`는 열린 동안만 있고 실제 패널을 가리킨다. 안내가 있으면 버튼 `aria-describedby`가 안내 문구를 가리키고 안내는 닫힘·열림 모두 보이며, 안내가 없으면 `aria-describedby`가 없다

### UI-042 모달은 제목 이름의 aria-modal 대화상자로 열리고 data-autofocus 또는 첫 칸에 포커스한다
- Given 제목 "매출 확정"·안에 입력 칸 "금액"인 모달, 첫 버튼 뒤에 `data-autofocus` 칸이 있는 모달, 포커스 가능한 요소가 없는 모달
- When 각각 연다
- Then 첫째는 이름 "매출 확정"·`aria-modal="true"`이고 "금액" 칸에 포커스, 둘째는 `data-autofocus` 칸에 포커스, 셋째는 대화상자 자체에 포커스가 있다

### UI-043 Esc로 닫으면 연 버튼으로 포커스가 돌아오고 배경을 눌러도 닫히지 않는다
- Given "열기" 버튼으로 여는 모달
- When 열고 배경을 누른 뒤 Esc를 누른다
- Then 배경 누름에는 `onClose`가 없고 대화상자가 남으며, Esc에 `onClose`가 한 번 불려 대화상자가 사라지고 포커스는 "열기"다

### UI-044 Tab·Shift+Tab은 모달 안에서 돈다
- Given 바깥 버튼 "바깥"과 버튼 "첫째"·"둘째"가 있는 모달, 포커스 가능한 요소가 없는 모달
- When Tab을 세 번 누르고, 둘째 모달에서 Tab을 누른다
- Then 포커스는 계속 첫 모달 안이고, 요소가 없는 모달에서는 포커스가 대화상자 밖으로 나가지 않는다

### UI-045 겹친 모달에서 Esc·Tab은 맨 위만 받고 안쪽이 닫히면 바깥이 받는다
- Given 바깥 모달 안에서 "안쪽 열기"로 연 안쪽 모달(버튼 "안쪽 첫째"·"안쪽 둘째")
- When (가) Esc (나) 다시 Esc (다) 새로 열어 Tab, Tab (라) 새로 열어 Shift+Tab (마) 겹친 모달을 모두 없앤 뒤 새 단일 모달에서 Esc
- Then (가) 안쪽만 닫히고 바깥 `onClose`는 없다 (나) 바깥 `onClose` 한 번 (다) 포커스는 "안쪽 첫째" → "안쪽 둘째" → "안쪽 첫째" (라) "안쪽 둘째" (마) 새 모달 `onClose` 한 번

### UI-046 확인 대화상자는 문구·확인·취소를 보이고 Esc는 취소이며 busy·confirmDisabled면 확인만 꺼진다
- Given 제목 "삭제"·문구 "삭제할까요?"·확인 "삭제"·`danger`인 대화상자, `busy`인 대화상자, `confirmDisabled`인 대화상자
- When 첫째에서 "삭제"·"취소"를 누르고, 둘째에서 Esc를 누른다
- Then 첫째는 대화상자 이름 "삭제"와 문구가 보이고 `onConfirm`·`onCancel`이 각각 한 번이다. 둘째·셋째는 "확인" 버튼이 비활성이고 "취소"는 활성이며, 둘째의 Esc는 `onCancel`을 부른다

### UI-047 페이저는 첫 페이지에서 이전이 꺼지고 페이지 번호와 이전·다음 offset을 낸다
- Given (가) offset 0·limit 20·total 41 (나) offset 40·limit 20·total 100
- When (가)에서 "다음"을, (나)에서 "이전"을 누른다
- Then (가) "이전" 비활성·"1 페이지"·`onChange(20)` (나) "3 페이지"·`onChange(20)`. `nav` 이름은 "페이지"다

### UI-048 페이저는 total이 있으면 그것으로, 없으면 받은 건수로 마지막 페이지를 정한다
- Given (가) offset 20·limit 20·total 40 (나) offset 0·limit 20·count 20(total 없음) (다) offset 0·limit 20·count 7
- When 화면을 본다
- Then (가) "다음" 비활성·"이전" 활성 (나) "다음" 활성 (다) "다음" 비활성

### UI-049 표지가 200px 안에 들어오면 다음 페이지를 한 번 요청한다
- Given 다음 페이지가 있고 읽는 중이 아닌 목록의 표지
- When 표지가 화면 가까이 들어온다
- Then 관찰 대상은 하나이고 rootMargin은 `200px`이며 `fetchNextPage`가 한 번 불린다

### UI-050 다음 페이지가 없거나 읽는 중이면 요청하지 않고 교차 순간의 최신 상태를 쓴다
- Given (가) 다음 페이지 없음 (나) 읽는 중 (다) 처음엔 다음 페이지가 있었으나 다시 그릴 때 없음
- When 각각 표지가 들어온다
- Then 세 경우 모두 `fetchNextPage`가 불리지 않는다

### UI-051 페이지가 늘면 다시 관찰하고 떠나면 끊으며 IntersectionObserver가 없어도 오류가 없다
- Given 페이지 1을 관찰 중인 표지
- When 페이지 수가 2가 되고, 이어서 화면을 떠난다. 별도로 `IntersectionObserver`가 없는 환경에서 그린다
- Then 관찰자가 새로 만들어지고 관찰 대상은 여전히 하나이며, 떠난 뒤 관찰 대상은 0이다. 관찰자가 없는 환경에서도 오류가 없다

### UI-052 정렬 머리글은 정렬 중인 열에만 aria-sort·방향을 두고 누르면 onSort, onSort가 없으면 글자만이다
- Given 정렬 중 asc "담당자", 정렬 중 desc "담당자", 정렬 중 아님 "유형", 정렬 중 아님 "Due Date"(onSort 연결), onSort 없는 "Memo"
- When 화면을 보고 "Due Date"를 누른다
- Then "담당자"는 `aria-sort` ascending/descending과 버튼 `data-dir` asc/desc·클래스 `th-sort`, "유형"은 둘 다 없음, "Due Date"를 누르면 `onSort` 한 번, "Memo"는 버튼·`aria-sort`가 없다

### UI-053 탭은 선택 상태·패널 이름을 갖고 클릭·화살표·Home·End로 옮기며 선택 탭만 Tab 순서에 든다
- Given 탭 목록 "Deal 하단"에 Actions(선택)·Deal History·Files
- When "Deal History"를 누르고, Actions에서 → 두 번·End·Home·←를 누른다
- Then 처음 Actions가 `aria-selected="true"`이고 패널 이름 Actions, 누르면 Deal History 선택·패널 내용 바뀜. 화살표·Home·End마다 그 탭으로 선택과 포커스가 옮겨지고(끝에서 처음으로 돈다) 선택되지 않은 탭은 `tabindex=-1`이다

### UI-054 알림 줄은 오류만 alert이고 onClose가 있을 때만 닫기 버튼이 있다
- When `success` "저장되었습니다.", `error` "실패", `onClose`가 있는 알림, `onClose`가 없는 알림을 그리고 닫기를 누른다
- Then 첫째는 `status`, 둘째는 `alert`, 셋째는 "닫기"를 누르면 `onClose`, 넷째는 "닫기" 버튼이 없다

### UI-055 화면 이동 알림은 한 번 보이고 기록 상태를 비우며 주소는 그대로이고 문자열이 아니면 없다
- Given 이동 상태 `{notice: '삭제되었습니다.'}`로 연 `/deals?q=a`, 상태 `{notice: 3}`, 상태 없음
- When 화면을 본다
- Then 첫째는 알림 "삭제되었습니다."가 보이고 기록 상태가 null이 된 뒤에도 알림이 남으며 주소는 `/deals?q=a`다. 둘째·셋째는 알림이 없다

### UI-056 데이터가 없으면 Deal 목록은 전체 연도에서 등록 안내와 등록 링크, 기본 연도에서는 조건 문구다
- Given 업무 데이터가 없는 Fake(`seed: 'empty'`)
- When `/deals?year=all`과 `/deals`를 연다
- Then 앞은 "등록된 Deal이 없습니다."와 링크 "+ Deal 등록", 뒤는 "조건에 맞는 Deal이 없습니다."("등록된 Deal이 없습니다." 없음)이고 주소가 `/deals?year=<올해>`가 된다

### UI-057 데이터가 없어도 Forecast·연락처는 빈 문구이고 기본 코드·Label·로그인 계정은 보인다
- Given 업무 데이터가 없는 Fake
- When `/forecast?year=2026`, admin으로 `/admin/contacts`, `/admin/deal`(탭 Status 코드·Forecast 코드·BANT Label), `/admin/users`를 연다
- Then Forecast는 "조건에 맞는 Deal이 없습니다."이고 alert가 없다. 연락처는 "등록된 연락처가 없습니다.", Deal 관리에는 기회발굴·Commit 행과 Budget의 "단독 예산 확보", 사용자 관리에는 kim(sales 김영업)·root(admin 최관리) 행이 보인다

### UI-058 빈 상태에서 첫 Deal 등록 → Action 추가 → 첨부 → History가 이어진다
- Given 업무 데이터가 없는 Fake, `/deals/new`
- When 고객·파트너를 직접 입력하고 금액 `100000000`·Solution·Users count·Expected Close를 넣어 저장 → Actions 탭에서 Action(유형 "미팅", 진행사항, Next Action, Due Date)을 등록 → Deal 상세 탭에서 `제안서.pdf`를 올린다 → Deal History 탭을 연다
- Then 상세 주소(`/deals/<YYYYMMDD>-<4자>`)와 제목 "첫 Deal", Action 목록의 "킥오프 미팅", 첨부 전 "첨부된 파일이 없습니다."와 올린 뒤 `제안서.pdf` 버튼, History에 `제안서.pdf` 행이 보인다

### UI-059 키·값 격자 CSS는 글자 크기 없이 최대 3열·라벨 고정 열·긴 값 줄바꿈을 선언한다
- When `kvGrid.css`를 정적으로 읽는다
- Then `font-size`가 없고, `.kv-grid`에 `repeat(auto-fill`·`/ 3)`, 행에 `var(--kv-label-w) minmax(0, 1fr)`·`align-items: baseline`·`min-width: 0`, `.kv-grid dd`에 `overflow-wrap: anywhere`가 있으며, `grid-column`을 주는 `.combo-list` 선택자는 모두 `.kv-grid > `로 시작한다

### UI-060 본문 영역은 모든 너비에서 좌우 5% 여백이고 최대 너비가 없다
- When `index.css`의 `.content` 규칙들을 읽는다
- Then 기본 규칙은 `padding: 24px 5%`, 규칙이 둘 이상이고 모두 `padding: <n>px 5%`이며 어느 규칙에도 `max-width`가 없다

### UI-061 기본 필드는 라벨이 접근 이름이고 TextField 날짜 형식은 DateInput이다
- Given 라벨 "이름" `TextField`(invalid), 라벨 "메모" `TextArea`, 라벨 "역할" `SelectField`, 라벨 "내 딜만" `CheckboxField`, 라벨 "시작일"·`name="from"`·`type="date"` `TextField`
- When 화면을 보고 각 칸에 값을 넣거나 체크한다
- Then 각 칸을 라벨로 찾고 `onChange`가 새 값(체크박스는 참)으로 불리며, "이름" 칸은 `aria-invalid`, "메모"는 3줄이다. "시작일"은 id `from-date`·`inputmode="numeric"`인 텍스트 칸과 "시작일 달력 열기" 버튼이며 native `type="date"` 텍스트 칸이 아니다

### UI-062 required 콤보박스는 입력 칸 required 속성과 루트 required 클래스를 가진다
- Given 라벨 "고객 회사명" `required` 콤보박스와 라벨 "파트너 회사명" 콤보박스(`required` 없음)
- When 화면을 그린다
- Then 첫 칸은 입력 칸에 `required` 속성, 루트에 `required` 클래스가 있고 둘째 칸에는 둘 다 없다. 라벨 글자(접근 이름)는 그대로다

## 5. 변경 이력

| 날짜 | 변경 | 영향 테스트 코드 |
| --- | --- | --- |
| 2026-11-11 | 최초 작성(구현된 동작을 정본으로 옮김, 초안) | UI-001~UI-061 |
| 2026-11-11 | 사용자 결정 반영(추천대로): 범위에 주인 없는 shared 부품 포함·`UserSelect`·`PeriodField` 등은 원래 feature, 금액 판정·문구 정본 UI-R13·R14(DE-R26이 번호로 가리킴), `formatWonAxis` UI-R16, 빈 첫 실행 UI-R36(UI-056~058), CSS 정적 점검 UI-059·060, 확인 대화상자 진행 중 취소·Esc 허용 현행 문서화(UI-R29). 다른 문서의 UI 이름 참조를 규칙 번호로 교체. 동작·케이스 변경 없음 | 없음 |
| 2026-11-12 | DE 고객 필수 표시 요청에 따라 UI-R18에 `required`의 루트 클래스 규칙 추가(운영 코드 변경 필요) | 신규: UI-062 |
