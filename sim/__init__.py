"""
Core tools for building simulations.
"""


from abc import ABC, ABCMeta, abstractmethod
from heapq import heappush, heappop
from typing import Callable, Tuple, List, Iterable, Any, TypeVar, Optional

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
        Constructor. Parameter ts_now can be set to the initial value of the
        simulator's clock; it defaults at 0.0.
        """
        self._ts_now = ts_now
        self._events: List[Tuple[float, int, Callable]] = []
        self._is_running = False
        self._counter = 0

        self._gr = greenlet.getcurrent()  # The Simulator's main greenlet

    def now(self) -> float:
        """
        Returns the current value of the simulator's clock.
        """
        return self._ts_now

    def events(self) -> Iterable[Tuple[float, Callable]]:
        """
        Iterates over scheduled events.
        """
        return ((moment, event) for moment, _, event in self._events)

    def schedule(self, delay: float, event: Callable) -> 'Simulator':
        """
        Schedules an event to be run along the simulation. The event is
        scheduled relative to current simulator time, so delay is expected to
        be a positive simulation time interval. The `event' parameter
        corresponds to a callable object (e.g. a function): it will be called
        so as to "execute" the event, with sole parameter the simulator
        instance itself. Once this event function returns, the simulation
        carries on to the next event, or stops if none remain.
        """

        delay = float(delay)
        if delay < 0.0:
            raise ValueError("Delay must be positive.")

        # Use counter to strictly order events happening at the same
        # simulated time. This gives a total order on events, working around
        # the heap queue not yielding a stable ordering.
        heappush(self._events, (self._ts_now + delay, self._counter, event))
        self._counter += 1
        return self

    def start(self) -> None:
        """
        Runs the simulation until a stopping condition is met (no more events,
        or an event invokes method stop()).
        """
        self._is_running = True
        while self.is_running() and len(self._events) > 0:
            self._ts_now, _, event = heappop(self._events)
            event(self)

        self.stop()

    def stop(self) -> None:
        """
        Stops the running simulation once the current event is done
        executing.
        """
        self._is_running = False

    def is_running(self) -> bool:
        """
        Tells whether the simulation is currently running.
        """
        return self._is_running

    def _switch(self) -> None:
        """
        Gives control back to the simulator. Meant to be called from a Process object.
        """
        self._gr.switch()


class Process(ABC):
    """
    Abstract class used to model a process composed of a sequence of discrete
    events. A model is typically built around a set of intertwining infinite
    processes, with one of these processes triggering the termination of the
    simulation after a certain condition is met (e.g. elapsed simulation time,
    number of occurrences of a certain event, etc.). The current
    implementation leverages so-called green threads ("greenlets") as
    coroutines that alternates CPU control between process instances and the
    simulator itself.

    The sequence of events that compose the process is built by implementing
    method _run() in a Process subclass. This method performs what is needed
    to actualize an event along the process, then calls advance() to carry the
    simulation to the moment where something else happens.
    """

    def __init__(self, sim: Simulator, delay_start: float = 0.0) -> None:
        """
        Constructor. Receives a simulator instance, as well as a relative
        moment at which the process should be made to start.
        """
        self.sim = sim
        self._gr = greenlet.greenlet(lambda _sim: self._run(), self.sim._gr)
        self.schedule(delay_start)

    @abstractmethod
    def _run(self) -> None:
        """
        Implement the `run` method in your derived class.
        To re-schedule, simply call self.advance()
        """
        pass

    def schedule(self, delay: float) -> None:
        """
        Schedules execution of this process for t + `delay` time units.
        """
        self.sim.schedule(delay, self._gr.switch)

    def advance(self, delay: float) -> None:
        """
        Puts the process to "sleep," and resumes its execution only after the
        given delay in simulated time.
        """
        self.schedule(delay)
        self.sim._switch()

    def pause(self) -> None:
        """
        Indefinitely puts the process to "sleep." It will resume its execution
        only once some other process invokes its methods resume() or schedule().
        """
        self.sim._switch()

    def resume(self) -> None:
        """
        Schedules the resumption of a previously paused process immediately.
        """
        self.schedule(0.0)


class Ordered(metaclass=ABCMeta):
    @abstractmethod
    def __lt__(self, other: Any) -> bool:
        ...


Orderable = TypeVar('Orderable', bound=Ordered)
GetQueueOrderToken = Callable[[Process, int], Orderable]


class Queue(object):

    def __init__(self, sim: Simulator, get_order_token: Optional[GetQueueOrderToken] = None) -> None:
        super().__init__()
        self.sim = sim
        self._waiting: List[Process] = []
        self._counter = 0
        self._get_order_token = get_order_token or (lambda process, counter: counter)

    def is_empty(self):
        return len(self._waiting) == 0

    def join(self, process):
        self._counter += 1
        heappush(self._waiting, (self._get_order_token(process, self._counter), process))
        process.pause()

    def pop(self):
        if not self.is_empty():
            _, process = heappop(self._waiting)
            process.resume()


class Gate(object):

    def __init__(self, sim: Simulator, get_queue_order_token: Optional[GetQueueOrderToken] = None) -> None:
        super().__init__()
        self.sim = sim
        self._is_open = True
        self._queue = Queue(sim, get_queue_order_token)

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

    def cross(self, process: Process) -> None:
        while not self.is_open:
            self._queue.join(process)
