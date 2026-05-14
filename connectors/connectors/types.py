from __future__ import annotations

from enum import Enum


class DataType(str, Enum):
    TEXT = "text"
    INTEGER = "integer"
    NUMBER = "number"
    BOOLEAN = "boolean"
    DATE = "date"
    DATETIME = "datetime"
    JSON = "json"
    EMAIL = "email"
    URL = "url"
    MONEY = "money"
    UNKNOWN = "unknown"


class AuthMethod(str, Enum):
    NONE = "none"
    API_KEY = "api_key"
    OAUTH2 = "oauth2"
    BASIC = "basic"


class Capability(str, Enum):
    INTROSPECT = "introspect"
    READ = "read"
    WRITE = "write"
    WEBHOOK = "webhook"
    LIST_RESOURCES = "list_resources"  # can enumerate available resources for credentials
