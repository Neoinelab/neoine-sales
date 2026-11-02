# web 이미지(컨텍스트: 저장소 루트). nginx 가 TLS를 끝내고 정적 파일을 서빙하며 /api 를 api 컨테이너로 프록시한다.
# frontend/dist 는 Jenkins Verify 가 검증한 빌드 결과를 그대로 넣는다(이미지 안에서 다시 빌드하지 않음).
# 빌드는 infra/docker/build_images.sh. 베이스 이미지는 태그와 digest를 함께 고정한다(2026-11-02 Docker Hub 조회, 올릴 때 함께 바꿈).
# 태그 1.30.6-alpine 은 stable-alpine 과 같은 index digest 이다.
FROM nginx:1.30.6-alpine@sha256:0e52bd054126cdc040b1276c0af347aeb02a41b9cfe305d6094767ac30e97949

COPY frontend/dist /usr/share/nginx/html
COPY infra/docker/web/config/config.product.json /usr/share/nginx/config/config.product.json
# 공식 이미지의 entrypoint 가 /etc/nginx/templates/*.template 을 렌더링해 /etc/nginx/conf.d/ 에 둔다
COPY infra/docker/web/templates/default.conf.template /etc/nginx/templates/default.conf.template
