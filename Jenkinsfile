pipeline {
    agent any

    stages {

        stage('Install') {
            steps {
                sh '''
                python3 -m venv venv
                . venv/bin/activate
                pip install --upgrade pip
                pip install -r requirements.txt
                '''
            }
        }

        stage('Test') {
            steps {
                sh '''
                . venv/bin/activate
                pytest
                '''
            }
        }

        stage('Run') {
            steps {
                sh '''
                . venv/bin/activate
                python app.py
                '''
            }
        }
    }
}
