"""Turn database driver errors into safe, actionable messages, and retry connecting when it can help.

Standard library only, and no driver import, so the rules are unit-tested without psycopg or a
database. The Postgres adapter passes its exceptions in; the rules read only the exception text and
SQLSTATE. A message produced here never repeats the driver text, because that text can contain the
host, user or project id from DATABASE_URL.

Why connecting is retried but operations are not: a failed connect has done nothing, so trying again
is safe. An operation that fails mid-transaction has been rolled back by the server and the session
is gone; replaying it on a new connection could repeat half of a multi-step command. Every pfq load
is idempotent, so the safe recovery for an operation is to re-run the whole command.
"""

from __future__ import annotations

import time
from dataclasses import dataclass
from typing import Callable, TypeVar

from ...core.errors import StorageError

T = TypeVar("T")


@dataclass(frozen=True)
class DbFailure:
    kind: str
    message: str
    transient: bool  # worth retrying the connect


# (kind, any-of substrings (lowercase), SQLSTATE codes, transient, message). First match wins.
_RULES: tuple[tuple[str, tuple[str, ...], tuple[str, ...], bool, str], ...] = (
    (
        "project_unavailable",
        ("tenant/user", "tenant or user not found"),
        (),
        False,
        "Supabase's connection pooler does not recognize this project. On the free plan the project is "
        "most likely paused after about 7 days without activity: restore it in the Supabase dashboard "
        "and try again. If it is active, check the user name in DATABASE_URL",
    ),
    (
        "auth_failed",
        ("password authentication failed",),
        ("28P01", "28000"),
        False,
        "the database rejected the user or password in DATABASE_URL",
    ),
    (
        "host_unknown",
        ("could not translate host name", "nodename nor servname", "name or service not known",
         "temporary failure in name resolution"),
        (),
        False,
        "the database host name in DATABASE_URL could not be resolved; check the host and your network",
    ),
    (
        "too_many_connections",
        ("max client connections", "too many clients", "remaining connection slots"),
        ("53300",),
        True,
        "the database has no free connection slots (too many open connections); close other clients "
        "or wait a moment and try again",
    ),
    (
        "timeout",
        ("timeout expired", "timed out", "connection timeout"),
        (),
        True,
        "the database did not answer in time; it may still be starting up, or the network may block "
        "the port in DATABASE_URL",
    ),
    (
        "refused",
        ("connection refused",),
        (),
        False,
        "the database refused the connection; check the host and port in DATABASE_URL",
    ),
    (
        "connection_lost",
        ("server closed the connection", "connection is closed", "connection is lost", "ssl syscall",
         "consuming input failed", "terminating connection", "eof detected"),
        ("57P01", "08006", "08003"),
        False,
        "the connection to the database was lost during the command; the open transaction was rolled "
        "back by the server, nothing partial was saved. Re-run the command (loads are idempotent)",
    ),
)


def classify(exc: BaseException) -> DbFailure:
    """Map a driver exception to a safe message. Unrecognized errors get a generic message."""
    text = str(exc).lower()
    sqlstate = getattr(exc, "sqlstate", None) or ""
    for kind, needles, codes, transient, message in _RULES:
        if sqlstate in codes or any(needle in text for needle in needles):
            return DbFailure(kind, message, transient)
    return DbFailure(
        "unknown",
        f"the database reported an error ({type(exc).__name__}); set PFQ_DEBUG=1 to see the driver "
        "message (it may include the host from DATABASE_URL)",
        False,
    )


def connect_with_retry(
    connect: Callable[[], T],
    driver_error: type[BaseException] | tuple[type[BaseException], ...],
    attempts: int = 3,
    first_delay: float = 2.0,
    sleep: Callable[[float], None] = time.sleep,
) -> T:
    """Call `connect`, retrying only transient failures with doubling delays.

    Raises StorageError with a classified message once a failure is not transient or the attempts
    are used up. The driver exception is not chained, so a traceback cannot echo it.
    """
    delay = first_delay
    for attempt in range(1, attempts + 1):
        try:
            return connect()
        except driver_error as exc:
            failure = classify(exc)
            if not failure.transient or attempt == attempts:
                tried = f" (tried {attempt} times)" if attempt > 1 else ""
                raise StorageError(f"could not connect to the database: {failure.message}{tried}") from None
        sleep(delay)
        delay *= 2
    raise AssertionError("unreachable")  # pragma: no cover
