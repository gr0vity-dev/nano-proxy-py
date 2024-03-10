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

app = Flask(__name__)
limiter = Limiter(app=app, key_func=get_remote_address, storage_uri=getenv(
    'MEMCACHED_URI', 'memcached://localhost:11211'))
config_manager = ConfigManager(settings)

# ----------------
# Helper Functions
# ----------------


def get_auth_strategy(auth_header: str) -> AuthStrategy:
    if auth_header.startswith('Bearer '):
        return BearerAuthStrategy()
    elif auth_header.startswith('Basic '):
        return BasicAuthStrategy()
    else:
        return UnAuthStrategy()


def get_authorised_details():
    auth_header = request.headers.get('Authorization', '')
    strategy = get_auth_strategy(auth_header)
    credentials = strategy.extract_credentials(auth_header)
    if not strategy.is_authorized(credentials):
        abort(403, description="Unauthorized or Command not allowed")

    return strategy, credentials


def handle_authorization_and_rate_limiting():
    strategy, credentials = get_authorised_details()
    rate_limit = strategy.get_rate_limit(credentials)
    return rate_limit


def prepare_command(command: Optional[str], json_data: Dict[str, Any]) -> bool:
    _, credentials = get_authorised_details()
    user = credentials[0]

    allowed_commands = config_manager.commands_config.get(
        user, {}).get("commands", [])
    forced_values = config_manager.commands_config.get(
        user, {}).get("forced_values", {}).get(command, {})
    for key, value in forced_values.items():
        json_data[key] = value
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
        json_data = request.get_json(force=True) or {}
        command = json_data.get('action')
        prepare_command(command, json_data)
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
    json_data = request.get_json(force=True)
    try:
        response = requests.post(config_manager.endpoint, json=json_data)
        return jsonify(response.json()), response.status_code
    except requests.RequestException as e:
        return jsonify({'error': 'Failed to forward request', 'message': str(e)}), 502


if __name__ == '__main__':
    app.run(debug=False)
