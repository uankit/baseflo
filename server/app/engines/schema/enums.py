"""Schema-level enums.

Defined in their own module so agent input/output models can import them
without pulling in the full IR (which transitively imports SemanticType
and would otherwise create a cycle).
"""

from __future__ import annotations

from enum import StrEnum


class SemanticType(StrEnum):
    """What a column *means* in the business — set by `ColumnClassifier`.

    Distinct from `PhysicalType` (storage representation). The agent decides
    semantic; the compiler chooses physical from semantic + observed values.
    """

    IDENTITY = "identity"                 # primary-key-like; uniquely names a row
    FOREIGN_KEY = "foreign_key"           # references another entity's identity
    MONEY = "money"                       # currency-bearing amount
    STATUS = "status"                     # enum-shaped lifecycle / state
    TEMPORAL = "temporal"                 # timestamp / date
    PII_EMAIL = "pii_email"
    PII_PHONE = "pii_phone"
    PII_ADDRESS = "pii_address"
    PII_NAME = "pii_name"
    PII_ID_NUMBER = "pii_id_number"
    CATEGORY = "category"                 # low-cardinality classification, non-status
    FREE_TEXT = "free_text"               # unbounded text
    BOOLEAN = "boolean"
    COUNT = "count"                       # non-negative integer
    DERIVED = "derived"                   # synthetic / computed; not a real input


PII_SEMANTIC_TYPES: frozenset[SemanticType] = frozenset(
    {
        SemanticType.PII_EMAIL,
        SemanticType.PII_PHONE,
        SemanticType.PII_ADDRESS,
        SemanticType.PII_NAME,
        SemanticType.PII_ID_NUMBER,
    }
)


class PhysicalType(StrEnum):
    UUID = "uuid"
    BIGINT = "bigint"
    INT = "int"
    SMALLINT = "smallint"
    NUMERIC = "numeric"
    TEXT = "text"
    VARCHAR = "varchar"
    BOOLEAN = "boolean"
    TIMESTAMPTZ = "timestamptz"
    DATE = "date"
    JSONB = "jsonb"
    BYTEA = "bytea"


class Cardinality(StrEnum):
    """Form `from..to`. `1..*` = one row on the from-side relates to many on
    the to-side. The deterministic compiler places the FK on the many-side."""

    ONE_TO_ONE = "1..1"
    ONE_TO_MANY = "1..*"
    MANY_TO_ONE = "*..1"
    MANY_TO_MANY = "*..*"


class OnDelete(StrEnum):
    RESTRICT = "RESTRICT"
    CASCADE = "CASCADE"
    SET_NULL = "SET NULL"


class MergeStrategy(StrEnum):
    """How a reconciled entity composes rows from multiple sources."""

    PREFERRED_SOURCE = "preferred_source"
    LATEST_WRITE_WINS = "latest_write_wins"
    UNION = "union"
    AGGREGATE = "aggregate"


class JoinTransform(StrEnum):
    """Normalization applied to columns before equality comparison in a JoinKey."""

    EXACT = "exact"
    LOWERCASE_TRIM = "lowercase_trim"
    DIGITS_ONLY = "digits_only"            # for phone / id-number normalization


class PrimaryKeyStrategy(StrEnum):
    GENERATED_UUID = "generated_uuid"
    COMPOSITE_FROM_SOURCES = "composite_from_sources"
    INHERIT_AUTHORITATIVE = "inherit_authoritative"


class SourceRole(StrEnum):
    AUTHORITATIVE_PRIMARY = "authoritative_primary"
    AUGMENTING = "augmenting"
    LOG_ONLY = "log_only"
