from typing import List, Callable

import pytest

from greensim import Simulator, Process, now, advance, pause, Queue, Gate, Resource


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
    sim = Simulator()
    sim.add(process, ll)
    sim.run()
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
    sim.run(100.0)
    assert sorted(
        [(n, "eleven") for n in range(11, 100, 11)] +
        [(n, "seven") for n in range(7, 100, 7)] +
        [(n, "three") for n in range(3, 100, 3)],
        key=lambda p: p[0]
    )


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


def test_process_pause_resume():
    counter = 0

    def pausing():
        nonlocal counter
        advance(1.0)
        counter += 1
        pause()
        advance(1.0)
        counter += 1

    sim = Simulator()
    process = sim.add(pausing)
    sim.run()
    assert sim.now() == pytest.approx(1.0)
    assert counter == 1
    sim.run()
    assert sim.now() == pytest.approx(1.0)
    assert counter == 1
    process.resume()
    sim.run()
    assert sim.now() == pytest.approx(2.0)
    assert counter == 2


def queuer(name: int, queue: Queue, log: List[int], delay: float):
    Process.current().local["name"] = name
    advance(delay)
    queue.join()
    log.append(name)


def dequeueing(queue, delay):
    advance(delay)
    while not queue.is_empty():
        advance(1.0)
        queue.pop()


def run_test_queue_join_pop(queue: Queue) -> List[int]:
    sim = Simulator()
    log: List[int] = []
    for n in range(10):
        sim.add(queuer, n, queue, log, float(n + 1))
    sim.add(dequeueing, queue, 100.0)
    sim.run()
    return log


def test_queue_join_pop_chrono():
    assert list(range(10)) == run_test_queue_join_pop(Queue())


def test_queue_join_pop_evenodd():
    assert [2 * n for n in range(5)] + [2 * n + 1 for n in range(5)] == \
        run_test_queue_join_pop(Queue(lambda counter: counter + 1000000 * (Process.current().local["name"] % 2)))


def test_queue_pop_empty():
    sim = Simulator()
    queue = Queue()
    log = []
    sim.add(queuer, 1, queue, log, 1.0)
    sim.run()
    assert [] == log
    queue.pop()
    sim.run()
    assert [1] == log
    assert queue.is_empty()
    queue.pop()  # Raises an exception unless empty queue is properly processed.
    sim.run()
    assert [1] == log


def go_through(gate: Gate, times_cross_expected: List[float], delay_between: float):
    for expected in times_cross_expected:
        advance(delay_between)
        gate.cross()
        assert pytest.approx(expected) == now()


def test_gate_already_open():
    sim = Simulator()
    gate = Gate().open()
    sim.add(go_through, gate, [1.0], 1.0)
    sim.run()


def test_gate_wait_open():
    sim = Simulator()
    gate = Gate().close()
    sim.add(go_through, gate, [3.0, 4.0], 1.0)
    sim.schedule(3.0, gate.open)
    sim.run()


def test_gate_toggling():
    sim = Simulator()
    gate = Gate().close()
    sim.add(go_through, gate, [3.0, 4.0, 10.0, 13.0], 1.0)
    sim.schedule(3.0, gate.open)
    sim.schedule(4.5, gate.close)
    sim.schedule(10.0, gate.open)
    sim.schedule(10.1, gate.close)
    sim.schedule(13.0, gate.open)
    sim.run()


def test_gate_crosser_closing():
    def crosser_closing(gate: Gate, log: List[float]):
        gate.cross()
        gate.close()
        log.append(now())

    sim = Simulator()
    gate = Gate().close()
    log_time = []
    for n in range(5):
        sim.add(crosser_closing, gate, log_time)
    schedule_gate_open = [4.0, 9.0, 9.1, 200.0, 3000.0]
    for moment in schedule_gate_open:
        sim.schedule(moment, gate.open)
    sim.run()
    assert schedule_gate_open == pytest.approx(log_time)


def do_while_holding_resource(delay: float, log: List[float]):
    advance(delay)
    log.append(now())


ResourceTaker = Callable[[Resource, float, List[float]], None]


def run_test_resource(resource_taker: ResourceTaker, num_instances: int, expected: List[float]) -> None:
    sim = Simulator()
    resource = Resource(num_instances)
    log: List[float] = []
    for n in range(8):
        sim.add(resource_taker, resource, float(n + 1), log)
    sim.run()
    assert expected == pytest.approx(log)


def take_release(resource: Resource, delay: float, log: List[float]) -> None:
    resource.take()
    do_while_holding_resource(delay, log)
    resource.release()


def test_resource_take_release_1():
    run_test_resource(take_release, 1, [1.0, 3.0, 6.0, 10.0, 15.0, 21.0, 28.0, 36.0])


def test_resource_take_release_5():
    run_test_resource(take_release, 5, [1.0, 2.0, 3.0, 4.0, 5.0, 7.0, 9.0, 11.0])


def take_using(resource: Resource, delay: float, log: List[float]) -> None:
    with resource.using():
        do_while_holding_resource(delay, log)


def test_resource_context_manager():
    run_test_resource(take_using, 2, [1.0, 2.0, 4.0, 6.0, 9.0, 12.0, 16.0, 20.0])


def take_many(resource: Resource, delay: float, log: List[float]) -> None:
    with resource.using(int(delay)):
        do_while_holding_resource(delay, log)


def test_resource_many_once():
    run_test_resource(take_many, 10, [1.0, 2.0, 3.0, 4.0, 8.0, 14.0, 21.0, 29.0])


def take_M_release_N(resource: Resource, num_take: int, num_release: int) -> None:
    resource.take(num_take)
    advance(1.0)
    resource.release(num_release)


def run_resource_test_incoherent(num_take: int, num_release: int):
    sim = Simulator()
    resource = Resource(5)
    sim.add(take_M_release_N, resource, num_take, num_release)
    with pytest.raises(ValueError):
        sim.run()
        assert resource.num_instances_free >= 0
        assert resource.num_instances_total == 5


def test_resource_take_less_than_1():
    for num in [0, -1]:
        run_resource_test_incoherent(num, 1)


def test_resource_take_more_than_max():
    run_resource_test_incoherent(6, 0)


def test_resource_release_more_than_take():
    run_resource_test_incoherent(1, 2)
    run_resource_test_incoherent(3, 5)
