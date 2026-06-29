import functools
import inspect
import logging
import time


logger = logging.getLogger("timing")


def measure_time(operation_name: str):
    def decorator(func):
        if inspect.iscoroutinefunction(func):

            @functools.wraps(func)
            async def async_wrapper(*args, **kwargs):
                start_time = time.perf_counter()

                result = await func(*args, **kwargs)

                duration = time.perf_counter() - start_time

                logger.info(
                    "[TIMER] %s finished in %.2f sec",
                    operation_name,
                    duration
                )

                return result

            return async_wrapper

        @functools.wraps(func)
        def sync_wrapper(*args, **kwargs):
            start_time = time.perf_counter()

            result = func(*args, **kwargs)

            duration = time.perf_counter() - start_time

            logger.info(
                "[TIMER] %s finished in %.2f sec",
                operation_name,
                duration
            )

            return result

        return sync_wrapper

    return decorator
