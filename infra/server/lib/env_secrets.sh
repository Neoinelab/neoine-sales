#!/usr/bin/env bash
# 비밀 생성과 .env 줄 편집 공용 함수(scripts/setup.sh, infra/server/bootstrap.sh가 source한다).
# source만으로는 아무것도 실행하거나 출력하지 않는다. 비밀 값은 출력하지 않고 명령 인자(argv)에도 싣지 않는다.

# 32바이트 난수를 URL-safe base64(패딩 없음) 43자로 출력한다(개행 없음)
gen_jwt_secret() {
  head -c 32 /dev/urandom | base64 | tr '+/' '-_' | tr -d '=\n'
}

# 32바이트 난수를 URL-safe base64 44자(끝 '=', Fernet 키 형식)로 출력한다(개행 없음)
gen_fernet_key() {
  head -c 32 /dev/urandom | base64 | tr '+/' '-_' | tr -d '\n'
}

# env_ensure_line <file> <NAME> <generator_fn>
# NAME= 줄이 있으면 아무것도 하지 않고 1을 돌려준다. 없으면 생성기 값으로 덧붙이고 0을 돌려준다.
env_ensure_line() {
  local file="$1" name="$2" generator="$3" value
  if grep -q "^${name}=" "$file"; then
    return 1
  fi
  value="$("$generator")"
  if [ -n "$(tail -c 1 "$file")" ]; then
    printf '\n' >> "$file" # 마지막 줄에 개행이 없으면 먼저 붙여 줄이 합쳐지지 않게 한다
  fi
  printf '%s=%s\n' "$name" "$value" >> "$file"
  return 0
}

# env_replace_value <file> <NAME>
# 새 값은 환경변수 ENV_NEW_VALUE로 받는다(argv 노출 방지). NAME= 줄을 바꾸고 없으면 덧붙인다.
env_replace_value() {
  local file="$1" name="$2" tmp
  tmp="$(mktemp "$(dirname "$file")/.env_replace.XXXXXX")" || return 1
  if ! awk -v name="$name" '
    BEGIN { prefix = name "="; done = 0 }
    index($0, prefix) == 1 { if (!done) { print prefix ENVIRON["ENV_NEW_VALUE"]; done = 1 } ; next }
    { print }
    END { if (!done) print prefix ENVIRON["ENV_NEW_VALUE"] }
  ' "$file" > "$tmp"; then
    rm -f "$tmp"
    return 1
  fi
  chmod 600 "$tmp" && mv "$tmp" "$file"
}

# env_has_value <file> <NAME>: NAME= 뒤에 값이 있으면 0(출력 없음)
env_has_value() {
  grep -q "^${2}=." "$1"
}
