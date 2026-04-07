pipeline {
    agent any

    stages {
        stage('Install') {
            steps {
                sh 'pip3 install -r requirements.txt'
            }
        }

        stage('Test') {
            steps {
                sh 'pytest'
            }
        }

        stage('Run') {
            steps {
                sh 'python3 app.py'
            }
        }
    }
}
