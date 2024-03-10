
from os import path as os_path
import importlib

# Configuration Management


class ConfigManager:
    def __init__(self, settings_module):
        self.settings_module = settings_module
        self.mod_time = os_path.getmtime(settings_module.__file__)
        self.load_configs()

    def load_configs(self):
        self.tokens_config = getattr(self.settings_module, "TOKENS", {})
        self.commands_config = getattr(self.settings_module, "COMMANDS", {})
        self.endpoint = getattr(self.settings_module, "endpoint", None)

    def check_and_reload(self):
        current_mod_time = os_path.getmtime(self.settings_module.__file__)
        if current_mod_time != self.mod_time:
            print("Configuration changed, reloading...")
            importlib.reload(self.settings_module)
            self.mod_time = current_mod_time
            self.load_configs()
