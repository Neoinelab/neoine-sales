#!/usr/bin/env bash
# infra/server/bootstrap.sh <dev|product>
# 서버당 최초 1회, root(sudo)로 실행한다. 멱등: 설정 파일(systemd, nginx, sudoers)을 바꿨을 때도 다시 실행한다.
set -euo pipefail

ENV_NAME="${1:?usage: bootstrap.sh <dev|product>}"
case "$ENV_NAME" in dev | product) ;; *) echo "알 수 없는 프로파일: $ENV_NAME" >&2; exit 2 ;; esac
[ "$(id -u)" -eq 0 ] || { echo "root(sudo)로 실행하세요" >&2; exit 2; }

UV_VERSION="0.10.4"   # uv.lock을 만든 uv와 같은 버전으로 고정
PYTHON_VERSION="3.14" # backend/.python-version 과 일치
HERE="$(cd "$(dirname "$0")" && pwd)"
APP_HOME=/opt/neoine-sales

# 비밀 생성·.env 줄 편집 공용 함수(scripts/setup.sh와 함께 쓴다)
[ -f "$HERE/lib/env_secrets.sh" ] || { echo "lib/env_secrets.sh가 없습니다: $HERE/lib" >&2; exit 2; }
# shellcheck source=lib/env_secrets.sh
source "$HERE/lib/env_secrets.sh"

# 0) 사전 설치(OS 패키지, 배포판에 맞게 수동): curl, tar, (DB 서버는 별도 호스트). nginx는 있을 때만 설정을 설치한다
#    예) Ubuntu: apt install curl    /  Rocky: dnf install curl

# 1) 서비스/배포 계정(SSH 키 인증 전용. Jenkins 배포 키의 공개키는 관리자가 authorized_keys에 등록)
id neoine &> /dev/null || useradd --create-home --shell /bin/bash neoine
install -d -o neoine -g neoine -m 750 "$APP_HOME" "$APP_HOME/incoming" "$APP_HOME/releases" "$APP_HOME/shared"
# 첨부 파일 저장 위치(systemd ReadWritePaths=/var/lib/neoine-sales). 외부연동 화면에서 이 경로를 등록한다
install -d -o neoine -g neoine -m 750 /var/lib/neoine-sales /var/lib/neoine-sales/files

# 2) uv와 Python(neoine 계정, 인터넷에서 직접 다운로드)
sudo -u neoine -H sh -c "curl -LsSf https://astral.sh/uv/$UV_VERSION/install.sh | sh"
sudo -u neoine -H /home/neoine/.local/bin/uv python install "$PYTHON_VERSION"

# 3) 설정 파일 설치(systemd, sudoers, nginx는 있을 때만). nginx 경로는 배포판에 맞게 조정(conf.d / sites-enabled)
install -m 644 "$HERE"/systemd/*.service /etc/systemd/system/
install -m 644 "$HERE"/systemd/*.timer /etc/systemd/system/
install -m 440 "$HERE/sudoers/neoine-sales" /etc/sudoers.d/neoine-sales
visudo -cf /etc/sudoers.d/neoine-sales
systemctl daemon-reload
systemctl enable neoine-sales-api # 시작은 첫 배포 때
systemctl enable --now neoine-sales-forecast-snapshot.timer # 월말 Forecast 스냅숏(서비스가 아니라 timer를 enable)
if command -v nginx > /dev/null; then
  install -m 644 "$HERE/nginx/neoine-sales.conf" /etc/nginx/conf.d/neoine-sales.conf
  nginx -t && systemctl reload nginx
else
  echo "nginx가 없어 nginx 설정 설치와 reload를 건너뜁니다(nginx를 쓰려면 설치 후 bootstrap.sh를 다시 실행)"
fi

# 4) .env 생성: APP_PROFILE만 채우고 나머지 비밀은 관리자가 직접 입력(이미 있으면 보존)
if [ ! -f "$APP_HOME/.env" ]; then
  install -m 600 -o neoine -g neoine /dev/null "$APP_HOME/.env"
  echo "APP_PROFILE=$ENV_NAME" > "$APP_HOME/.env"
  echo "필수 변수(.env.example 참고)를 neoine 계정으로 $APP_HOME/.env 에 입력하세요."
fi

# 5) 비밀 키: 줄이 없을 때만 만들고 값은 출력하지 않는다(이미 있으면 보존, 재실행 안전)
#    APP_SETTINGS_ENCRYPTION_KEY(AD 바인드 비밀번호 암호화, Fernet 형식 = 32바이트 URL-safe base64): 잃거나 바꾸면
#    저장된 바인드 비밀번호를 풀 수 없어 외부연동 설정에서 다시 입력해야 하므로 DB 백업과 다른 곳에 따로 보관한다
if env_ensure_line "$APP_HOME/.env" APP_JWT_SECRET gen_jwt_secret; then
  echo "APP_JWT_SECRET을 새로 만들어 $APP_HOME/.env 에 넣었습니다(값은 출력하지 않음)."
fi
if env_ensure_line "$APP_HOME/.env" APP_SETTINGS_ENCRYPTION_KEY gen_fernet_key; then
  echo "APP_SETTINGS_ENCRYPTION_KEY를 새로 만들어 $APP_HOME/.env 에 넣었습니다(값은 출력하지 않음). DB 백업과 다른 곳에 따로 보관하세요."
fi
echo "bootstrap 완료: $ENV_NAME"
