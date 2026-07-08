# nn_meta/live/notifier.py
"""Push a signal alert to the user's phone.

Telegram is the chosen transport (free, unlimited, instant): one HTTPS POST
to the Bot API. Pushover remains as an alternative; console is the fallback
when no credentials are set, so the scanner runs in --dry-run and tests
without any secrets or network.

Env (first configured transport wins, in this order):
    TELEGRAM_BOT_TOKEN — bot API token from @BotFather
    TELEGRAM_CHAT_ID   — destination chat (discover via getUpdates after
                         messaging the bot once)
    PUSHOVER_TOKEN     — application API token
    PUSHOVER_USER      — user/group key
"""
from __future__ import annotations

import os
from abc import ABC, abstractmethod

import requests

from utils.logging_utils import setup_logging

logger = setup_logging(log_file="logs/backtester.log")

_PUSHOVER_URL = "https://api.pushover.net/1/messages.json"
_TELEGRAM_URL = "https://api.telegram.org/bot{token}/sendMessage"
_TIMEOUT = 15


class Notifier(ABC):
    @abstractmethod
    def send(self, message: str, title: str = "Signal") -> bool:
        """Return True on successful delivery."""


class ConsoleNotifier(Notifier):
    """Prints instead of sending — for --dry-run and tests."""

    def send(self, message: str, title: str = "Signal") -> bool:
        print(f"\n🔔 [{title}]\n{message}\n", flush=True)
        logger.info(f"[notify:console] {title}: {message}")
        return True


class PushoverNotifier(Notifier):
    def __init__(self, token: str, user: str,
                 session: requests.Session | None = None):
        self._token = token
        self._user = user
        self._session = session or requests.Session()

    def send(self, message: str, title: str = "Signal") -> bool:
        try:
            r = self._session.post(_PUSHOVER_URL, data={
                "token": self._token, "user": self._user,
                "message": message, "title": title,
            }, timeout=_TIMEOUT)
        except requests.RequestException as e:
            logger.error(f"[notify:pushover] request failed: {e}")
            return False
        if r.status_code != 200:
            logger.error(f"[notify:pushover] HTTP {r.status_code}: {r.text[:160]}")
            return False
        logger.info(f"[notify:pushover] sent: {title}")
        return True


class TelegramNotifier(Notifier):
    def __init__(self, token: str, chat_id: str,
                 session: requests.Session | None = None):
        self._url = _TELEGRAM_URL.format(token=token)
        self._chat_id = chat_id
        self._session = session or requests.Session()

    def send(self, message: str, title: str = "Signal") -> bool:
        try:
            r = self._session.post(self._url, data={
                "chat_id": self._chat_id,
                "text": f"🔔 {title}\n{message}",
            }, timeout=_TIMEOUT)
        except requests.RequestException as e:
            logger.error(f"[notify:telegram] request failed: {e}")
            return False
        if r.status_code != 200:
            logger.error(f"[notify:telegram] HTTP {r.status_code}: {r.text[:160]}")
            return False
        logger.info(f"[notify:telegram] sent: {title}")
        return True


def get_notifier(force_console: bool = False) -> Notifier:
    """First configured transport wins: Telegram, then Pushover, else console."""
    tg_token = os.environ.get("TELEGRAM_BOT_TOKEN", "")
    tg_chat = os.environ.get("TELEGRAM_CHAT_ID", "")
    if not force_console and tg_token and tg_chat:
        return TelegramNotifier(tg_token, tg_chat)
    token = os.environ.get("PUSHOVER_TOKEN", "")
    user = os.environ.get("PUSHOVER_USER", "")
    if not force_console and token and user:
        return PushoverNotifier(token, user)
    if not force_console:
        logger.warning("[notify] no TELEGRAM_*/PUSHOVER_* creds — using console notifier")
    return ConsoleNotifier()
