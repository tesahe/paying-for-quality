"""Database failure handling (Sprint 4, DC-9): classified messages, connect retry, guarded operations.

No database and no psycopg needed: driver errors are stood in for by a small exception class that
carries the same text and SQLSTATE the real driver produces. The paused-project text below is the
pooler's real reply, observed on 2026-11-22 with the host, user and addresses replaced.
"""

import pytest

from paying_for_quality.adapters.storage.db_errors import classify, connect_with_retry
from paying_for_quality.adapters.storage.postgres_repository import GuardedConnection
from paying_for_quality.core.errors import StorageError

SECRET_HOST = "aws-0-us-east-1.pooler.supabase.com"
SECRET_USER = "postgres.rhfuunhdgtkusntauvdyXX"


class FakeDriverError(Exception):
    def __init__(self, text: str, sqlstate: str | None = None) -> None:
        super().__init__(text)
        self.sqlstate = sqlstate


PAUSED = FakeDriverError(
    f'connection failed: connection to server at "10.0.0.1", port 5432 failed: FATAL:  (ENOTFOUND) '
    f"tenant/user {SECRET_USER} not found\nMultiple connection attempts failed. host: '{SECRET_HOST}'"
)
TIMEOUT = FakeDriverError(f"connection timeout expired (host '{SECRET_HOST}')")
SLOTS = FakeDriverError("FATAL: Max client connections reached")
BAD_PASSWORD = FakeDriverError(f'FATAL: password authentication failed for user "{SECRET_USER}"', "28P01")
DNS = FakeDriverError(f'could not translate host name "{SECRET_HOST}" to address: nodename nor servname provided')
REFUSED = FakeDriverError('connection to server at "127.0.0.1", port 1 failed: Connection refused')
LOST = FakeDriverError("server closed the connection unexpectedly\n\tThis probably means the server terminated")


@pytest.mark.parametrize(
    "error, kind, transient",
    [
        (PAUSED, "project_unavailable", False),
        (BAD_PASSWORD, "auth_failed", False),
        (DNS, "host_unknown", False),
        (SLOTS, "too_many_connections", True),
        (FakeDriverError("sorry, too many clients already", "53300"), "too_many_connections", True),
        (TIMEOUT, "timeout", True),
        (REFUSED, "refused", False),
        (LOST, "connection_lost", False),
        (FakeDriverError("terminating connection due to administrator command", "57P01"), "connection_lost", False),
        (FakeDriverError("something new"), "unknown", False),
    ],
)
def test_classify_names_the_cause(error, kind, transient):  # AC-DC-9.1
    failure = classify(error)
    assert (failure.kind, failure.transient) == (kind, transient)


def test_paused_project_says_restore_it_not_check_the_url():  # AC-DC-9.1
    # The Sprint 3 message ("check DATABASE_URL in .env") sent the user to the wrong place.
    assert "paused" in classify(PAUSED).message and "restore it" in classify(PAUSED).message


@pytest.mark.parametrize("error", [PAUSED, TIMEOUT, BAD_PASSWORD, DNS, FakeDriverError(f"x {SECRET_HOST}")])
def test_messages_never_repeat_connection_details(error):  # AC-DC-9.3
    message = classify(error).message
    assert SECRET_HOST not in message and SECRET_USER not in message and "rhfuunhdgtkusntauvdy" not in message


class Attempts:
    def __init__(self, *outcomes):
        self.outcomes = list(outcomes)
        self.calls = 0

    def __call__(self):
        self.calls += 1
        outcome = self.outcomes.pop(0)
        if isinstance(outcome, BaseException):
            raise outcome
        return outcome


def test_transient_failure_is_retried_with_doubling_delays():  # AC-DC-9.2
    connect, slept = Attempts(TIMEOUT, SLOTS, "conn"), []
    assert connect_with_retry(connect, FakeDriverError, attempts=3, first_delay=2, sleep=slept.append) == "conn"
    assert connect.calls == 3 and slept == [2, 4]


def test_permanent_failure_is_not_retried():  # AC-DC-9.2
    connect, slept = Attempts(PAUSED, "never"), []
    with pytest.raises(StorageError, match="paused") as exc:
        connect_with_retry(connect, FakeDriverError, sleep=slept.append)
    assert connect.calls == 1 and slept == []
    assert exc.value.__cause__ is None and exc.value.__suppress_context__  # driver text not chained


def test_retries_stop_after_the_limit_and_say_so():
    connect, slept = Attempts(TIMEOUT, TIMEOUT, TIMEOUT), []
    with pytest.raises(StorageError, match=r"did not answer in time.*tried 3 times"):
        connect_with_retry(connect, FakeDriverError, attempts=3, sleep=slept.append)
    assert slept == [2.0, 4.0]


def test_other_exceptions_pass_through_untouched():
    with pytest.raises(ValueError):
        connect_with_retry(Attempts(ValueError("bug")), FakeDriverError, sleep=lambda _: None)


class DroppingConnection:
    """A connection that loses the server on execute, and whose rollback then fails as well."""

    def __init__(self):
        self.closed = False

    def execute(self, *args, **kwargs):
        raise LOST

    def commit(self):
        raise LOST

    def rollback(self):
        raise FakeDriverError("the connection is closed")

    def close(self):
        self.closed = True


def test_dropped_connection_mid_operation_becomes_a_handled_error():  # AC-DC-9.4
    guarded = GuardedConnection(DroppingConnection(), FakeDriverError)
    with pytest.raises(StorageError, match="lost during the command.*Re-run") as exc:
        guarded.execute("SELECT 1")
    assert isinstance(exc.value.__cause__, FakeDriverError)  # kept for PFQ_DEBUG


def test_failed_rollback_does_not_hide_the_original_error():  # AC-DC-9.4
    from paying_for_quality.adapters.storage.sql_repository import SqlRepository

    repo = SqlRepository(GuardedConnection(DroppingConnection(), FakeDriverError))
    with pytest.raises(StorageError, match="lost during the command"):
        with repo._transaction():
            repo._execute("INSERT INTO x VALUES (1)")


def test_test_teardown_drops_the_schema_over_a_fresh_connection_when_the_old_one_died():
    from tests.conftest import _drop_test_schema

    events = []

    class Repo:
        def __init__(self, url=None, schema=None, dead=False):
            self.dead = dead

        def drop_schema(self):
            if self.dead:
                raise StorageError("database operation failed: connection lost")
            events.append("dropped")

        def close(self):
            events.append("closed")

    _drop_test_schema(Repo(dead=True), "url", "pfq_test_x", Repo)
    assert events == ["dropped", "closed", "closed"]  # fresh drop + fresh close, then the dead one closed
