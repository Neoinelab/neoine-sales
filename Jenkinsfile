// neoine-sales CI 파이프라인 (Multibranch). 설계 근거: docs/dev-guide.html 15장.
// 모든 브랜치/PR은 검증(Verify, Contract & Security)만 하고, main에서만 릴리스 번들을 만든다.
// main에서는 이어서 dev 자동 배포(마이그레이션 자동 적용) -> 사람 승인 -> product 순차 배포를 한다.
// 호스트 이름·자격 증명 ID·승인 그룹은 예시 값이다. 실제 서버에 맞게 바꾼다(docs/dev-guide.html 16장).
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
                        sh 'bash -n infra/server/deploy.sh infra/server/bootstrap.sh infra/build_release.sh'
                        sh 'bash infra/server/tests/test_deploy.sh'
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
                sh 'infra/build_release.sh "$RELEASE_TAG"'
                archiveArtifacts artifacts: 'build/*.tar.gz', fingerprint: true
                stash name: 'release', includes: 'build/*.tar.gz'
            }
        }

        stage('Deploy: Dev') {
            when { branch 'main' }
            agent { label 'deploy' }
            steps {
                unstash 'release'
                lock(resource: 'neoine-dev') {
                    withCredentials([sshUserPrivateKey(credentialsId: 'deploy-ssh-dev',
                                                       keyFileVariable: 'SSH_KEY',
                                                       usernameVariable: 'SSH_USER')]) {
                        // 번들과 같은 커밋의 deploy.sh를 함께 전달한다(스크립트도 코드와 함께 버전 관리)
                        sh '''
                            scp -i "$SSH_KEY" -o StrictHostKeyChecking=yes \
                                "build/neoine-sales-$RELEASE_TAG.tar.gz" infra/server/deploy.sh \
                                "$SSH_USER@dev.internal.example.com:/opt/neoine-sales/incoming/"
                            ssh -i "$SSH_KEY" -o StrictHostKeyChecking=yes "$SSH_USER@dev.internal.example.com" \
                                "bash /opt/neoine-sales/incoming/deploy.sh dev $RELEASE_TAG"
                        '''
                    }
                }
                sh 'curl --fail --retry 5 --retry-delay 3 https://dev.internal.example.com/readyz'
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
                unstash 'release'
                lock(resource: 'neoine-product') {
                    withCredentials([sshUserPrivateKey(credentialsId: 'deploy-ssh-product',
                                                       keyFileVariable: 'SSH_KEY',
                                                       usernameVariable: 'SSH_USER')]) {
                        // 서버를 한 대씩 순차 배포(롤링). 한 대라도 실패하면 중단
                        sh '''
                            for host in prd1.internal.example.com prd2.internal.example.com; do
                                scp -i "$SSH_KEY" -o StrictHostKeyChecking=yes \
                                    "build/neoine-sales-$RELEASE_TAG.tar.gz" infra/server/deploy.sh \
                                    "$SSH_USER@$host:/opt/neoine-sales/incoming/"
                                ssh -i "$SSH_KEY" -o StrictHostKeyChecking=yes "$SSH_USER@$host" \
                                    "bash /opt/neoine-sales/incoming/deploy.sh product $RELEASE_TAG"
                            done
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
