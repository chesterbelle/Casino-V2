"""
Centralized Error Handler for Casino V3.

Provides intelligent error handling with:
- Error classification (retriable vs fatal)
- Exponential backoff with jitter
- Circuit breaker integration
- Retry logic
- Error metrics

Author: Casino V3 Team
Version: 2.0.0
"""

import asyncio
import logging
import random
from dataclasses import dataclass
from typing import Any, Callable, Optional, TypeVar

from exchanges.resilience.error_classifier import ErrorAction, ErrorClassifier

from .circuit_breaker import CircuitBreaker, CircuitBreakerOpenError

T = TypeVar("T")


@dataclass
class RetryConfig:
    """Configuration for retry behavior."""

    max_retries: int = 3
    backoff_base: float = 1.0  # Base delay in seconds
    backoff_max: float = 60.0  # Max delay in seconds
    backoff_factor: float = 2.0  # Exponential factor
    jitter: bool = True  # Add randomness to backoff


class ErrorHandler:
    """
    Centralized error handler with intelligent retry logic.

    Example:
        handler = ErrorHandler()

        # With automatic retry
        result = await handler.execute(
            risky_function,
            arg1, arg2,
            retry_config=RetryConfig(max_retries=5)
        )

        # With circuit breaker
        result = await handler.execute_with_breaker(
            "api_calls",
            risky_function,
            arg1, arg2
        )
    """

    def __init__(self):
        self.logger = logging.getLogger("ErrorHandler")
        self.classifier = ErrorClassifier()
        self._circuit_breakers: dict[str, CircuitBreaker] = {}
        self._error_counts: dict[str, int] = {}

    def get_circuit_breaker(
        self,
        name: str,
        failure_threshold: int = 5,
        recovery_timeout: int = 60,
        half_open_max_calls: int = 3,
    ) -> CircuitBreaker:
        """
        Get or create a circuit breaker.

        Args:
            name: Unique name for the circuit breaker
            failure_threshold: Failures before opening
            recovery_timeout: Seconds before attempting recovery
            half_open_max_calls: Max calls in half-open state

        Returns:
            CircuitBreaker instance
        """
        if name not in self._circuit_breakers:
            self._circuit_breakers[name] = CircuitBreaker(
                failure_threshold=failure_threshold,
                recovery_timeout=recovery_timeout,
                half_open_max_calls=half_open_max_calls,
                name=name,
            )
        return self._circuit_breakers[name]

    async def execute(
        self,
        func: Callable[..., T],
        *args,
        retry_config: Optional[RetryConfig] = None,
        context: str = "unknown",
        **kwargs,
    ) -> T:
        """
        Execute function with automatic retry on retriable errors.

        Args:
            func: Async function to execute
            *args: Positional arguments for func
            retry_config: Retry configuration (uses defaults if None)
            context: Context for logging/metrics
            **kwargs: Keyword arguments for func

        Returns:
            Result from func

        Raises:
            Exception: If all retries exhausted or error is not retriable
        """
        config = retry_config or RetryConfig()
        last_exception = None

        for attempt in range(config.max_retries):
            try:
                result = await func(*args, **kwargs)

                # Reset error count on success
                if context in self._error_counts:
                    del self._error_counts[context]

                return result

            except Exception as e:
                last_exception = e

                # Track error
                self._error_counts[context] = self._error_counts.get(context, 0) + 1

                # Classify error
                classification = self.classifier.classify(e)

                # Log error
                self.logger.warning(
                    f"⚠️ Error in {context} (attempt {attempt + 1}/{config.max_retries}): "
                    f"{classification.category.value} | {str(e)[:100]}"
                )

                # Check if retriable
                if not classification.is_retriable:
                    self.logger.error(
                        f"❌ Non-retriable error in {context}: "
                        f"{classification.category.value} | {classification.message}"
                    )
                    raise

                # Check if max retries reached
                if attempt >= config.max_retries - 1:
                    self.logger.error(f"❌ Max retries ({config.max_retries}) exhausted for {context}")
                    raise

                # Calculate backoff delay
                delay = self._calculate_backoff(
                    attempt=attempt,
                    base=config.backoff_base,
                    factor=config.backoff_factor,
                    max_delay=config.backoff_max,
                    jitter=config.jitter,
                )

                # Use classifier's suggested delay if available
                if classification.retry_delay:
                    delay = min(delay, classification.retry_delay)

                self.logger.info(
                    f"🔄 Retrying {context} in {delay:.2f}s " f"(attempt {attempt + 2}/{config.max_retries})"
                )
                await asyncio.sleep(delay)

        # Should never reach here, but just in case
        raise last_exception

    async def execute_with_breaker(
        self,
        breaker_name: str,
        func: Callable[..., T],
        *args,
        retry_config: Optional[RetryConfig] = None,
        **kwargs,
    ) -> T:
        """
        Execute function with circuit breaker protection and retry logic.

        Args:
            breaker_name: Name of circuit breaker to use
            func: Async function to execute
            *args: Positional arguments for func
            retry_config: Retry configuration
            **kwargs: Keyword arguments for func

        Returns:
            Result from func

        Raises:
            CircuitBreakerOpenError: If circuit is open
            Exception: If all retries exhausted
        """
        breaker = self.get_circuit_breaker(breaker_name)

        # Wrap function execution with circuit breaker
        async def wrapped():
            async with breaker:
                return await func(*args, **kwargs)

        # Execute with retry logic
        return await self.execute(
            wrapped,
            retry_config=retry_config,
            context=f"{breaker_name}.{func.__name__}",
        )

    def _calculate_backoff(
        self,
        attempt: int,
        base: float,
        factor: float,
        max_delay: float,
        jitter: bool,
    ) -> float:
        """
        Calculate exponential backoff delay with optional jitter.

        Args:
            attempt: Current attempt number (0-indexed)
            base: Base delay in seconds
            factor: Exponential factor
            max_delay: Maximum delay
            jitter: Whether to add jitter

        Returns:
            Delay in seconds
        """
        # Exponential backoff: base * (factor ^ attempt)
        delay = base * (factor**attempt)

        # Cap at max_delay
        delay = min(delay, max_delay)

        # Add jitter (±25% randomness)
        if jitter:
            jitter_range = delay * 0.25
            delay += random.uniform(-jitter_range, jitter_range)
            delay = max(0.1, delay)  # Ensure positive

        return delay

    def get_error_stats(self) -> dict[str, Any]:
        """
        Get error statistics.

        Returns:
            Dictionary with error counts and circuit breaker states
        """
        return {
            "error_counts": dict(self._error_counts),
            "circuit_breakers": {name: breaker.get_stats() for name, breaker in self._circuit_breakers.items()},
            "classifier_metrics": self.classifier.get_metrics(),
        }

    def reset_circuit_breaker(self, name: str):
        """Manually reset a circuit breaker."""
        if name in self._circuit_breakers:
            self._circuit_breakers[name].reset()
            self.logger.info(f"🔄 Circuit breaker '{name}' manually reset")
        else:
            self.logger.warning(f"⚠️ Circuit breaker '{name}' not found")

    def reset_all_circuit_breakers(self):
        """Reset all circuit breakers."""
        for breaker in self._circuit_breakers.values():
            breaker.reset()
        self.logger.info("🔄 All circuit breakers reset")


# Global error handler instance
_global_error_handler: Optional[ErrorHandler] = None


def get_error_handler() -> ErrorHandler:
    """Get global error handler instance."""
    global _global_error_handler
    if _global_error_handler is None:
        _global_error_handler = ErrorHandler()
    return _global_error_handler
