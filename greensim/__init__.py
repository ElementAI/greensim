"""
Core tools for building simulations.
"""

from contextlib import contextmanager
from heapq import heappush, heappop
from math import inf
from typing import cast, Callable, Tuple, List, Iterable, Optional, Dict, Sequence, Mapping, MutableMapping, Any

import greenlet


class Simulator(object):
    """
    This class articulates the dynamic sequence of events that composes a discrete event system. While single events may
    be added into a simulation, using method `schedule()`, its use with *processes*, functions that respectively
    describe trains of events, yields an elegant DSL for modeling discrete event systems. Processes are incorporated
    into the simulation using method `add()`. This will make the process functions run on green threads (so-called
    *greenlets*), granting the simulator the possibility of running a large number of concurrent processes. Green thread
    cooperation is transparent to the simulation's writer: it naturally stems from switching between concurrent events
    as the simulation progresses. In addition, green threads do not imply the use of Python multi-threading on the
    simulator's behalf: simulations are run on a single Python thread, and thus data sharing between simulation
    processes involve no race condition (unless one is explicitly implemented).

    Each event within a simulation is associated to a moment on the simulator's clock. This timeline is completely
    abstract: a 1.0 unit on this clock corresponds to whatever unit of time is convenient to the model author (such
    correspondence, when relevant, is best documented for the benefit of the users of the model). When the simulation
    runs, events are executed as fast as a single CPU allows.

    Usage of this class is simple: one sets up events and processes that will generate events as they execute. Then one
    invokes the run() method. The events are executed in chronological order. Events can schedule new ad hoc events: the
    only rule is that events cannot be scheduled in the past. The simulation stops once all events have been executed,
    or one of the events invokes the stop() method of the Simulator instance; at this moment, method run() returns. It
    may be called again to resume the simulation, and so on as many times as makes sense to study the model.
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

    def events(self) -> Iterable[Tuple[float, Callable, Sequence, Mapping]]:
        """
        Iterates over scheduled events. Each event is a 4-tuple composed of the moment (on the simulated clock) the
        event should execute, the function corresponding to the event, its positional parameters (as a tuple of
        arbitrary length), and its keyword parameters (as a dictionary).
        """
        return ((moment, event, args, kwargs) for moment, _, event, args, kwargs in self._events)

    def schedule(self, delay: float, event: Callable, *args: Any, **kwargs: Any) -> 'Simulator':
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

        # Use counter to strictly order events happening at the same simulated time. This gives a total order on events,
        # working around the heap queue not yielding a stable ordering.
        heappush(self._events, (self._ts_now + delay, self._counter, event, args, kwargs))
        self._counter += 1
        return self

    def add(self, fn_process: Callable, *args, **kwargs) -> 'Simulator':
        """
        Adds a process to the simulation. The process is embodied by a function, which will be called with the given
        positional and keyword parameters when the simulation runs. As a process, this function runs on a special green
        thread, and thus will be able to call functions `now()`, `advance()`, `pause()` and `stop()` to articulate its
        events across the simulated timeline and control the simulation's flow.
        """
        process = Process(self, fn_process, self._gr)
        self.schedule(0.0, process.switch, *args, **kwargs)
        return process

    def run(self, duration: float = inf) -> None:
        """
        Runs the simulation until a stopping condition is met (no more events, or an event invokes method stop()), or
        until the simulated clock hits the given duration.
        """
        counter_stop_event = None
        if duration != inf:
            counter_stop_event = self._counter
            self.schedule(duration, self.stop)

        self._is_running = True
        while self.is_running() and len(self._events) > 0:
            self._ts_now, _, event, args, kwargs = heappop(self._events)
            event(*args, **kwargs)
        self.stop()

        if counter_stop_event is not None:
            # Change the planned stop to a no-op. We would rather eliminate it, but this would force a re-sort of the
            # event queue.
            for (i, (moment, counter, _, _, _)) in enumerate(self._events):
                if counter == counter_stop_event:
                    self._events[i] = (moment, counter, lambda: None, (), {})
                    break

    def stop(self) -> None:
        """
        Stops the running simulation once the current event is done executing.
        """
        self._is_running = False

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
    """
    Processes are green threads transparently used to mix the concurrent execution of multiple functions that generate
    trains of events. A simulation's writer typically does not have to care for processes: their management is
    transparent through the usage of Queues, Gates and Resources. However, if one uses methods pause() to implement a
    queueing or interruption mechanism of their own, they become responsible with resuming the stopped processes, by
    invoking their method `resume()`.

    Through their `local` public data member, processes may store arbitrary values that can be then manipulated by other
    processes (no risk of race condition). This is useful for implementing non-trivial queue disciplines, for instance.
    """

    def __init__(self, sim: Simulator, run: Callable, parent: greenlet.greenlet) -> None:
        super().__init__(run, parent)
        self.sim = sim
        self.local: MutableMapping[str, Any] = {}

    @staticmethod
    def current() -> 'Process':
        """
        Returns the instance of the process that is executing at the current moment.
        """
        curr = greenlet.getcurrent()
        if not isinstance(curr, Process):
            raise TypeError("Current greenlet does not correspond to a Process instance.")
        return cast(Process, greenlet.getcurrent())

    def resume(self) -> None:
        """
        Resumes a process that has been previously paused by invoking function `pause()`. This does not interrupt the
        current process or event: it merely schedules again the target process, so that its execution carries on at the
        return of the `pause()` function, when this new wake-up event fires.
        """
        self.sim.schedule(0.0, self.switch)


def pause() -> None:
    """
    Pauses the current process indefinitely -- it will require another process to `resume()` it. When this resumption
    happens, the process returns from this function.
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
    """
    Returns current simulated time to the running process.
    """
    return Process.current().sim.now()


def stop() -> None:
    """
    Stops the ongoing simulation, from a process.
    """
    Process.current().sim.stop()


class Queue(object):
    """
    Waiting queue for processes, with arbitrary queueing discipline.  Processes `join()` the queue, which pauses them.
    It is assumed that other events of the process result in invoking the queue's `pop()` method, which takes the top
    process out of the queue and resumes it.

    The queue discipline is implemented through a function that yields an order token for each process: the lower the
    token, the closer the process to the top of the queue. Each process joining the queue is given an monotonic counter
    value, which indicates chronological order -- this counter is passed to the function that computes order tokens for
    the queue. By default, the queue discipline is chronological order (the function trivially returns the counter value
    as order token). Alternative disciplines, such as priority order and so on, may be implemented by mixing the
    chronological counter passed to this function with data obtained or computed from the running process. The order
    token of a joining process is computed only once, before the process is paused.
    """

    GetOrderToken = Callable[[int], int]

    def __init__(self, get_order_token: Optional[GetOrderToken] = None) -> None:
        super().__init__()
        self._waiting: List[Tuple[int, Process]] = []
        self._counter = 0
        self._get_order_token = get_order_token or (lambda counter: counter)

    def is_empty(self) -> bool:
        """
        Returns whether the queue is empty.
        """
        return len(self._waiting) == 0

    def peek(self) -> Process:
        """
        Returns the process instance at the top of the queue. This is useful mostly for querying purposes: the
        `resume()` method of the returned process should *not* be called by the caller, as `peek()` does not remove the
        process from the queue.
        """
        return self._waiting[0][1]

    def join(self):
        """
        Can be invoked only by a process: makes it join the queue. The order token is computed once for the process,
        before it is enqueued. Another process or event, or control code of some sort, must invoke method `pop()` of the
        queue so that the process can eventually leave the queue and carry on with its execution.
        """
        self._counter += 1
        heappush(self._waiting, (self._get_order_token(self._counter), Process.current()))
        pause()

    def pop(self):
        """
        Removes the top process from the queue, and resumes its execution. For an empty queue, this method is a no-op.
        This method may be invoked from anywhere (its use is not confined to processes, as method `join()` is).
        """
        if not self.is_empty():
            _, process = heappop(self._waiting)
            process.resume()


class Gate(object):
    """
    `Gate` instances model a kind of *process transistor*. Processes can `cross()` a gate. When they do so, if it is
    *open*, then they cross instantly. Alternatively, if it is *closed*, the process is made to join a queue. It is
    popped out of the queue and resumed when the gate is opened at once.
    """

    def __init__(self, get_order_token: Optional[Queue.GetOrderToken] = None) -> None:
        super().__init__()
        self._is_open = True
        self._queue = Queue(get_order_token)

    @property
    def is_open(self) -> bool:
        """
        Tells whether the gate is open.
        """
        return self._is_open

    def open(self) -> "Gate":
        """
        Opens the gate. If processes are waiting, they are all resumed. This may be invoked from any code.

        Remark that while processes are simultaneously resumed in simulated time, they are effectively resumed in the
        sequence corresponding to the queue discipline. Therefore, if one of the resumed processes `close()`s back the
        gate, remaining resumed processes join back the queue. If the queue discipline is not monotonic (for instance,
        it bears a random component), then this open-close toggling of the gate may reorder the processes.
        """
        self._is_open = True
        while not self._queue.is_empty():
            self._queue.pop()
        return self

    def close(self) -> "Gate":
        """
        Closes the gate. This may be invoked from any code.
        """
        self._is_open = False
        return self

    def cross(self) -> None:
        """
        Gets the current process across the gate. If it is closed, it will join the gate's queue.
        """
        while not self.is_open:
            self._queue.join()


class Resource(object):
    """
    Resource instances model limited commodities that processes need exclusive access to, and the waiting queue to gain
    access. A resource is built with a number of available *instances*, and any process can `take()` a certain number of
    these instances; it must then `release()` these instances afterwards. If the requested number of available instances
    is available, `take()` returns instantly. Otherwise, the process is made to join a queue. When another process
    releases the instances it has previously taken, if the number of available instances becomes sufficient to satisfy
    the request of the process at the top of the queue, this top process is popped off and resumed.

    Remark that concurrent processes can deadlock if they do not `take()` resource instances properly. Consider a set of
    resources `{R1, R2 ... Rn}` that processes from set `{P1, P2, ... Pm}` want to take. Irrespective of process order,
    the processes will *not* enter a deadlock state if they `take()` of each resource in the same order, and if all
    instances they need from each resource respectively is reserved atomically, i.e. in a single call to `take()`.
    """

    def __init__(self, num_instances: int = 1, get_order_token: Optional[Queue.GetOrderToken] = None) -> None:
        super().__init__()
        self._num_instances_free = num_instances
        self._waiting = Queue(get_order_token)
        self._usage: Dict[Process, int] = {}

    @property
    def num_instances_free(self):
        """Returns the number of free instances."""
        return self._num_instances_free

    @property
    def num_instances_total(self):
        """Returns the total number of instances of this resource."""
        return self.num_instances_free + sum(self._usage.values())

    def take(self, num_instances: int = 1):
        """
        The current process reserves a certain number of instances. If there are not enough instances available, the
        process is made to join a queue. When this method returns, the process holds the instances it has requested to
        take.
        """
        if num_instances < 1:
            raise ValueError(f"Process must request at least 1 instance; here requested {num_instances}.")
        if num_instances > self.num_instances_total:
            raise ValueError(
                f"Process must request at most {self.num_instances_total} instances; here requested {num_instances}."
            )
        proc = Process.current()
        if self._num_instances_free < num_instances:
            proc.local["num_instances"] = num_instances
            self._waiting.join()
            del proc.local["num_instances"]
        self._num_instances_free -= num_instances
        self._usage.setdefault(proc, 0)
        self._usage[proc] += num_instances

    def release(self, num_instances: int = 1):
        """
        The current process releases instances it has previously taken. It may thus release less than it has taken.
        These released instances become free. If the total number of free instances then satisfy the request of the top
        process of the waiting queue, it is popped off the queue and resumed.
        """
        proc = Process.current()
        if self._usage.get(proc, 0) > 0:
            if num_instances > self._usage[proc]:
                raise ValueError(
                    f"Process holds {self._usage[proc]} instances, but requests too release more ({num_instances})"
                )
            self._usage[proc] -= num_instances
            if self._usage[proc] <= 0:
                del self._usage[proc]
            self._num_instances_free += num_instances
            if not self._waiting.is_empty():
                num_instances_next = cast(int, self._waiting.peek().local["num_instances"])
                if num_instances_next <= self.num_instances_free:
                    self._waiting.pop()

    @contextmanager
    def using(self, num_instances: int = 1):
        """
        Context manager around resource reservation: when the code block under the with statement is entered, the
        current process holds the instances it requested. When it exits, all these instances are released.

        Do not explicitly `release()` instances within the context block, at the risk of breaking instance management.
        If one needs to `release()` instances piecemeal, it should instead reserve the instances using `take()`.
        """
        self.take(num_instances)
        yield self
        self.release(num_instances)
