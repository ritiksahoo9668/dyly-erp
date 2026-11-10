"""Production settings. Secrets must come from the environment."""

from utils.env import env_bool

from .base import *  # noqa: F403

DEBUG = False

if SECRET_KEY == "dev-only-change-me":
    raise RuntimeError("Set SECRET_KEY before using production settings.")

SECURE_CONTENT_TYPE_NOSNIFF = True
SESSION_COOKIE_SECURE = env_bool("SESSION_COOKIE_SECURE", False)
CSRF_COOKIE_SECURE = env_bool("CSRF_COOKIE_SECURE", False)
SECURE_SSL_REDIRECT = env_bool("SECURE_SSL_REDIRECT", False)
