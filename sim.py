from heapq import heappush, heappop
import random

import greenlet


class Simulator(object):

    def __init__(self, ts_now = 0.0):
        self._ts_now = ts_now
        self._events = []
        self._is_running = False
        self._counter = 0

    def now(self):
        return self._ts_now

    def schedule(self, delay, event):
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
        self._is_running = True
        while self.is_running() and len(self._events) > 0:
            self._ts_now, _, event = heappop(self._events)
            event(self)
        return self

    def stop(self):
        self._is_running = False
        return self

    def is_running(self):
        return self._is_running


class Process(object):

    def __init__(self, sim, delay_start = 0.0):
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
        self.sim.schedule(delay, self._resume)
        self._gr_sim.switch()
