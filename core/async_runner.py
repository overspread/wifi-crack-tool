# -*- coding: utf-8 -*-
"""
Async runner utilities for WiFi Crack Tool

This module provides utilities for running synchronous blocking code
in an asynchronous context, particularly for pywifi operations.
"""
import asyncio
from functools import wraps
from typing import Callable, Any, TypeVar, Coroutine
from concurrent.futures import ThreadPoolExecutor

# Thread pool for running blocking operations
_executor = ThreadPoolExecutor(max_workers=4, thread_name_prefix="wifi_async_")

T = TypeVar('T')


async def run_in_thread(func: Callable[..., T], *args: Any, **kwargs: Any) -> T:
    """
    Run a blocking function in a thread pool
    
    This is used to wrap pywifi synchronous operations so they don't block
    the async event loop.
    
    :param func: Blocking function to run
    :param args: Positional arguments for the function
    :param kwargs: Keyword arguments for the function
    :return: Function result
    """
    loop = asyncio.get_event_loop()
    return await loop.run_in_executor(
        _executor,
        lambda: func(*args, **kwargs)
    )


def async_wrap(func: Callable[..., T]) -> Callable[..., Coroutine[Any, Any, T]]:
    """
    Decorator to wrap a synchronous function as async
    
    :param func: Synchronous function
    :return: Async wrapper function
    """
    @wraps(func)
    async def wrapper(*args: Any, **kwargs: Any) -> T:
        return await run_in_thread(func, *args, **kwargs)
    return wrapper


class CancellableTask:
    """
    Wrapper for managing cancellable async tasks
    """
    
    def __init__(self):
        self._task: asyncio.Task | None = None
        self._cancelled = False
    
    @property
    def is_running(self) -> bool:
        """Check if task is currently running"""
        return self._task is not None and not self._task.done()
    
    @property
    def is_cancelled(self) -> bool:
        """Check if task was cancelled"""
        return self._cancelled
    
    def start(self, coro: Coroutine) -> asyncio.Task:
        """
        Start an async task
        
        :param coro: Coroutine to run
        :return: The created task
        """
        self._cancelled = False
        self._task = asyncio.create_task(coro)
        return self._task
    
    def cancel(self) -> bool:
        """
        Cancel the running task
        
        :return: True if task was cancelled, False if no task running
        """
        if self._task is not None and not self._task.done():
            self._cancelled = True
            self._task.cancel()
            return True
        return False
    
    async def wait(self) -> Any:
        """
        Wait for the task to complete
        
        :return: Task result or None if cancelled/no task
        """
        if self._task is None:
            return None
        try:
            return await self._task
        except asyncio.CancelledError:
            return None


def shutdown_executor():
    """Shutdown the thread pool executor"""
    _executor.shutdown(wait=False)
