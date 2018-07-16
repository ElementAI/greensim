"""
Core tools for building simulations.
"""

from abc import ABC, abstractmethod
from contextlib import contextmanager
from heapq import heappush, heappop
from typing import Callable, Tuple, List, Iterable, Any, Optional, Dict, cast

import greenlet


class Simulator(object):
    """
    This class articulates the dynamic sequence of events that composes a
    discrete event system. While it may be used by itself, using method
    schedule(), its use in conjunction with subclasses of abstract class
    Process yields an elegant DSL for modeling discrete event systems.

    Each event within a simulation is associated to a moment on the
    simulator's clock. This timeline is completely abstract: a 1.0 unit on
    this clock corresponds to whatever unit of time is convenient to the
    model author (such correspondence, when relevant, is best documented for
    the benefit of the users of the model). When the simulation runs, events
    are executed as fast as a single CPU allows.

    Usage of this class is simple: one sets up a few events, or a process that
    will generate events as it executes. Then one invokes the start()
    method. The events are executed (each event corresponds to a function)
    in chronological order. Events can schedule new ad hoc events: the only
    rule is that events cannot be scheduled in the past. The simulation stops
    once all events have been executed, or one of the events invokes the
    stop() method of the Simulator instance; at this moment, method start()
    returns. It may be called again to resume the simulation, and so on
    as many times as makes sense to study the model.
    """

    def __init__(self, ts_now: float = 0.0) -> None:
        """
        Constructor. Parameter ts_now can be set to the initial value of the simulator's clock; it defaults at 0.0.
        """
        self._ts_now = ts_now
        self._events: List[Tuple[float, int, Callable, Tuple, Dict]] = []
        self._is_running = False
        self._counter = 0
        self._gr = greenlet.getcurrent()  # The Simulator's greenlet

    def now(self) -> float:
        """
        Returns the current value of the simulator's clock.
        """
        return self._ts_now

    def events(self) -> Iterable[Tuple[float, Callable]]:
        """
        Iterates over scheduled events.
        """
        return ((moment, event, args, kwargs) for moment, _, event, args, kwargs in self._events)

    def schedule(self, delay: float, event: Callable, *args, **kwargs) -> 'Simulator':
        """
        Schedules a one-time event to be run along the simulation.  The event is scheduled relative to current simulator
        time, so delay is expected to be a positive simulation time interval. The `event' parameter corresponds to a
        callable object (e.g. a function): it will be called so as to "execute" the event, with the positional and
        keyword parameters that follow `event` in the call to `schedule` (note that the value of these arguments are
        evaluated when `schedule()` is called, not when the event is executed). Once this event function returns, the
        simulation carries on to the next event, or stops if none remain.
        """
        delay = float(delay)
        if delay < 0.0:
            raise ValueError("Delay must be positive.")

        # Use counter to strictly order events happening at the same
        # simulated time. This gives a total order on events, working around
        # the heap queue not yielding a stable ordering.
        heappush(self._events, (self._ts_now + delay, self._counter, event, args, kwargs))
        self._counter += 1
        return self

    def add(self, fn_process: Callable, *args, **kwargs) -> 'Simulator':
        """
        Adds a process to the simulation. The process is embodied by a function, which will be called with the given
        positional and keyword parameters when the simulation runs. As a process, this function will be able to call
        functions `now()`, `advance()`, `pause()` and `stop()` to articulate its events across the simulated timeline
        and control the simulation's flow.
        """
        process = Process(self, fn_process, self._gr)
        self.schedule(0.0, process.switch, *args, **kwargs)
        return process

    def run(self) -> None:
        """
        Runs the simulation until a stopping condition is met (no more events, or an event invokes method stop()).
        """
        self._is_running = True
        while self.is_running() and len(self._events) > 0:
            self._ts_now, _, event, args, kwargs = heappop(self._events)
            event(*args, **kwargs)
        self.stop()

    def stop(self) -> None:
        """
        Stops the running simulation once the current event is done executing.
        """
        self._is_running = False

    def stop_at(self, delay: float) -> 'Simulator':
        """
        Schedules stopping the simulator after the given delay.
        """
        self.schedule(delay, self.stop)

    def is_running(self) -> bool:
        """
        Tells whether the simulation is currently running.
        """
        return self._is_running

    def _switch(self) -> None:
        """
        Gives control back to the simulator. Meant to be called from a process greenlet.
        """
        self._gr.switch()


class Process(greenlet.greenlet):

    def __init__(self, sim: Simulator, run: Callable, parent: greenlet.greenlet):
        super().__init__(run, parent)
        self.sim = sim
        self.local = {}

    @staticmethod
    def current() -> 'Process':
        curr = greenlet.getcurrent()
        if not isinstance(curr, Process):
            raise TypeError("Current greenlet does not correspond to a Process instance.")
        return cast(Process, greenlet.getcurrent())

    def resume(self) -> None:
        self.sim.schedule(0.0, self.switch)


def pause() -> None:
    """
    Pauses the current process indefinitely -- it will require another process to `resume()` it.
    """
    Process.current().sim._switch()


def advance(delay: float) -> None:
    """
    Pauses the current process for the given delay (in simulated time). The process will be resumed when the simulation
    has advanced to the moment corresponding to `now() + delay`.
    """
    curr = Process.current()
    curr.sim.schedule(delay, curr.switch)
    curr.sim._switch()


def now() -> float:
    return Process.current().sim.now()


def stop() -> None:
    Process.current().sim.stop()


class Queue(object):

    GetOrderToken = Callable[[int], int]

    def __init__(self, get_order_token: Optional[GetOrderToken] = None) -> None:
        super().__init__()
        self._waiting: List[Tuple[int, Process]] = []
        self._counter = 0
        self._get_order_token = get_order_token or (lambda counter: counter)

    def is_empty(self):
        return len(self._waiting) == 0

    def peek(self) -> Process:
        return self._waiting[0][1:]

    def join(self):
        self._counter += 1
        heappush(self._waiting, (self._get_order_token(self._counter), Process.current()))
        pause()

    def pop(self):
        if not self.is_empty():
            _, process = heappop(self._waiting)
            process.resume()


class Gate(object):

    def __init__(self, get_order_token: Optional[Queue.GetOrderToken] = None) -> None:
        super().__init__()
        self._is_open = True
        self._queue = Queue(get_order_token)

    @property
    def is_open(self) -> bool:
        return self._is_open

    def open(self) -> "Gate":
        self._is_open = True
        while not self._queue.is_empty():
            self._queue.pop()
        return self

    def close(self) -> "Gate":
        self._is_open = False
        return self

    def cross(self) -> None:
        while not self.is_open:
            self._queue.join()


# class Resource(object):

#     def __init__(
#         self,
#         sim: Simulator,
#         num_instances: int = 1,
#         get_order_token: Optional[Queue.GetOrderToken] = None
#     ) -> None:
#         super().__init__()
#         self.sim = sim
#         self._num_instances_free = num_instances
#         self._waiting = Queue(sim, get_order_token)
#         self._usage: Dict[Process, int] = {}

#     @property
#     def num_instances_free(self):
#         return self._num_instances_free

#     @property
#     def num_instances_total(self):
#         return self.num_instances_free + sum(self._usage.values())

#     def take(self, proc: Process, num_instances: int = 1):
#         if num_instances < 1:
#             raise ValueError(f"Process must request at least 1 instance; here requested {num_instances}.")
#         if num_instances > self.num_instances_total:
#             raise ValueError(
#                 f"Process must request at most {self.num_instances_total} instances; here requested {num_instances}."
#             )
#         if self._num_instances_free < num_instances:
#             self._waiting.join(proc, tag=num_instances)
#         self._num_instances_free -= num_instances
#         self._usage.setdefault(proc, 0)
#         self._usage[proc] += num_instances

#     def release(self, proc: Process, num_instances: int = 1):
#         if self._usage.get(proc, 0) > 0:
#             if num_instances > self._usage[proc]:
#                 raise ValueError(
#                     f"Process holds {self._usage[proc]} instances, but requests too release more ({num_instances})"
#                 )
#             self._usage[proc] -= num_instances
#             if self._usage[proc] <= 0:
#                 del self._usage[proc]
#             self._num_instances_free += num_instances
#             if not self._waiting.is_empty():
#                 num_instances_next = cast(int, self._waiting.peek()[1])
#                 if num_instances_next <= self.num_instances_free:
#                     self._waiting.pop()

#     @contextmanager
#     def using(self, proc: Process, num_instances: int = 1):
#         self.take(proc, num_instances)
#         yield self
#         self.release(proc, num_instances)
