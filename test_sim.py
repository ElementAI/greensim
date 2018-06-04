import pytest

from sim import Simulator, Process


def test_schedule_none():
    sim = Simulator()
    assert 0.0 == sim.now()

def append(n, ll):
    def _append(sim):
        ll.append(n)
    return _append

def test_schedule_1_event():
    ll = []
    sim = Simulator()
    sim.schedule(1.0, append(1, ll))
    sim.start()
    assert ll == [1]

def test_schedule_multiple_events():
    ll = []
    sim = Simulator()
    sim.schedule(1.0, append(1, ll))
    sim.schedule(0.7, append(2, ll))
    sim.schedule(10.0, append(3, ll))
    sim.start()
    assert ll == [2,1,3]
    assert sim.now() == 10.0

def test_schedule_recurring():
    ll = [0]
    def _append(_sim):
        if _sim.now() <= 10.0:
            ll.append(ll[-1] + 1)
            _sim.schedule(1.0, _append)
        else:
            _sim.stop()
    sim = Simulator()
    sim.schedule(1.0, _append)
    sim.start()
    assert sim.now() == 11.0
    assert ll == list(range(11))


class ProcessTest(Process):

    def __init__(self, sim):
        super().__init__(sim)
        self.ll = []

    def _run(self):
        self.ll.append(self.sim.now())
        self.advance(1.0)
        self.ll.append(self.sim.now())
        self.advance(5.0)
        self.ll.append(self.sim.now())


def test_process_advance():
    sim = Simulator()
    proc = ProcessTest(sim)
    sim.start()
    assert proc.ll == [0.0, 1.0, 6.0]


class ProcessConstant(Process):

    def __init__(self, sim, name, period, log):
        super().__init__(sim, 0)
        self.name = name
        self.period = period
        self.log = log

    def _run(self):
        while True:
            self.advance(self.period)
            self.log.append((int(self.sim.now()), self.name))


class Stopper(Process):

    def _run(self):
        self.sim.stop()


def test_process_multiple():
    sim = Simulator()
    log = []
    ProcessConstant(sim, "three", 3.0, log)
    ProcessConstant(sim, "seven", 7.0, log)
    ProcessConstant(sim, "eleven", 11.0, log)
    Stopper(sim, 100.0)
    sim.start()
    assert sorted(
        [(n, "eleven") for n in range(11, 100, 11)] +
            [(n, "seven") for n in range(7, 100, 7)] +
            [(n, "three") for n in range(3, 100, 3)],
        key=lambda p: p[0]
    )
