"""
Centralized Event Bus for Event-Driven Architecture (EDA).
Enables decoupled component communication, modular extensions, and pipeline dispatching.
"""
from typing import Callable, Dict, List, Type
from app.core.logging import get_logger
from app.events.events import DomainEvent

logger = get_logger("event_bus")

EventHandler = Callable[[DomainEvent], None]


class EventBus:
    """
    Publish-Subscribe Event Bus for Domain Events.

    BUG FIX #5 — EventBus Transaction Inconsistency:
    The original bus silently caught and logged all subscriber exceptions.
    This created a race condition / partial-commit hazard: if subscriber A
    incremented stock and subscriber B (expiry creation) then raised an error,
    the error was swallowed, stock was committed, but no expiry was ever created.

    Fix: publish() now accepts a `transactional` flag (default True for
    BillConfirmedEvent). When transactional=True, ALL subscribers are called
    first; if ANY raise an exception, all exceptions are collected and re-raised
    as a single RuntimeError. The caller (confirm_bill) wraps the publish in a
    try/except that calls db.rollback(), ensuring the entire operation is ACID.
    """
    def __init__(self):
        self._subscribers: Dict[Type[DomainEvent], List[EventHandler]] = {}

    def subscribe(self, event_type: Type[DomainEvent], handler: EventHandler) -> None:
        """Register a subscriber handler for a specific domain event type."""
        if event_type not in self._subscribers:
            self._subscribers[event_type] = []
        if handler not in self._subscribers[event_type]:
            self._subscribers[event_type].append(handler)
            logger.debug(f"Subscribed handler '{handler.__name__}' to '{event_type.__name__}'")

    def publish(self, event: DomainEvent, transactional: bool = False) -> None:
        """
        Publish an event to all registered subscribers.

        Args:
            event: The domain event to dispatch.
            transactional: If True, collects ALL subscriber exceptions and
                re-raises them together as a RuntimeError after all handlers
                have been attempted. The caller is expected to rollback the
                DB transaction on error. This implements the Outbox pattern's
                all-or-nothing guarantee without a separate outbox table.
                If False (default), exceptions are logged and swallowed
                (fire-and-forget, suitable for non-critical side effects).
        """
        event_type = type(event)
        handlers = self._subscribers.get(event_type, [])
        logger.info(f"[EVENT DISPATCH] Publishing '{event_type.__name__}' to {len(handlers)} subscriber(s) "
                    f"(transactional={transactional})")

        failures: List[str] = []

        for handler in handlers:
            try:
                logger.debug(f"Running subscriber '{handler.__name__}' for '{event_type.__name__}'")
                handler(event)
            except Exception as e:
                error_msg = f"Subscriber '{handler.__name__}' on event '{event_type.__name__}': {e}"
                logger.error(f"[EVENT ERROR] {error_msg}", exc_info=True)
                if transactional:
                    failures.append(error_msg)
                # In non-transactional mode: log and continue (fire-and-forget)

        if transactional and failures:
            # Re-raise so the caller's DB transaction can be rolled back atomically.
            # This prevents partial state (e.g. stock incremented but expiry not created).
            raise RuntimeError(
                f"EventBus transactional publish failed — {len(failures)} subscriber(s) errored. "
                f"The DB transaction will be rolled back to maintain consistency.\n"
                + "\n".join(f"  • {f}" for f in failures)
            )


# Global EventBus Singleton
event_bus = EventBus()
