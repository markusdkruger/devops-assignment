import os
from flask import Flask
app = Flask(__name__)

@app.route('/', methods=['GET'])
def home():
    return '''<h1>Default API Route - Devops Assignment Python Application</h1>'''

@app.route('/message', methods=['GET'])
def message():
    return os.environ.get('ENV_MESSAGE', '')

@app.route('/messageFromFile', methods=['GET'])
def messageFromFIle():
    app.config.from_pyfile('/tmp/config.cfg')
    print(os.environ)
    return app.config['MESSAGE']

if __name__ == '__main__':
    app.run(host="0.0.0.0", port=5000)