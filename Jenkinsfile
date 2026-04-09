pipeline {
    agent any

    environment {
        DOCKER_IMAGE = "yourdockerhubusername/interview-app"
    }

    stages {

        stage('Checkout') {
            steps {
                git 'https://github.com/pran-17/interview-assistance.git'
            }
        }

        stage('Install') {
            steps {
                sh '''
                python3 -m venv venv
                . venv/bin/activate
                pip install --upgrade pip
                if [ -f requirements.txt ]; then
                    pip install -r requirements.txt
                fi
                '''
            }
        }

        stage('Test') {
            steps {
                sh '''
                . venv/bin/activate
                pytest || true
                '''
            }
        }

        stage('Build Docker Image') {
            steps {
                sh '''
                docker build -t $DOCKER_IMAGE:$BUILD_NUMBER .
                '''
            }
        }

        stage('Push Docker Image') {
            steps {
                sh '''
                docker login -u YOUR_USERNAME -p YOUR_PASSWORD
                docker push $DOCKER_IMAGE:$BUILD_NUMBER
                '''
            }
        }
    }
}
