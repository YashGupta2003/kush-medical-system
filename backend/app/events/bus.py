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

    def publish(self, event: DomainEvent) -> None:
        """
        Publish an event to all registered subscribers.
        Executes registered subscriber functions cleanly.
        """
        event_type = type(event)
        handlers = self._subscribers.get(event_type, [])
        logger.info(f"[EVENT DISPATCH] Publishing '{event_type.__name__}' to {len(handlers)} subscriber(s)")

        for handler in handlers:
            try:
                logger.debug(f"Running subscriber '{handler.__name__}' for '{event_type.__name__}'")
                handler(event)
            except Exception as e:
                logger.error(
                    f"Error executing subscriber '{handler.__name__}' on event '{event_type.__name__}': {e}",
                    exc_info=True
                )
                # Note: Subscriber exceptions are logged; caller transaction integrity is managed cleanly.


# Global EventBus Singleton
event_bus = EventBus()
