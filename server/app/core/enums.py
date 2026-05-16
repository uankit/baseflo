from __future__ import annotations

from enum import StrEnum


class UserStatus(StrEnum):
    ACTIVE = "active"
    SUSPENDED = "suspended"
    DELETED = "deleted"


class OrgPlan(StrEnum):
    FREE = "free"
    PRO = "pro"
    TEAM = "team"
    ENTERPRISE = "enterprise"


class Role(StrEnum):
    OWNER = "owner"
    ADMIN = "admin"
    MEMBER = "member"
    VIEWER = "viewer"


class MembershipStatus(StrEnum):
    ACTIVE = "active"
    PENDING = "pending"
    REVOKED = "revoked"


class MagicLinkPurpose(StrEnum):
    SIGN_IN = "sign_in"


class TokenType(StrEnum):
    ACCESS = "access"
    REFRESH = "refresh"


class ConnectionStatus(StrEnum):
    ACTIVE = "active"
    ERROR = "error"
    DISCONNECTED = "disconnected"


class DataSourceStatus(StrEnum):
    ACTIVE = "active"
    ERROR = "error"
    DISCONNECTED = "disconnected"


class AuthEventKind(StrEnum):
    SIGNUP = "signup"
    LOGIN = "login"
    LOGIN_FAILED = "login_failed"
    LOGOUT = "logout"
    MAGIC_LINK_REQUESTED = "magic_link_requested"
    MAGIC_LINK_CONSUMED = "magic_link_consumed"
    REFRESH_TOKEN_ISSUED = "refresh_token_issued"
    REFRESH_TOKEN_ROTATED = "refresh_token_rotated"
    REFRESH_TOKEN_REVOKED = "refresh_token_revoked"
    ORG_CREATED = "org_created"
    MEMBERSHIP_CREATED = "membership_created"
    MEMBERSHIP_REVOKED = "membership_revoked"
    INVITATION_SENT = "invitation_sent"
    INVITATION_ACCEPTED = "invitation_accepted"
    INVITATION_REVOKED = "invitation_revoked"
