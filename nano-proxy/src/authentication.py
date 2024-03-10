from typing import Tuple, Optional
from settings import TOKENS, COMMANDS
import base64


class AuthStrategy:
    def extract_credentials(self, auth_header: str) -> Tuple[Optional[str], Optional[str]]:
        raise NotImplementedError

    def is_authorized(self, credentials: Tuple[str, str]) -> bool:
        user, token = credentials
        return TOKENS.get(user) == token

    def get_rate_limit(self, credentials: Tuple[str, str]) -> str:
        return COMMANDS.get(credentials[0]).get("rate_limit", "1 per hour")


class UnAuthStrategy(AuthStrategy):
    def extract_credentials(self, auth_header: str) -> Tuple[Optional[str], Optional[str]]:
        return ("public", "")


class BearerAuthStrategy(AuthStrategy):
    def extract_credentials(self, auth_header: str) -> Tuple[Optional[str], Optional[str]]:
        if auth_header.startswith('Bearer '):
            token = auth_header.split(' ')[1]
            _, credentials = self.get_credentials_from_token(token)
            return credentials
        return (None, None)

    def get_credentials_from_token(self, bearer_token):
        for conf_user, conf_token in TOKENS.items():
            if conf_token == bearer_token:
                return True, (conf_user, conf_token)
        return False, (None, bearer_token)


class BasicAuthStrategy(AuthStrategy):
    def extract_credentials(self, auth_header: str) -> Tuple[Optional[str], Optional[str]]:
        if auth_header.startswith('Basic '):
            decoded = base64.b64decode(
                auth_header.split(' ')[1]).decode('utf-8')
            return tuple(decoded.split(':', 1))
        return (None, None)
