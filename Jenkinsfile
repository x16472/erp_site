pipeline {
    agent { label 'linux-docker' }

    options {
        skipDefaultCheckout(true)
        disableConcurrentBuilds()
        timeout(time: 120, unit: 'MINUTES')
        buildDiscarder(logRotator(numToKeepStr: '20'))
    }

    stages {
        stage('Checkout') {
            steps {
                script {
                    def checkoutInfo = checkout scm
                    env.ERP_IMAGE = "erp-site:ci-${env.BUILD_NUMBER}-${checkoutInfo.GIT_COMMIT}"
                }
            }
        }

        stage('Check Docker environment') {
            steps {
                sh '''
                    set -eu
                    test "$(docker info --format '{{.OSType}}')" = linux
                    docker compose version
                    docker compose -f docker-compose.yml config --quiet
                '''
            }
        }

        stage('Go tests and vet') {
            steps {
                sh 'docker build --platform linux/amd64 -f dockerfile --target go_test .'
            }
        }

        stage('Frontend tests') {
            steps {
                sh 'docker build --platform linux/amd64 -f dockerfile --target frontend_test .'
            }
        }

        stage('Python tests on Alpine') {
            steps {
                sh 'docker build --platform linux/amd64 -f dockerfile --target python_test .'
            }
        }

        stage('Build Alpine image') {
            steps {
                sh '''
                    set -eu
                    docker compose -f docker-compose.yml build erp_service
                    docker image inspect --format '{{.Id}}' "$ERP_IMAGE" > image-id.txt
                    printf '%s\\n' "$ERP_IMAGE" > image-tag.txt
                '''
                archiveArtifacts artifacts: 'image-id.txt,image-tag.txt', fingerprint: true
            }
        }
    }
}
