#!/usr/bin/env bash
# 비밀 생성과 .env 줄 편집 공용 함수(scripts/setup.sh가 source한다).
# source만으로는 아무것도 실행하거나 출력하지 않는다. 비밀 값은 출력하지 않고 명령 인자(argv)에도 싣지 않는다.

# 32바이트 난수를 URL-safe base64(패딩 없음) 43자로 출력한다(개행 없음)
gen_jwt_secret() {
  head -c 32 /dev/urandom | base64 | tr '+/' '-_' | tr -d '=\n'
}

# 32바이트 난수를 URL-safe base64 44자(끝 '=', Fernet 키 형식)로 출력한다(개행 없음)
gen_fernet_key() {
  head -c 32 /dev/urandom | base64 | tr '+/' '-_' | tr -d '\n'
}

# 영숫자 32자 DB 비밀번호를 출력한다(개행 없음). 영숫자만 써서 .env 파싱과 URL 인코딩 문제가 없다
gen_db_password() {
  head -c 96 /dev/urandom | base64 | tr -dc 'A-Za-z0-9' | head -c 32
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

# env_ensure_database_url <file>
# APP_DATABASE_URL 줄이 없고 POSTGRES_USER·POSTGRES_PASSWORD·POSTGRES_DB가 있으면 같은 값으로
# postgresql+asyncpg://<user>:<password>@db:5432/<db> 를 덧붙이고 0을 돌려준다.
# 줄이 이미 있으면 1(파일 불변), POSTGRES_* 가 하나라도 비어 있으면 2(파일 불변).
# 비밀번호는 파일 안에서만 다루고 출력하지 않으며 외부 명령의 인자(argv)에 싣지 않는다.
env_ensure_database_url() {
  local file="$1" user password db
  if grep -q "^APP_DATABASE_URL=" "$file"; then
    return 1
  fi
  user="$(grep "^POSTGRES_USER=" "$file" | head -1 | cut -d= -f2-)"
  password="$(grep "^POSTGRES_PASSWORD=" "$file" | head -1 | cut -d= -f2-)"
  db="$(grep "^POSTGRES_DB=" "$file" | head -1 | cut -d= -f2-)"
  if [ -z "$user" ] || [ -z "$password" ] || [ -z "$db" ]; then
    return 2
  fi
  if [ -n "$(tail -c 1 "$file")" ]; then
    printf '\n' >> "$file"
  fi
  printf 'APP_DATABASE_URL=postgresql+asyncpg://%s:%s@db:5432/%s\n' "$user" "$password" "$db" >> "$file"
  return 0
}
