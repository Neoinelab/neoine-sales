// neoine-sales CI 파이프라인 (Multibranch). 설계 근거: docs/dev-guide.html 15장.
// 모든 브랜치/PR은 검증(Verify, Contract & Security)만 하고, main에서만 api·web 이미지를 만들어 레지스트리에 push한다.
// main에서는 이어서 사람 승인 -> product 서버 1대 배포(docker compose)를 한다(dev 자동 배포는 2026-10-20 제거: dev DB는 로컬 start-backend.sh --profile dev로 사용).
// REGISTRY(레지스트리 주소)와 PRODUCT_HOST(product 서버)는 Jenkins 전역 환경변수로 받는다(저장소에 값을 쓰지 않는다).
// 자격 증명 ID·승인 그룹은 예시 값이다. 실제 환경에 맞게 바꾼다(docs/dev-guide.html 16장).
// agent 요구: linux-build(docker, trivy, PostgreSQL 18, openssl), deploy(ssh).
pipeline {
    agent none

    options {
        timeout(time: 45, unit: 'MINUTES')
        timestamps()
        disableConcurrentBuilds()
        skipStagesAfterUnstable()
        buildDiscarder(logRotator(numToKeepStr: '30', artifactNumToKeepStr: '20'))
    }

    environment {
        RELEASE_TAG = "${env.GIT_COMMIT.take(12)}"
        // 통합 테스트용 PostgreSQL(agent 로컬, CREATEDB 권한만 있는 ci role). 비밀 아님
        TEST_DATABASE_ADMIN_URL = 'postgresql+asyncpg://ci@localhost:5432/postgres'
        // DB를 못 쓰면 통합 테스트를 건너뛰지 않고 실패시킨다(조용한 skip 방지)
        REQUIRE_INTEGRATION_DB = '1'
    }

    stages {
        stage('Verify') {
            parallel {
                stage('Backend') {
                    agent { label 'linux-build' }
                    steps {
                        dir('backend') {
                            sh 'uv sync --locked'
                            sh 'uv run ruff check .'
                            sh 'uv run ruff format --check .'
                            sh 'uv run mypy src scripts tests'
                            sh 'uv run lint-imports'
                            sh 'uv run python scripts/check_file_length.py'
                            sh 'uv run python scripts/check_feature_trace.py'
                            sh 'uv run pytest --junitxml=reports/junit.xml --cov-report=xml:reports/coverage.xml'
                        }
                    }
                    post {
                        always { junit allowEmptyResults: true, testResults: 'backend/reports/junit.xml' }
                    }
                }

                stage('Infra scripts') {
                    agent { label 'linux-build' }
                    steps {
                        sh 'bash -n infra/docker/deploy.sh infra/docker/build_images.sh scripts/setup.sh infra/server/lib/env_secrets.sh'
                        sh 'bash -n infra/docker/tests/test_deploy.sh infra/docker/tests/test_build_images.sh infra/docker/tests/test_compose.sh infra/docker/tests/test_images.sh'
                        sh 'bash infra/docker/tests/test_deploy.sh'
                        sh 'bash infra/docker/tests/test_build_images.sh'
                        // docker를 쓸 수 없으면 건너뛰지 않고 실패한다
                        sh 'REQUIRE_DOCKER=1 bash infra/docker/tests/test_compose.sh'
                        sh 'bash infra/server/tests/test_env_secrets.sh'
                        sh 'bash scripts/tests/test_setup.sh'
                    }
                }

                stage('Frontend') {
                    agent { label 'linux-build' }
                    steps {
                        dir('frontend') {
                            // packageManager(package.json)에 고정된 pnpm 버전을 corepack이 받아 쓴다
                            sh 'corepack enable'
                            sh 'pnpm install --frozen-lockfile'
                            sh 'pnpm lint'
                            sh 'pnpm typecheck'
                            sh 'pnpm test --reporter=default --reporter=junit --outputFile.junit=reports/junit.xml'
                            sh 'pnpm build'
                        }
                        // 검증을 통과한 바로 그 빌드 결과를 Package 단계에서 쓴다
                        stash name: 'frontend-dist', includes: 'frontend/dist/**', allowEmpty: false
                    }
                    post {
                        always { junit allowEmptyResults: true, testResults: 'frontend/reports/junit.xml' }
                    }
                }
            }
        }

        stage('Contract & Security') {
            agent { label 'linux-build' }
            steps {
                // 백엔드 API 문서(openapi.json)와 프런트엔드 API 타입(schema.d.ts)이 코드와 같은지 확인
                dir('backend') {
                    sh 'uv sync --locked'
                    sh 'uv run python scripts/export_openapi.py'
                }
                dir('frontend') {
                    sh 'corepack enable'
                    sh 'pnpm install --frozen-lockfile'
                    sh 'pnpm gen:api'
                    sh 'pnpm audit --prod --audit-level high'
                }
                sh 'git diff --exit-code -- backend/openapi.json frontend/src/shared/api/schema.d.ts'
                dir('backend') {
                    sh 'uvx pip-audit'
                }
                sh 'trivy fs --scanners vuln --severity CRITICAL,HIGH --exit-code 1 backend/uv.lock frontend/pnpm-lock.yaml'
                sh 'gitleaks detect --no-banner --redact'
            }
        }

        stage('Package') {
            when { branch 'main' }
            agent { label 'linux-build' }
            steps {
                unstash 'frontend-dist'
                sh '[ -n "$REGISTRY" ] || { echo "REGISTRY(Jenkins 전역 환경변수)가 설정되지 않았습니다"; exit 1; }'
                sh 'infra/docker/build_images.sh "$RELEASE_TAG"'
                sh 'REQUIRE_DOCKER=1 bash infra/docker/tests/test_images.sh "$RELEASE_TAG"'
                sh 'trivy image --severity CRITICAL,HIGH --exit-code 1 "$REGISTRY/neoine-sales/api:$RELEASE_TAG"'
                sh 'trivy image --severity CRITICAL,HIGH --exit-code 1 "$REGISTRY/neoine-sales/web:$RELEASE_TAG"'
                withCredentials([usernamePassword(credentialsId: 'registry-push',
                                                  usernameVariable: 'REG_USER',
                                                  passwordVariable: 'REG_PASS')]) {
                    // 작은따옴표 셸: 비밀이 Groovy 문자열에 보간되지 않는다. 비밀번호는 stdin으로만 넘긴다
                    sh '''
                        trap 'docker logout "$REGISTRY" >/dev/null 2>&1' EXIT
                        printf '%s' "$REG_PASS" | docker login "$REGISTRY" -u "$REG_USER" --password-stdin
                        docker push "$REGISTRY/neoine-sales/api:$RELEASE_TAG"
                        docker push "$REGISTRY/neoine-sales/web:$RELEASE_TAG"
                    '''
                }
                archiveArtifacts artifacts: 'build/deploy-*.tar.gz', fingerprint: true
                stash name: 'deploy-kit', includes: 'build/deploy-*.tar.gz'
            }
        }

        stage('Deploy: Product') {
            when {
                beforeInput true
                branch 'main'
            }
            input {
                message "product(운영)에 ${env.GIT_COMMIT.take(12)} 버전을 배포할까요?"
                ok '배포'
                submitter 'release-managers'
            }
            agent { label 'deploy' }
            steps {
                unstash 'deploy-kit'
                sh '[ -n "$PRODUCT_HOST" ] || { echo "PRODUCT_HOST(Jenkins 전역 환경변수)가 설정되지 않았습니다"; exit 1; }'
                lock(resource: 'neoine-product') {
                    withCredentials([sshUserPrivateKey(credentialsId: 'deploy-ssh-product',
                                                       keyFileVariable: 'SSH_KEY',
                                                       usernameVariable: 'SSH_USER')]) {
                        // 서버 1대. 서버가 레지스트리에서 읽기 전용 계정으로 이미지를 pull하고, deploy.sh가 덤프 -> migrate -> 전환 -> 헬스체크(실패 시 롤백)를 한다
                        sh '''
                            scp -i "$SSH_KEY" -o StrictHostKeyChecking=yes \
                                "build/deploy-$RELEASE_TAG.tar.gz" infra/docker/deploy.sh \
                                "$SSH_USER@$PRODUCT_HOST:/opt/neoine-sales/incoming/"
                            ssh -i "$SSH_KEY" -o StrictHostKeyChecking=yes "$SSH_USER@$PRODUCT_HOST" \
                                "bash /opt/neoine-sales/incoming/deploy.sh product $RELEASE_TAG"
                        '''
                    }
                }
            }
        }
    }

    post {
        failure {
            mail to: 'dev-team@example.com', subject: "FAILED: ${env.JOB_NAME} #${env.BUILD_NUMBER}", body: "${env.BUILD_URL}"
        }
    }
}
