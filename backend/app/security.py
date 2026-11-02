import hashlib
import hmac
import json
import secrets
import time
from urllib.parse import parse_qsl

from .config import settings

_ALGO = "pbkdf2_sha256"


def hash_password(password: str, iterations: int | None = None) -> str:
    iterations = iterations or settings.password_iterations
    salt = secrets.token_hex(16)
    digest = hashlib.pbkdf2_hmac("sha256", password.encode(), salt.encode(), iterations).hex()
    return f"{_ALGO}${iterations}${salt}${digest}"


def verify_password(password: str, encoded: str) -> bool:
    try:
        algo, iterations, salt, digest = encoded.split("$")
    except ValueError:
        return False
    if algo != _ALGO:
        return False
    candidate = hashlib.pbkdf2_hmac("sha256", password.encode(), salt.encode(), int(iterations)).hex()
    return hmac.compare_digest(candidate, digest)


class InvalidInitData(ValueError):
    pass


def verify_telegram_init_data(init_data: str, bot_token: str, max_age_seconds: int) -> dict:
    """Validate Telegram WebApp initData and return the `user` object.

    Algorithm from https://core.telegram.org/bots/webapps#validating-data-received-via-the-mini-app:
    secret = HMAC_SHA256(key="WebAppData", msg=bot_token);
    hash   = hex(HMAC_SHA256(key=secret, msg=data_check_string)),
    where data_check_string is the sorted `key=value` pairs (without `hash`) joined by "\\n".
    """
    pairs = dict(parse_qsl(init_data, keep_blank_values=True, strict_parsing=False))
    received_hash = pairs.pop("hash", None)
    if not received_hash:
        raise InvalidInitData("нет подписи")
    data_check_string = "\n".join(f"{k}={v}" for k, v in sorted(pairs.items()))
    secret = hmac.new(b"WebAppData", bot_token.encode(), hashlib.sha256).digest()
    expected = hmac.new(secret, data_check_string.encode(), hashlib.sha256).hexdigest()
    if not hmac.compare_digest(expected, received_hash):
        raise InvalidInitData("неверная подпись")

    try:
        auth_date = int(pairs.get("auth_date", "0"))
    except ValueError:
        raise InvalidInitData("некорректная дата") from None
    if max_age_seconds and time.time() - auth_date > max_age_seconds:
        raise InvalidInitData("данные устарели, перезапустите приложение")

    try:
        user = json.loads(pairs.get("user", ""))
        user["id"] = int(user["id"])
    except (ValueError, KeyError, TypeError):
        raise InvalidInitData("нет данных пользователя") from None
    return user


def new_token() -> str:
    return secrets.token_urlsafe(32)


def hash_token(token: str) -> str:
    return hashlib.sha256(token.encode()).hexdigest()
