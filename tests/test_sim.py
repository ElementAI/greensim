from typing import Tuple, List
import pytest
from sim import Simulator, Process, Queue, Gate


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


class Process2(Process):

    def __init__(self, sim: Simulator, name: str, delay_start: float = 0) -> None:
        super().__init__(sim, delay_start)
        self.name = name

        self.results: List[Tuple] = []

    def _run(self):
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


@pytest.fixture
def simulator():
    return Simulator()


class ProcessPausing(Process):

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._counter = 0

    @property
    def counter(self):
        return self._counter

    def _increment(self):
        self._counter += 1

    def _run(self):
        self._increment()
        self.pause()
        self.advance(1.0)
        self._increment()


def test_process_pause_resume(simulator):
    pp = ProcessPausing(simulator, delay_start=1.0)
    simulator.start()
    assert simulator.now() == pytest.approx(1.0)
    assert pp.counter == 1
    simulator.start()
    assert simulator.now() == pytest.approx(1.0)
    assert pp.counter == 1
    pp.resume()
    simulator.start()
    assert simulator.now() == pytest.approx(2.0)
    assert pp.counter == 2


LogTestQueue = List[int]


class Queuer(Process):

    def __init__(self, name: int, queue, log: LogTestQueue, delay) -> None:
        super().__init__(queue.sim, delay)
        self.name = name
        self._queue = queue
        self._log = log

    def _run(self):
        self._queue.join(self)
        self._log.append(self.name)


class Dequeueing(Process):

    def __init__(self, queue, delay):
        super().__init__(queue.sim, delay)
        self._queue = queue

    def _run(self):
        while not self._queue.is_empty():
            self.advance(1.0)
            self._queue.pop()


@pytest.fixture
def log_test_queue() -> LogTestQueue:
    return []


def run_test_queue_join_pop(queue: Queue, log: LogTestQueue) -> None:
    for n in range(10):
        Queuer(n, queue, log, float(n + 1))
    Dequeueing(queue, 100.0)
    queue.sim.start()


def test_queue_join_pop_chrono(simulator, log_test_queue):
    run_test_queue_join_pop(Queue(simulator), log_test_queue)
    assert list(range(10)) == log_test_queue


def test_queue_join_pop_evenodd(simulator, log_test_queue):
    run_test_queue_join_pop(Queue(simulator, lambda process, counter: (process.name % 2, counter)), log_test_queue)
    assert [2 * n for n in range(5)] + [2 * n + 1 for n in range(5)] == log_test_queue


@pytest.fixture
def gate(simulator):
    return Gate(simulator)


class GoThrough(Process):

    def __init__(self, gate, times_cross_expected, time_between):
        super().__init__(gate.sim)
        self._gate = gate
        self._times_cross_expected = times_cross_expected
        self._time_between = time_between

    def _run(self):
        for expected in self._times_cross_expected:
            self.advance(self._time_between)
            self._gate.cross(self)
            assert pytest.approx(expected) == self.sim.now()


def test_gate_already_open(gate):
    gate.open()
    GoThrough(gate, [1.0], 1.0)
    gate.sim.start()


def test_gate_wait_open(gate):
    gate.close()
    GoThrough(gate, [3.0, 4.0], 1.0)
    gate.sim.schedule(3.0, lambda sim: gate.open())
    gate.sim.start()


def test_gate_toggling(gate):
    gate.close()
    GoThrough(gate, [3.0, 4.0, 10.0, 13.0], 1.0)
    gate.sim.schedule(3.0, lambda sim: gate.open())
    gate.sim.schedule(4.5, lambda sim: gate.close())
    gate.sim.schedule(10.0, lambda sim: gate.open())
    gate.sim.schedule(10.1, lambda sim: gate.close())
    gate.sim.schedule(13.0, lambda sim: gate.open())


@pytest.fixture
def log_time() -> List[float]:
    return []


class CrosserClosing(Process):

    def __init__(self, gate: Gate, log: List[float]) -> None:
        super().__init__(gate.sim)
        self._gate = gate
        self._log = log

    def _run(self) -> None:
        self._gate.cross(self)
        self._gate.close()
        self._log.append(self.sim.now())


def test_gate_crosser_closing(gate, log_time):
    for n in range(5):
        CrosserClosing(gate, log_time)
    schedule_gate_open = [4.0, 9.0, 9.1, 200.0, 3000.0]
    for moment in schedule_gate_open:
        gate.sim.schedule(moment, lambda sim: gate.open())
    gate.close()
    gate.sim.start()
    assert schedule_gate_open == pytest.approx(log_time)
