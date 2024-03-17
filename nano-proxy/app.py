from flask import Flask, request, jsonify, abort, current_app
from functools import wraps
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address
from src.config_manager import ConfigManager
from typing import Dict, Any, Optional
from os import getenv
from src.authentication import AuthStrategy, BasicAuthStrategy, BearerAuthStrategy, UnAuthStrategy
import settings
import requests
import logging

# Configure logging
logging.basicConfig(level=logging.INFO,
                    format='[%(asctime)s] [%(levelname)s] %(message)s')
logger = logging.getLogger(__name__)

app = Flask(__name__)
limiter = Limiter(app=app, key_func=get_remote_address, storage_uri=getenv(
    'MEMCACHED_URI', 'memcached://localhost:11211'))
config_manager = ConfigManager(settings)

# ----------------
# Helper Functions
# ----------------


def log_rpc_request(user, request_body):
    log_disabled = getenv('LOG_DISABLED', 'false').lower() in ['true', '1']

    # Return early if logging is explicitly disabled
    if log_disabled:
        return

    # Determine whether to log request headers and body based on environment variables
    log_request_headers = getenv(
        'LOG_REQUEST_HEADERS', 'false').lower() in ['true', '1']
    log_request_body = getenv('LOG_REQUEST_BODY', 'false').lower() in [
        'true', '1']
    origin = request.headers.get('X-Forwarded-For', request.remote_addr)
    # Exclude the Authorization header from logging
    headers_to_log = {k: v for k, v in request.headers.items()
                      if k.lower() != 'authorization'}
    headers_log = ', '.join(
        [f"{k}: {v}" for k, v in headers_to_log.items()]) if log_request_headers else ""
    body_log = request_body if log_request_body else ""
    logger.info(f"|{user}| |{origin}| |{body_log}| |{headers_log}|")


def get_auth_strategy(auth_header: str) -> AuthStrategy:
    if auth_header.startswith('Bearer '):
        return BearerAuthStrategy(auth_header)
    elif auth_header.startswith('Basic '):
        return BasicAuthStrategy(auth_header)
    else:
        return UnAuthStrategy("")


def get_authorised_details():
    auth_header = request.headers.get('Authorization', '')
    strategy = get_auth_strategy(auth_header)
    credentials = strategy.extract_credentials()
    if not strategy.is_authorized(credentials):
        abort(403, description="Unauthorized")

    return strategy, credentials


def handle_authorization_and_rate_limiting():
    strategy, credentials = get_authorised_details()
    rate_limit = strategy.get_rate_limit(credentials)
    return rate_limit


def prepare_command(request_body: Dict[str, Any]) -> bool:
    _, credentials = get_authorised_details()
    user = credentials[0]
    log_rpc_request(user, request_body)

    command = request_body.get('action')
    allowed_commands = config_manager.commands_config.get(
        user, {}).get("commands", [])
    forced_values = config_manager.commands_config.get(
        user, {}).get("forced_values", {}).get(command, {})
    for key, value in forced_values.items():
        request_body[key] = value
    return command in allowed_commands


# ----------
# Decorators
# ----------


def auto_reload_config(func):
    @wraps(func)
    def wrapper(*args, **kwargs):
        config_manager.check_and_reload()
        return func(*args, **kwargs)
    return wrapper


def verify_token_and_command(func):
    @wraps(func)
    def wrapper(*args, **kwargs):
        request_body = request.get_json(force=True) or {}
        if not prepare_command(request_body):
            abort(403, description="Command not allowed")
        return func(*args, **kwargs)
    return wrapper

# ------
# Routes
# ------


@app.route('/rpc', methods=['POST'])
@auto_reload_config
@verify_token_and_command
@limiter.limit(handle_authorization_and_rate_limiting)
def rpc_proxy():
    request_body = request.get_json(force=True)
    try:
        response = requests.post(config_manager.endpoint, json=request_body)
        return jsonify(response.json()), response.status_code
    except requests.RequestException as e:
        return jsonify({'error': 'Failed to forward request', 'message': str(e)}), 502


if __name__ == '__main__':
    app.run(debug=False)
