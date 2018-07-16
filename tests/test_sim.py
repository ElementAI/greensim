from typing import Tuple, List, Callable

import pytest

from greensim import Simulator, now, advance #Queue, Gate, Resource


def test_schedule_none():
    sim = Simulator()
    assert 0.0 == sim.now()


def append(n, ll):
    ll.append(n)


def test_schedule_1_event():
    ll = []
    sim = Simulator()
    sim.schedule(1.0, append, 1, ll)
    sim.run()
    assert ll == [1]


def test_schedule_multiple_events():
    ll = []
    sim = Simulator()
    sim.schedule(1.0, append, 1, ll)
    sim.schedule(0.7, append, 2, ll)
    sim.schedule(10.0, append, 3, ll)
    sim.run()
    assert ll == [2, 1, 3]
    assert sim.now() == 10.0


def test_schedule_recurring():
    ll = [0]

    def _append():
        if sim.now() <= 10.0:
            ll.append(ll[-1] + 1)
            sim.schedule(1.0, _append)
        else:
            sim.stop()

    sim = Simulator()
    sim.schedule(1.0, _append)
    sim.run()
    assert sim.now() == 11.0
    assert ll == list(range(11))


def test_process_advance():
    def process(ll):
        ll.append(now())
        advance(1.0)
        ll.append(now())
        advance(5.0)
        ll.append(now())

    ll = []
    Simulator().add(process, ll).run()
    assert ll == [0.0, 1.0, 6.0]


def test_process_multiple():
    def tick(name, period, log):
        while True:
            advance(period)
            log.append((int(now()), name))

    sim = Simulator()
    log = []
    sim.add(tick, "three", 3.0, log)
    sim.add(tick, "seven", 7.0, log)
    sim.add(tick, "eleven", 11.0, log)
    sim.stop_at(100.0)
    sim.run()
    assert sorted(
        [(n, "eleven") for n in range(11, 100, 11)] +
        [(n, "seven") for n in range(7, 100, 7)] +
        [(n, "three") for n in range(3, 100, 3)],
        key=lambda p: p[0]
    )


# class Process2(Process):

#     def __init__(self, sim: Simulator, name: str, delay_start: float = 0) -> None:
#         super().__init__(sim, delay_start)
#         self.name = name

#         self.results: List[Tuple] = []

#     def _run(self):
#         self.results.append((self.sim.now(), self.name, 0))
#         self.advance(2)
#         self.results.append((self.sim.now(), self.name, 1))
#         self.advance(2)
#         self.results.append((self.sim.now(), self.name, 2))
#         self.advance(2)
#         self.results.append((self.sim.now(), self.name, 3))
#         self.advance(2)
#         self.results.append((self.sim.now(), self.name, 4))


def test_interleaved_sequence():
    def process(name, results, delay_start):
        advance(delay_start)
        for n in range(5):
            results.append((now(), name, n))
            advance(2)

    sim = Simulator()
    results_p1 = []
    sim.add(process, "p1", results_p1, 0)
    results_p2 = []
    sim.add(process, "p2", results_p2, 1)

    sim.run()
    assert [(0.0, 'p1', 0), (2.0, 'p1', 1), (4.0, 'p1', 2), (6.0, 'p1', 3), (8.0, 'p1', 4)] == results_p1
    assert [(1.0, 'p2', 0), (3.0, 'p2', 1), (5.0, 'p2', 2), (7.0, 'p2', 3), (9.0, 'p2', 4)] == results_p2
    assert not sim.is_running()


# test_functions_result = []


def test_schedule_functions():
    def f1(sim, results):
        res = f"1 + {sim.now()}"
        results.append(res)

    def f2(sim, results):
        res = f"2 + {sim.now()}"
        results.append(res)

    sim = Simulator()
    results = []
    sim.schedule(1, f1, sim, results)
    sim.schedule(2, f2, sim, results)
    sim.schedule(3, f1, sim, results)
    sim.run()
    assert ['1 + 1.0', '2 + 2.0', '1 + 3.0'] == results


# @pytest.fixture
# def simulator():
#     return Simulator()


# class ProcessPausing(Process):

#     def __init__(self, *args, **kwargs):
#         super().__init__(*args, **kwargs)
#         self._counter = 0

#     @property
#     def counter(self):
#         return self._counter

#     def _increment(self):
#         self._counter += 1

#     def _run(self):
#         self._increment()
#         self.pause()
#         self.advance(1.0)
#         self._increment()


# def test_process_pause_resume(simulator):
#     pp = ProcessPausing(simulator, delay_start=1.0)
#     simulator.start()
#     assert simulator.now() == pytest.approx(1.0)
#     assert pp.counter == 1
#     simulator.start()
#     assert simulator.now() == pytest.approx(1.0)
#     assert pp.counter == 1
#     pp.resume()
#     simulator.start()
#     assert simulator.now() == pytest.approx(2.0)
#     assert pp.counter == 2


# LogTestQueue = List[int]


# class Queuer(Process):

#     def __init__(self, name: int, queue, log: LogTestQueue, delay) -> None:
#         super().__init__(queue.sim, delay)
#         self.name = name
#         self._queue = queue
#         self._log = log

#     def _run(self):
#         self._queue.join(self)
#         self._log.append(self.name)


# class Dequeueing(Process):

#     def __init__(self, queue, delay):
#         super().__init__(queue.sim, delay)
#         self._queue = queue

#     def _run(self):
#         while not self._queue.is_empty():
#             self.advance(1.0)
#             self._queue.pop()


# @pytest.fixture
# def log_test_queue() -> LogTestQueue:
#     return []


# def run_test_queue_join_pop(queue: Queue, log: LogTestQueue) -> None:
#     for n in range(10):
#         Queuer(n, queue, log, float(n + 1))
#     Dequeueing(queue, 100.0)
#     queue.sim.run()


# def test_queue_join_pop_chrono(simulator, log_test_queue):
#     run_test_queue_join_pop(Queue(simulator), log_test_queue)
#     assert list(range(10)) == log_test_queue


# def test_queue_join_pop_evenodd(simulator, log_test_queue):
#     run_test_queue_join_pop(
#         Queue(simulator, lambda process, counter: counter + 1000000 * (process.name % 2)),
#         log_test_queue
#     )
#     assert [2 * n for n in range(5)] + [2 * n + 1 for n in range(5)] == log_test_queue


# def test_queue_pop_empty(simulator: Simulator, log_test_queue: LogTestQueue):
#     queue: Queue = Queue(simulator)
#     Queuer(1, queue, log_test_queue, 1.0)
#     # for delay in [10.0, 20.0]:
#     #     simulator.schedule(delay, lambda sim: queue.pop())
#     simulator.start()
#     assert [] == log_test_queue
#     queue.pop()
#     simulator.start()
#     assert [1] == log_test_queue
#     assert queue.is_empty()
#     queue.pop()  # Raises an exception unless empty queue is properly processed.
#     simulator.start()
#     assert [1] == log_test_queue


# @pytest.fixture
# def gate(simulator):
#     return Gate(simulator)


# class GoThrough(Process):

#     def __init__(self, gate, times_cross_expected, time_between):
#         super().__init__(gate.sim)
#         self._gate = gate
#         self._times_cross_expected = times_cross_expected
#         self._time_between = time_between

#     def _run(self):
#         for expected in self._times_cross_expected:
#             self.advance(self._time_between)
#             self._gate.cross(self)
#             assert pytest.approx(expected) == self.sim.now()


# def test_gate_already_open(gate):
#     gate.open()
#     GoThrough(gate, [1.0], 1.0)
#     gate.sim.run()


# def test_gate_wait_open(gate):
#     gate.close()
#     GoThrough(gate, [3.0, 4.0], 1.0)
#     gate.sim.schedule(3.0, lambda sim: gate.open())
#     gate.sim.run()


# def test_gate_toggling(gate):
#     gate.close()
#     GoThrough(gate, [3.0, 4.0, 10.0, 13.0], 1.0)
#     gate.sim.schedule(3.0, lambda sim: gate.open())
#     gate.sim.schedule(4.5, lambda sim: gate.close())
#     gate.sim.schedule(10.0, lambda sim: gate.open())
#     gate.sim.schedule(10.1, lambda sim: gate.close())
#     gate.sim.schedule(13.0, lambda sim: gate.open())


# @pytest.fixture
# def log_time() -> List[float]:
#     return []


# class CrosserClosing(Process):

#     def __init__(self, gate: Gate, log: List[float]) -> None:
#         super().__init__(gate.sim)
#         self._gate = gate
#         self._log = log

#     def _run(self) -> None:
#         self._gate.cross(self)
#         self._gate.close()
#         self._log.append(self.sim.now())


# def test_gate_crosser_closing(gate, log_time):
#     for n in range(5):
#         CrosserClosing(gate, log_time)
#     schedule_gate_open = [4.0, 9.0, 9.1, 200.0, 3000.0]
#     for moment in schedule_gate_open:
#         gate.sim.schedule(moment, lambda sim: gate.open())
#     gate.close()
#     gate.sim.run()
#     assert schedule_gate_open == pytest.approx(log_time)


# class ResourceTaker(Process):

#     def __init__(self, resource: Resource, delay_with: float, log: List[float]) -> None:
#         super().__init__(resource.sim)
#         self._resource = resource
#         self._delay = delay_with
#         self._log = log

#     def _run(self) -> None:
#         self._resource.take(self)
#         self.do_while_holding_resource()
#         self._resource.release(self)

#     def do_while_holding_resource(self) -> None:
#         self.advance(self._delay)
#         self._log.append(self.sim.now())


# ResourceTakerConstructor = Callable[[Resource, float, List[float]], ResourceTaker]


# def run_test_resource(constructor: ResourceTakerConstructor, num_instances: int, expected: List[float]) -> None:
#     sim = Simulator()
#     resource = Resource(sim, num_instances)
#     log: List[float] = []
#     for n in range(8):
#         constructor(resource, float(n + 1), log)
#     sim.run()
#     assert expected == pytest.approx(log)


# def test_resource_take_release_1():
#     run_test_resource(ResourceTaker, 1, [1.0, 3.0, 6.0, 10.0, 15.0, 21.0, 28.0, 36.0])


# def test_resource_take_release_5(simulator: Simulator):
#     run_test_resource(ResourceTaker, 5, [1.0, 2.0, 3.0, 4.0, 5.0, 7.0, 9.0, 11.0])


# class ResourceTakerWith(ResourceTaker):

#     def _run(self) -> None:
#         with self._resource.using(self):
#             self.do_while_holding_resource()


# def test_resource_context_manager(simulator, log_time):
#     run_test_resource(ResourceTakerWith, 2, [1.0, 2.0, 4.0, 6.0, 9.0, 12.0, 16.0, 20.0])


# class ResourceTakerManyOnce(ResourceTaker):

#     def _run(self) -> None:
#         with self._resource.using(self, int(self._delay)):
#             self.do_while_holding_resource()


# def test_resource_many_once(simulator, log_time):
#     run_test_resource(ResourceTakerManyOnce, 10, [1.0, 2.0, 3.0, 4.0, 8.0, 14.0, 21.0, 29.0])


# class ResourceTakeRelease(Process):

#     def __init__(self, resource: Resource, num_take: int, num_release: int) -> None:
#         super().__init__(resource.sim)
#         self._resource = resource
#         self._num_take = num_take
#         self._num_release = num_release

#     def _run(self) -> None:
#         self._resource.take(self, self._num_take)
#         self.advance(1.0)
#         self._resource.release(self, self._num_release)


# def run_resource_test_incoherent(num_take: int, num_release: int):
#     sim = Simulator()
#     resource = Resource(sim, 5)
#     with pytest.raises(ValueError):
#         ResourceTakeRelease(resource, num_take, num_release)
#         sim.run()
#         assert resource.num_instances_free >= 0
#         assert resource.num_instances_total == 5


# def test_resource_take_less_than_1():
#     for num in [0, -1]:
#         run_resource_test_incoherent(num, 1)


# def test_resource_take_more_than_max():
#     run_resource_test_incoherent(6, 0)


# def test_resource_release_more_than_take():
#     run_resource_test_incoherent(1, 2)
#     run_resource_test_incoherent(3, 5)
