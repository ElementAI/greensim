from heapq import heappush, heappop
import random

import greenlet


class Simulator(object):
    """
    This class articulates the dynamic sequence of events that composes a
    discrete event system. While it may be used by itself, using method
    schedule(), its use in conjuction with subclasses of abstract class
    Process yields an elegant DSL for modeling discrete event systems.

    Each event within a simulation is associated to a moment on the
    simulator's clock. This timeline is completely abstract: a 1.0 unit on
    this clock corresponds to whatever unit of time is convenient to the
    model author (such correspondance, when relevant, is best documented for
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

    def __init__(self, ts_now = 0.0):
        """
        Constructor. Parameter ts_now can be set to the initial value of the
        simulator's clock; it defaults at 0.0.
        """
        self._ts_now = ts_now
        self._events = []
        self._is_running = False
        self._counter = 0

    def now(self):
        """
        Returns the current value of the simulator's clock.
        """
        return self._ts_now

    def schedule(self, delay, event):
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

    def start(self):
        """
        Runs the simulation until a stopping condition is met (no more events,
        or an event invokes method stop()).
        """
        self._is_running = True
        while self.is_running() and len(self._events) > 0:
            self._ts_now, _, event = heappop(self._events)
            event(self)
        return self

    def stop(self):
        """
        Stops the running simulation once the current event is done
        executing.
        """
        self._is_running = False
        return self

    def is_running(self):
        """
        Tells whether the simulation is currently running.
        """
        return self._is_running


class Process(object):
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

    def __init__(self, sim, delay_start = 0.0):
        """
        Constructor. Receives a simulator instance, as well as a relative
        moment at which the process should be made to start.
        """
        self.sim = sim
        self._gr = greenlet.greenlet(self._start)
        self._gr_sim = None
        self.sim.schedule(delay_start, self._resume)

    def _start(self, gr_sim):
        self._gr_sim = gr_sim
        self._run()

    def _resume(self, _sim):
        self._gr.switch(greenlet.getcurrent())

    def advance(self, delay):
        """
        Puts the process to "sleep," and resumes its execution only after the
        given delay in simulated time.
        """
        self.sim.schedule(delay, self._resume)
        self._gr_sim.switch()