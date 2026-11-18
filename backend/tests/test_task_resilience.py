"""Tests for resilient Celery/Redis dispatch and health reporting."""
from fastapi import BackgroundTasks
from redis.exceptions import ConnectionError as RedisConnectionError

from app.config import settings
from app.core import task_dispatch
from app.core.task_dispatch import dispatch_task, runtime_mode
from app.routers import health as health_router


class FakeTask:
    name = "fake_task"

    def __init__(self, broker_error=None, task_id="broker-123"):
        self.broker_error = broker_error
        self.task_id = task_id
        self.apply_calls = []

    def run(self, value=None):
        return {"status": "ok", "value": value}

    def apply_async(self, args=None, kwargs=None):
        self.apply_calls.append((args, kwargs))
        if self.broker_error:
            raise self.broker_error

        class AsyncResult:
            id = self.task_id

        return AsyncResult()


def _configure(monkeypatch, testing=False, eager=False, fallback=True):
    monkeypatch.setattr(task_dispatch, "_in_test_environment", lambda: testing)
    monkeypatch.setattr(settings, "celery_task_always_eager", eager)
    monkeypatch.setattr(settings, "use_sync_tasks_fallback", fallback)


def test_test_environment_never_touches_broker(monkeypatch):
    task = FakeTask(broker_error=RedisConnectionError("should not be called"))
    _configure(monkeypatch, testing=True)

    result = dispatch_task(task, 7)

    assert result.mode == "test"
    assert result.task_id.startswith("test-")
    assert task.apply_calls == []


def test_eager_mode_executes_task_inline(monkeypatch):
    task = FakeTask()
    _configure(monkeypatch, eager=True)

    result = dispatch_task(task, 42)

    assert result.mode == "eager"
    assert result.executed is True
    assert result.result == {"status": "ok", "value": 42}
    assert result.task_id.startswith("eager-")
    assert task.apply_calls == []


def test_broker_success_returns_real_task_id(monkeypatch):
    task = FakeTask(task_id="real-abc")
    _configure(monkeypatch)

    result = dispatch_task(task, 1, foo="bar")

    assert result.mode == "broker"
    assert result.task_id == "real-abc"
    assert task.apply_calls == [([1], {"foo": "bar"})]


def test_broker_failure_falls_back_inline(monkeypatch):
    task = FakeTask(broker_error=RedisConnectionError("connection refused"))
    _configure(monkeypatch)

    result = dispatch_task(task, 9)

    assert result.mode == "eager"
    assert result.executed is True
    assert result.result == {"status": "ok", "value": 9}
    assert "connection refused" in result.error


def test_broker_failure_can_use_fastapi_background_tasks(monkeypatch):
    task = FakeTask(broker_error=RedisConnectionError("connection refused"))
    _configure(monkeypatch)
    background_tasks = BackgroundTasks()

    result = dispatch_task(task, 3, background_tasks=background_tasks)

    assert result.mode == "background"
    assert result.executed is False
    assert len(background_tasks.tasks) == 1


def test_fallback_can_be_disabled(monkeypatch):
    task = FakeTask(broker_error=RedisConnectionError("connection refused"))
    _configure(monkeypatch, fallback=False)

    try:
        dispatch_task(task)
    except RedisConnectionError:
        pass
    else:
        raise AssertionError("Expected broker error when fallback is disabled")


def test_runtime_mode_reflects_settings(monkeypatch):
    _configure(monkeypatch, eager=True)
    assert runtime_mode() == "eager_fallback"

    _configure(monkeypatch, eager=False, fallback=True)
    assert runtime_mode() == "broker_with_sync_fallback"

    _configure(monkeypatch, eager=False, fallback=False)
    assert runtime_mode() == "broker_only"


def test_health_reports_fallback_without_failing(client, monkeypatch):
    monkeypatch.setattr(health_router, "runtime_mode", lambda: "eager_fallback")
    monkeypatch.setattr(
        health_router,
        "_check_celery",
        lambda: {"status": health_router._DEGRADED, "active_workers": 0},
    )
    monkeypatch.setattr(
        health_router,
        "get_cache_health",
        lambda: {"status": "offline", "backend": "in-memory"},
    )

    response = client.get("/health")

    assert response.status_code == 200
    body = response.json()
    assert body["status"] == health_router._DEGRADED
    assert body["mode"] == "eager_fallback"
    assert body["services"]["redis"]["status"] == health_router._DEGRADED
    assert body["services"]["celery"]["status"] == health_router._DEGRADED


def test_liveness_probe_never_checks_external_services(client):
    response = client.get("/health/live")

    assert response.status_code == 200
    assert response.json()["status"] == "healthy"
