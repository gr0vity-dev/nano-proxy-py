from flask import Flask, request, jsonify, abort
from functools import wraps
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address
import os
import importlib
import settings
import requests
from typing import Dict, Any, Optional

# App initialization
app = Flask(__name__)
limiter = Limiter(app=app, key_func=get_remote_address, storage_uri=os.getenv(
    'MEMCACHED_URI', 'memcached://localhost:11211'))

# Configuration Management


class ConfigManager:
    def __init__(self, settings_module):
        self.settings_module = settings_module
        self.mod_time = os.path.getmtime(settings_module.__file__)
        self.load_configs()

    def load_configs(self):
        self.tokens_config = getattr(self.settings_module, "TOKENS", {})
        self.commands_config = getattr(self.settings_module, "COMMANDS", {})
        self.endpoint = getattr(self.settings_module, "endpoint", None)

    def check_and_reload(self):
        current_mod_time = os.path.getmtime(self.settings_module.__file__)
        if current_mod_time != self.mod_time:
            print("Configuration changed, reloading...")
            importlib.reload(self.settings_module)
            self.mod_time = current_mod_time
            self.load_configs()


config_manager = ConfigManager(settings)

# Decorators


def auto_reload_config(func):
    @wraps(func)
    def wrapper(*args, **kwargs):
        config_manager.check_and_reload()
        return func(*args, **kwargs)
    return wrapper


def rate_limit_from_header():
    """Extracts the rate limit from the configuration based on the Authorization header."""
    auth_header = request.headers.get('Authorization')
    token = ""
    if auth_header and auth_header.startswith('Bearer '):
        token = auth_header.split(' ')[1]

    rate_limit = get_rate_limit_from_token(token)
    return rate_limit


def verify_token_and_command(func):
    @wraps(func)
    def wrapper(*args, **kwargs):
        token = request.headers.get('Authorization', '').split(' ')[-1]
        json_data = request.get_json(force=True) or {}
        command = json_data.get('action')

        if not is_authorized(token, command, json_data):
            abort(403, description="Unauthorized or Command not allowed")
        return func(*args, **kwargs)
    return wrapper

# Helper Functions


def get_rate_limit_from_token(token: str) -> str:
    for user, user_token in config_manager.tokens_config.items():
        if user_token == token:
            user_config = config_manager.commands_config.get(user)
            if user_config:
                return user_config.get("rate_limit", "1 per second")
    return config_manager.commands_config.get("public", {}).get("rate_limit", "1 per second")


def is_authorized(token: str, command: Optional[str], json_data: Dict[str, Any]) -> bool:
    user = next((user for user, user_token in config_manager.tokens_config.items(
    ) if user_token == token), None)
    if user:
        allowed_commands = config_manager.commands_config.get(
            user, {}).get("commands", [])
        forced_values = config_manager.commands_config.get(
            user, {}).get("forced_values", {}).get(command, {})
        for key, value in forced_values.items():
            json_data[key] = value
        return command in allowed_commands
    return command in config_manager.commands_config.get('public', {}).get("commands", [])

# Routes


@app.route('/reload', methods=['GET'])
@auto_reload_config
def reload_configs():
    config_manager.load_configs()
    return jsonify({"message": "Configuration reloaded successfully."})


@app.route('/rpc', methods=['POST'])
@auto_reload_config
@verify_token_and_command
@limiter.limit(rate_limit_from_header)
def rpc_proxy():
    json_data = request.get_json(force=True)
    try:
        response = requests.post(config_manager.endpoint, json=json_data)
        return jsonify(response.json()), response.status_code
    except requests.RequestException as e:
        return jsonify({'error': 'Failed to forward request', 'message': str(e)}), 502


if __name__ == '__main__':
    app.run(debug=True)
