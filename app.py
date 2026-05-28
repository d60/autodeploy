import hmac
import json
from waitress import serve

from flask import Flask, Response, request

from .core import FlaskAppConfig, ProcessManager

__all__ = ['setup', 'run']

app = Flask(__name__)


WEBHOOK_SECRET = None
APP_CONFIGS = None


####### Interface ######

def setup(webhook_secret: str, configs: list[FlaskAppConfig]):
    global WEBHOOK_SECRET, APP_CONFIGS
    WEBHOOK_SECRET = webhook_secret
    APP_CONFIGS = configs


def run(*args, **kwargs):
    if WEBHOOK_SECRET is None or APP_CONFIGS is None:
        raise RuntimeError('Setup is not complete. Call `setup(...)` first.')

    global process_manager
    process_manager = ProcessManager(APP_CONFIGS)
    process_manager.start_all_processes()
    serve(app, *args, **kwargs)

##########################


def verify_signature(header_signature, body):
    if not header_signature:
        return False

    sha_name, signature = header_signature.split('=')
    if sha_name != 'sha256':
        return False

    local_signature = hmac.new(WEBHOOK_SECRET.encode(), msg=body, digestmod='sha256')
    return hmac.compare_digest(local_signature.hexdigest(), signature)


@app.post('/')
def webhook():
    header_signature = request.headers.get('X-Hub-Signature-256')
    body = request.get_data()

    if not verify_signature(header_signature, body):
        return Response('Bad Request', 400)

    data = json.loads(body)
    repo = data['repository']['clone_url']
    process_manager.app_processes[repo].update()

    return 'ok'
