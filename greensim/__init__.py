"""
Core tools for building simulations.
"""

from contextlib import contextmanager
from heapq import heappush, heappop
from logging import getLogger, DEBUG, INFO, WARNING
from math import inf
from types import TracebackType
from typing import cast, Callable, Tuple, List, Iterable, Optional, Dict, Sequence, Mapping, Any, Type
from uuid import uuid4
import weakref

import greenlet

from greensim.tags import Tags, TaggedObject

GREENSIM_TAG_ATTRIBUTE = "_greensim_tags"

# Disable auto-logging by default: it bears a significant weight on performance. Auto-logging will be toggled using
# enable_logging() and disable_logging().
_logger = None


def enable_logging():
    global _logger
    _logger = getLogger(__name__)


def disable_logging():
    global _logger
    _logger = None


def _log(level: int, obj: str, name: str, event: str, **params: Any) -> None:
    try:
        ts_now = now()
        name_process = local.name
    except TypeError:
        ts_now = params.get("__now", -1.0)
        name_process = ""

    if "__now" in params:
        del params["__now"]

    (_logger or getLogger(__name__)).log(
        level,
        "",
        extra=dict(
            sim_time=ts_now,
            sim_process=name_process,
            sim_name=name,
            sim_object=obj,
            sim_event=event,
            sim_params=params
        )
    )


class Named(object):

    def __init__(self, name: Optional[str]) -> None:
        super().__init__()
        self._name = name or str(uuid4())

    @property
    def name(self) -> str:
        return self._name

    def _log(self, level: int, event: str, **params: Any) -> None:
        _log(level, type(self).__name__, self.name, event, **params)


class Interrupt(Exception):
    """
    Raised on a :py:class:`Process` instance through the :py:meth:`Process.interrupt` method, so it resumes its
    execution without having advanced in time as much as it expected, or having fulfilled the condition is hoped to
    satisfy by going into pause.
    """
    pass


class _Event(object):
    """
    Event on a simulation timeline.
    """

    def __init__(self, timestamp: float, identifier: int, event: Callable, *args: Any, **kwargs: Any) -> None:
        super().__init__()
        self._timestamp = timestamp
        self._identifier = identifier
        self._is_cancelled = False
        self._event = event
        self._args = args
        self._kwargs = kwargs

    def __eq__(self, other: object) -> bool:
        return isinstance(other, _Event) and \
            self._timestamp == other._timestamp and \
            self._identifier == other._identifier and \
            self.fn == other.fn and \
            self.args == other.args and \
            self.kwargs == other.kwargs

    def __lt__(self, other: object) -> bool:
        if not isinstance(other, _Event):
            return False
        return (self._timestamp, self._identifier) < (other._timestamp, other._identifier)

    @property
    def timestamp(self) -> float:
        return self._timestamp

    @property
    def identifier(self) -> int:
        return self._identifier

    @property
    def is_cancelled(self) -> bool:
        return self._is_cancelled

    @property
    def fn(self) -> Callable:
        return self._event

    @property
    def args(self) -> Sequence[Any]:
        return self._args

    @property
    def kwargs(self) -> Mapping[str, Any]:
        return self._kwargs

    def cancel(self) -> None:
        """
        Cancels this event, so that its execution will no-op.
        """
        self._is_cancelled = True

    def execute(self, sim: "Simulator") -> None:
        """
        Executes the event, unless it was cancelled.
        """
        if self._is_cancelled:
            if _logger is not None:
                _log(DEBUG, "Simulator", sim.name, "discard-event", counter=self._identifier, __now=self._timestamp)
        else:
            if _logger is not None:
                _log(DEBUG, "Simulator", sim.name, "exec-event", counter=self._identifier, __now=self._timestamp)
            self.fn(*self.args, **self.kwargs)


class Simulator(Named):
    """
    This class articulates the dynamic sequence of events that composes a discrete event system.  Its use to synchronize
    and articulate the execution of *processes*, functions that respectively describe trains of events, yields an
    elegant DSL for modeling discrete event systems. Processes are incorporated into the simulation using method
    `add()`. This will make the process functions run on green threads (so-called *greenlets*), granting the simulator
    the possibility of running a large number of concurrent processes. Green thread cooperation is transparent to the
    simulation's writer: it naturally stems from switching between concurrent events as the simulation progresses. In
    addition, green threads do not imply the use of Python multi-threading on the simulator's behalf: simulations are
    run on a single Python thread, and thus data sharing between simulation processes involve no race condition (unless
    one is explicitly implemented).

    Each event within a simulation is associated to a moment on the simulator's clock. This timeline is completely
    abstract: a 1.0 unit on this clock corresponds to whatever unit of time is convenient to the model author (such
    correspondence, when relevant, is best documented for the benefit of the users of the model). When the simulation
    runs, events are executed as fast as a single CPU allows.

    Usage of this class is simple: one sets up processes that will generate events as they execute. Then one
    invokes the run() method. The events are executed in chronological order. Processes can add yet other processes: the
    only rule is that events cannot be scheduled in the past. The simulation stops once all events have been executed,
    or one of the events invokes the stop() method of the Simulator instance; at this moment, method run() returns. It
    may be called again to resume the simulation, and so on as many times as makes sense to study the model.

    When running multiple simulations from a single process, one may become concerned that hanging processes come to
    use memory unduly. Processes hold a weak reference to the simulator they run in context of, so once all explicit
    references to the simulator are discarded, it is garbage-collected; its destructor then tears down all hanging
    processes, thereby freeing all simulation resources. However, to deliberately track and free simulation resources,
    one may use the simulator instance as a context manager, as in this example:

    with Simulator() as sim:
        sim.add(...)
        # ...
        sim.run(...)
        # ...

    Simulation resources and hanging processes are explicitly torn down on context exit.
    """

    def __init__(self, ts_now: float = 0.0, name: Optional[str] = None) -> None:
        """
        Constructor. Parameter ts_now can be set to the initial value of the simulator's clock; it defaults at 0.0.
        """
        super().__init__(name)
        self._ts_now = ts_now
        self._events: List[_Event] = []
        self._is_running = False
        self._counter = 0
        self._gr = greenlet.getcurrent()  # The Simulator's greenlet

    def now(self) -> float:
        """
        Returns the current value of the simulator's clock.
        """
        return self._ts_now

    def events(self) -> Iterable[Tuple[float, bool, Callable, Sequence[Any], Mapping[str, Any]]]:
        """
        Iterates over scheduled events. Each event is a 4-tuple composed of the moment (on the simulated clock) the
        event should execute, the function corresponding to the event, its positional parameters (as a tuple of
        arbitrary length), and its keyword parameters (as a dictionary).
        """
        return ((event.timestamp, event.is_cancelled, event.fn, event.args, event.kwargs) for event in self._events)

    def _schedule(self, delay: float, event: Callable, *args: Any, **kwargs: Any) -> int:
        """
        Schedules a one-time event to be run along the simulation.  The event is scheduled relative to current simulator
        time, so delay is expected to be a positive simulation time interval. The `event' parameter corresponds to a
        callable object (e.g. a function): it will be called so as to "execute" the event, with the positional and
        keyword parameters that follow `event` in the call to `_schedule()` (note that the value of these arguments are
        evaluated when `_schedule()` is called, not when the event is executed). Once this event function returns, the
        simulation carries on to the next event, or stops if none remain.

        Remark that this method is private, and is meant for internal usage by the :py:class:`Simulator` and
        :py:class:`Process` classes, and helper functions of this module.

        :return: Unique identifier for the scheduled event.
        """
        if _logger is not None:
            self._log(
                DEBUG,
                "schedule",
                delay=delay,
                fn=event,
                args=args,
                kwargs=kwargs,
                counter=self._counter,
                __now=self.now()
            )
        delay = float(delay)
        if delay < 0.0:
            raise ValueError("Delay must be positive.")

        # Use counter to strictly order events happening at the same simulated time. This gives a total order on events,
        # working around the heap queue not yielding a stable ordering.
        id_event = self._counter
        heappush(self._events, _Event(self._ts_now + delay, id_event, event, *args, **kwargs))
        self._counter += 1
        return id_event

    def _cancel(self, id_cancel) -> None:
        """
        Cancels a previously scheduled event. This method is private, and is meant for internal usage by the
        :py:class:`Simulator` and :py:class:`Process` classes, and helper functions of this module.
        """
        for event in self._events:
            if event.identifier == id_cancel:
                event.cancel()
                break

    def add(self, fn_process: Callable, *args: Any, **kwargs: Any) -> 'Process':
        """
        Adds a process to the simulation. The process is embodied by a function, which will be called with the given
        positional and keyword parameters when the simulation runs. As a process, this function runs on a special green
        thread, and thus will be able to call functions `now()`, `advance()`, `pause()` and `stop()` to articulate its
        events across the simulated timeline and control the simulation's flow.
        """
        return self.add_in(0.0, fn_process, *args, **kwargs)

    def add_in(self, delay: float, fn_process: Callable, *args: Any, **kwargs: Any) -> 'Process':
        """
        Adds a process to the simulation, which is made to start after the given delay in simulated time.

        See method add() for more details.
        """
        process = Process(self, fn_process, self._gr)
        if _logger is not None:
            self._log(INFO, "add", __now=self.now(), fn=fn_process, args=args, kwargs=kwargs)
        self._schedule(delay, process.switch, *args, **kwargs)
        return process

    def add_at(self, moment: float, fn_process: Callable, *args: Any, **kwargs: Any) -> 'Process':
        """
        Adds a process to the simulation, which is made to start at the given exact time on the simulated clock. Note
        that times in the past when compared to the current moment on the simulated clock are forbidden.

        See method add() for more details.
        """
        delay = moment - self.now()
        if delay < 0.0:
            raise ValueError(
                f"The given moment to start the process ({moment:f}) is in the past (now is {self.now():f})."
            )
        return self.add_in(delay, fn_process, *args, **kwargs)

    def run(self, duration: float = inf) -> None:
        """
        Runs the simulation until a stopping condition is met (no more events, or an event invokes method stop()), or
        until the simulated clock hits the given duration.
        """
        if _logger is not None:
            self._log(INFO, "run", __now=self.now(), duration=duration)
        counter_stop_event = None
        if duration != inf:
            counter_stop_event = self._counter
            self._schedule(duration, self.stop)

        self._is_running = True
        while self.is_running and len(self._events) > 0:
            event = heappop(self._events)
            self._ts_now = event.timestamp
            event.execute(self)

        if len(self._events) == 0:
            if _logger is not None:
                self._log(DEBUG, "out-of-events", __now=self.now())
        self.stop()

        if counter_stop_event is not None:
            # Change the planned stop to a no-op. We would rather eliminate it, but this would force a re-sort of the
            # event queue.
            for (i, event) in enumerate(self._events):
                if event.identifier == counter_stop_event:
                    if _logger is not None:
                        self._log(DEBUG, "cancel-stop", counter=counter_stop_event)
                    event.cancel()
                    break

    def step(self) -> None:
        """
        Runs a single event of the simulation.
        """
        event = heappop(self._events)
        self._ts_now = event.timestamp
        event.execute(self)

    def stop(self) -> None:
        """
        Stops the running simulation once the current event is done executing.
        """
        if self.is_running:
            if _logger is not None:
                self._log(INFO, "stop", __now=self.now())
            self._is_running = False

    @property
    def is_running(self) -> bool:
        """
        Tells whether the simulation is currently running.
        """
        return self._is_running

    def _clear(self) -> None:
        """
        Resets the internal state of the simulator, and sets the simulated clock back to 0.0. This discards all
        outstanding events and tears down hanging process instances.
        """
        for _, _, event, _, _ in self.events():
            if hasattr(event, "__self__") and isinstance(event.__self__, Process):  # type: ignore
                event.__self__.throw()                                              # type: ignore
        self._events.clear()
        self._ts_now = 0.0

    def __enter__(self) -> "Simulator":
        return self

    def __exit__(
        self,
        exc_type: Optional[Type],
        exc_value: Optional[Exception],
        traceback: Optional[TracebackType]
    ) -> bool:
        self._clear()
        return False

    def __del__(self) -> None:
        """
        Destructor: kill all outstanding processes so that everything gets properly deleted.
        """
        self._clear()


class _TreeLocalParam(object):
    """
    Growing object for which arbitrary attributes can be set and gotten back.
    """

    def __getattr__(self, name: str) -> Any:
        return self._get().__dict__.setdefault(name, _TreeLocalParam())

    def __setattr__(self, name: str, value: Any) -> None:
        self._get().__dict__[name] = value

    def __delattr__(self, name: str) -> None:
        del self._get().__dict__[name]

    def _get(self) -> "_TreeLocalParam":
        return self


class _TreeLocalParamCurrent(_TreeLocalParam):

    def _get(self) -> "_TreeLocalParam":
        return Process.current().local

    def __setattr__(self, name: str, value: Any) -> Any:
        if _logger is not None and name == "name":
            _log(DEBUG, "Process", self.name, "rename", new=value)
        super().__setattr__(name, value)


local = _TreeLocalParamCurrent()


class Process(greenlet.greenlet, TaggedObject):
    """
    Processes are green threads transparently used to mix the concurrent execution of multiple functions that generate
    trains of events. A simulation's writer typically does not have to care for processes: their management is
    transparent through the usage of Queues, Signals and Resources. However, if one uses methods pause() to implement a
    queueing or interruption mechanism of their own, they become responsible with resuming the stopped processes, by
    invoking their method `resume()`.

    Through their `local` public data member, processes may store arbitrary values that can be then manipulated by other
    processes (no risk of race condition). This is useful for implementing non-trivial queue disciplines, for instance.
    """

    def __init__(self, sim: Simulator, run: Callable, parent: greenlet.greenlet) -> None:
        global GREENSIM_TAG_ATTRIBUTE
        # Ignore type since Python correctly calls greenlet.greenlet.__init__(),
        # but the type checker compares to TaggedObject.__init__()
        super().__init__(run, parent)  # type: ignore
        self.rsim = weakref.ref(sim)
        self.local = _TreeLocalParam()
        self.local.name = str(uuid4())

        # Collect tags from the process spawning this one, and anything attached to the function
        if Process.current_exists():
            self.tag_with(*Process.current()._tag_set)
        # Due to the way Greenlets are reused in memory, tags can persist across simulations
        # This makes sure that the Process is fresh if a simulation is not current running
        # Moving this outside the else statement will cause it to wipe tags from the currently
        # running process, if one exists. This will require further research
        else:
            self.clear_tags()

        if hasattr(run, GREENSIM_TAG_ATTRIBUTE):
            self.tag_with(*getattr(run, GREENSIM_TAG_ATTRIBUTE))

    @staticmethod
    def current() -> 'Process':
        """
        Returns the instance of the process that is executing at the current moment.
        """
        curr = greenlet.getcurrent()
        if not isinstance(curr, Process):
            raise TypeError("Current greenlet does not correspond to a Process instance.")
        return cast(Process, greenlet.getcurrent())

    @staticmethod
    def current_exists() -> bool:
        """
        Convenience method to allow conditional logic without try-except
        """
        return isinstance(greenlet.getcurrent(), Process)

    def resume(self) -> None:
        """
        Resumes a process that has been previously paused by invoking function `pause()`. This does not interrupt the
        current process or event: it merely schedules again the target process, so that its execution carries on at the
        return of the `pause()` function, when this new wake-up event fires.
        """
        if _logger is not None:
            _log(INFO, "Process", self.local.name, "resume")
        self.rsim()._schedule(0.0, self.switch)  # type: ignore

    def interrupt(self) -> None:
        """
        Interrupts a process that has been previously :py:meth:`pause`d or made to :py:meth:`advance`, by resuming it
        immediately and raising an :py:class:`Interrupt` exception on it. This exception can be captured by the
        interrupted process and leveraged for various purposes, such as timing out on a wait or generating activity
        prompting immediate reaction.
        """
        if _logger is not None:
            _log(INFO, "Process", self.local.name, "interrupt")
        self.rsim()._schedule(0.0, self.throw, Interrupt())  # type: ignore


def pause() -> None:
    """
    Pauses the current process indefinitely -- it will require another process to `resume()` it. When this resumption
    happens, the process returns from this function.
    """
    if _logger is not None:
        _log(INFO, "Process", local.name, "pause")
    Process.current().rsim()._gr.switch()  # type: ignore


def advance(delay: float) -> None:
    """
    Pauses the current process for the given delay (in simulated time). The process will be resumed when the simulation
    has advanced to the moment corresponding to `now() + delay`.
    """
    if _logger is not None:
        _log(INFO, "Process", local.name, "advance", delay=delay)
    curr = Process.current()
    rsim = curr.rsim
    id_wakeup = rsim()._schedule(delay, curr.switch)  # type: ignore

    try:
        rsim()._gr.switch()                   # type: ignore
    except Interrupt:
        rsim()._cancel(id_wakeup)             # type: ignore
        raise


def now() -> float:
    """
    Returns current simulated time to the running process.
    """
    return Process.current().rsim().now()  # type: ignore


def add(proc: Callable, *args: Any, **kwargs: Any) -> Process:
    return Process.current().rsim().add(proc, *args, **kwargs)  # type: ignore


def add_in(delay: float, proc: Callable, *args: Any, **kwargs: Any) -> Process:
    return Process.current().rsim().add_in(delay, proc, *args, **kwargs)  # type: ignore


def add_at(moment: float, proc: Callable, *args: Any, **kwargs: Any) -> Process:
    return Process.current().rsim().add_at(moment, proc, *args, **kwargs)  # type: ignore


def stop() -> None:
    """
    Stops the ongoing simulation, from a process.
    """
    Process.current().rsim().stop()  # type: ignore


def happens(intervals: Iterable[float], name: Optional[str] = None) -> Callable:
    """
    Decorator used to set up a process that adds a new instance of another process at intervals dictated by the given
    sequence (which may be infinite).

    Example: the following program runs process named `my_process` 5 times, each time spaced by 2.0 time units.

    ```
    from itertools import repeat

    sim = Simulator()
    log = []

    @happens(repeat(2.0, 5))
    def my_process(the_log):
        the_log.append(now())

    sim.add(my_process, log)
    sim.run()

    print(str(log))  # Expect: [2.0, 4.0, 6.0, 8.0, 10.0]
    ```
    """
    def hook(event: Callable):
        def make_happen(*args_event: Any, **kwargs_event: Any) -> None:
            if name is not None:
                local.name = cast(str, name)
            for interval in intervals:
                advance(interval)
                add(event, *args_event, **kwargs_event)
        return make_happen
    return hook


def tagged(*tags: Tags) -> Callable:
    global GREENSIM_TAG_ATTRIBUTE
    """
    Decorator for adding a label to the process.
    These labels are applied to any child Processes produced by event
    """
    def hook(event: Callable):
        setattr(event, GREENSIM_TAG_ATTRIBUTE, tags)
        return event
    return hook


class Queue(Named):
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

    def __init__(self, get_order_token: Optional[GetOrderToken] = None, name: Optional[str] = None) -> None:
        super().__init__(name)
        self._waiting: List[Tuple[int, Process]] = []
        self._counter = 0
        self._get_order_token = get_order_token or (lambda counter: counter)

    def is_empty(self) -> bool:
        """
        Returns whether the queue is empty.
        """
        return len(self) == 0

    def __len__(self) -> int:
        """
        Queue length.
        """
        return len(self._waiting)

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
        if _logger is not None:
            self._log(INFO, "join")
        heappush(self._waiting, (self._get_order_token(self._counter), Process.current()))
        pause()

    def pop(self):
        """
        Removes the top process from the queue, and resumes its execution. For an empty queue, this method is a no-op.
        This method may be invoked from anywhere (its use is not confined to processes, as method `join()` is).
        """
        if not self.is_empty():
            _, process = heappop(self._waiting)
            if _logger is not None:
                self._log(INFO, "pop", process=process.local.name)
            process.resume()


class Signal(Named):
    """
    `Signal` instances model a condition on which processes can wait. When they do so, if the signal is *on*, their wait
    ends instantly. Alternatively, if it is *off*, the process is made to join a queue. It is popped out of the queue
    and resumed when the signal is turned on at once.
    """

    def __init__(self, get_order_token: Optional[Queue.GetOrderToken] = None, name: Optional[str] = None) -> None:
        super().__init__(name)
        self._is_on = True
        self._queue = Queue(get_order_token, name=self.name + "-queue")

    @property
    def is_on(self) -> bool:
        """
        Tells whether the signal is on or off.
        """
        return self._is_on

    def turn_on(self) -> "Signal":
        """
        Turns on the signal. If processes are waiting, they are all resumed. This may be invoked from any code.

        Remark that while processes are simultaneously resumed in simulated time, they are effectively resumed in the
        sequence corresponding to the queue discipline. Therefore, if one of the resumed processes turns the signal back
        off, remaining resumed processes join back the queue. If the queue discipline is not monotonic (for instance,
        if it bears a random component), then this toggling of the signal may reorder the processes.
        """
        if _logger is not None:
            self._log(INFO, "turn-on")
        self._is_on = True
        while not self._queue.is_empty():
            self._queue.pop()
        return self

    def turn_off(self) -> "Signal":
        """
        Turns off the signal. This may be invoked from any code.
        """
        if _logger is not None:
            self._log(INFO, "turn-off")
        self._is_on = False
        return self

    def wait(self) -> None:
        """
        Makes the current process wait for the signal. If it is closed, it will join the signal's queue.
        """
        if _logger is not None:
            self._log(INFO, "wait")
        while not self.is_on:
            self._queue.join()


def select(*signals: Signal) -> List[Signal]:
    """
    Allows the current process to wait for multiple concurrent signals. Waits until one of the signals turns on, at
    which point this signal is returned.
    """
    def wait_one(signal: Signal, common: Signal) -> None:
        signal.wait()
        common.turn_on()

    # We simply sets up multiple sub-processes respectively waiting for one of the signals. Once one of them has fired,
    # the others will all run no-op eventually, so no need for any explicit clean-up.
    common = Signal(name=local.name + "-selector").turn_off()
    if _logger is not None:
        _log(INFO, "select", "select", "select", signals=[sig.name for sig in signals])
    for signal in signals:
        add(wait_one, signal, common)
    common.wait()
    return [signal for signal in signals if signal.is_on]


class Resource(Named):
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

    def __init__(
        self,
        num_instances: int = 1,
        get_order_token: Optional[Queue.GetOrderToken] = None,
        name: Optional[str] = None
    ) -> None:
        super().__init__(name)
        self._num_instances_free = num_instances
        self._waiting = Queue(get_order_token, name=self.name + "-queue")
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
        if _logger is not None:
            self._log(INFO, "take", num_instances=num_instances, free=self.num_instances_free)
        proc = Process.current()
        if self._num_instances_free < num_instances:
            proc.local.__num_instances_required = num_instances
            self._waiting.join()
            del proc.local.__num_instances_required
        self._num_instances_free -= num_instances
        if _logger is not None and proc in self._usage:
            self._log(WARNING, "take-again", already=self._usage[proc], more=num_instances)
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
                    f"Process {proc.local.name} holds {self._usage[proc]} instances, " +
                    f"but requests to release more ({num_instances})"
                )
            self._usage[proc] -= num_instances
            self._num_instances_free += num_instances
            if _logger is not None:
                self._log(
                    INFO,
                    "release",
                    num_instances=num_instances,
                    keeping=self._usage[proc],
                    free=self.num_instances_free
                )
            if self._usage[proc] <= 0:
                del self._usage[proc]
            if not self._waiting.is_empty():
                num_instances_next = cast(int, self._waiting.peek().local.__num_instances_required)
                if num_instances_next <= self.num_instances_free:
                    self._waiting.pop()
                elif _logger is not None:
                    self._log(DEBUG, "release-nopop", next_requires=num_instances_next, free=self.num_instances_free)
            elif _logger is not None:
                self._log(DEBUG, "release-queueempty")
        else:
            raise RuntimeError(
                f"Process {proc.local.name} tries to release {num_instances} instances, but is holding none.)"
            )

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
