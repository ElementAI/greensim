from typing import Tuple, List

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
    assert ll == [2, 1, 3]
    assert sim.now() == 10.0


def test_schedule_recurring():
    ll = [0]

    def _append(sim):
        if sim.now() <= 10.0:
            ll.append(ll[-1] + 1)
            sim.schedule(1.0, _append)
        else:
            sim.stop()

    sim = Simulator()
    sim.schedule(1.0, _append)
    sim.start()
    assert sim.now() == 11.0
    assert ll == list(range(11))


class ProcessTest(Process):

    def __init__(self, sim):
        super().__init__(sim)
        self.ll = []

    def _run(self, sim):
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

    def _run(self, sim):
        while True:
            self.advance(self.period)
            self.log.append((int(self.sim.now()), self.name))


class Stopper(Process):

    def _run(self, sim):
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


class Process2(Process):

    def __init__(self, sim: Simulator, name: str, delay_start: float = 0) -> None:
        super().__init__(sim, delay_start)
        self.name = name

        self.results: List[Tuple] = []

    def _run(self, sim):
        self.results.append((self.sim.now(), self.name, 0))
        self.advance(2)
        self.results.append((self.sim.now(), self.name, 1))
        self.advance(2)
        self.results.append((self.sim.now(), self.name, 2))
        self.advance(2)
        self.results.append((self.sim.now(), self.name, 3))
        self.advance(2)
        self.results.append((self.sim.now(), self.name, 4))


def test_interleaved_sequence():
    sim = Simulator()
    p1 = Process2(sim, "p1")
    p2 = Process2(sim, "p2", delay_start=1)

    sim.start()
    print(p1.results)
    print(p2.results)
    assert [(0.0, 'p1', 0), (2.0, 'p1', 1), (4.0, 'p1', 2), (6.0, 'p1', 3), (8.0, 'p1', 4)] == p1.results
    assert [(1.0, 'p2', 0), (3.0, 'p2', 1), (5.0, 'p2', 2), (7.0, 'p2', 3), (9.0, 'p2', 4)] == p2.results
    assert not sim.is_running()


test_functions_result = []


def test_schedule_functions():
    def f1(sim):
        res = f"1 + {sim.now()}"
        test_functions_result.append(res)

    def f2(sim):
        res = f"2 + {sim.now()}"
        test_functions_result.append(res)

    sim = Simulator()
    sim.schedule(1, f1)
    sim.schedule(2, f2)
    sim.schedule(3, f1)
    sim.start()
    assert ['1 + 1.0', '2 + 2.0', '1 + 3.0'] == test_functions_result