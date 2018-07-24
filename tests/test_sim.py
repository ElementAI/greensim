from itertools import repeat
import re
from typing import List, Callable

import pytest

from greensim import Simulator, Process, Named, now, advance, pause, add, happens, local, Queue, Signal, select, \
    Resource


def test_schedule_none():
    sim = Simulator()
    assert 0.0 == sim.now()


def append(n, ll):
    ll.append(n)


def test_schedule_1_event():
    ll = []
    sim = Simulator()
    sim._schedule(1.0, append, 1, ll)
    sim.run()
    assert ll == [1]


def test_schedule_multiple_events():
    ll = []
    sim = Simulator()
    sim._schedule(1.0, append, 1, ll)
    sim._schedule(0.7, append, 2, ll)
    sim._schedule(10.0, append, 3, ll)
    sim.run()
    assert ll == [2, 1, 3]
    assert sim.now() == 10.0


def test_schedule_negative():
    sim = Simulator()
    ll = []
    with pytest.raises(ValueError):
        sim._schedule(-0.5, append, 1, ll)


def test_schedule_recurring():
    ll = [0]

    def _append():
        if sim.now() <= 10.0:
            ll.append(ll[-1] + 1)
            sim._schedule(1.0, _append)
        else:
            sim.stop()

    sim = Simulator()
    sim._schedule(1.0, _append)
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
    assert not sim.is_running


def test_schedule_functions():
    def f1(sim, results):
        res = f"1 + {sim.now()}"
        results.append(res)

    def f2(sim, results):
        res = f"2 + {sim.now()}"
        results.append(res)

    sim = Simulator()
    results = []
    sim._schedule(1, f1, sim, results)
    sim._schedule(2, f2, sim, results)
    sim._schedule(3, f1, sim, results)
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


def test_getting_current_process():
    def proc():
        assert isinstance(Process.current(), Process)

    sim = Simulator()
    sim.add(proc)
    sim.run()

    with pytest.raises(TypeError):
        proc()


def test_process_adding_process():
    log = []

    def proc(delay):
        advance(delay)
        log.append(now())
        add(proc, delay * 2.0)

    sim = Simulator()
    sim.add(proc, 1.0)
    sim.run(200.0)
    assert [1.0, 3.0, 7.0, 15.0, 31.0, 63.0, 127.0] == pytest.approx(log)


def test_happens():
    sim = Simulator()
    log = []

    @happens(repeat(2.0, 5))
    def process(the_log):
        the_log.append(now())

    sim.add(process, log)
    sim.run()
    assert pytest.approx([2.0, 4.0, 6.0, 8.0, 10.0]) == log


def test_happens_named():
    @happens([5], name="my-process")
    def process():
        advance(5)

    sim = Simulator()
    proc = sim.add(process)
    sim.run()
    assert proc.local.name == "my-process"
    assert 10.0 == pytest.approx(sim.now())


def sim_add_run(proc: Callable) -> None:
    sim = Simulator()
    sim.add(proc)
    sim.run()


def test_local_set_get():
    def fn():
        assert local.param == "asdf"
        assert local.parent.child == "qwer"

    def proc():
        local.param = "asdf"
        local.parent.child = "qwer"
        fn()

    sim_add_run(proc)


def test_local_get_unknown():
    def proc():
        assert local.unknown is not None
        local.unknown = 5
        assert local.unknown == 5

    sim_add_run(proc)


def test_local_replace_hierarchy():
    def proc():
        local.a.a = 5
        local.a.b = 6
        local.b.a = 7
        local.b.b = 8
        local.a = 10
        with pytest.raises(AttributeError):
            assert local.a.a == 5
        assert local.b.a == 7
        assert local.b.b == 8
        assert local.a == 10

    sim_add_run(proc)


def is_uuid(s: str) -> bool:
    return re.match('[0-9a-f]{8}-([0-9a-f]{4}-){3}[0-9a-f]{12}', s) is not None


def test_process_has_default_name():
    def proc():
        assert isinstance(local.name, str)
        assert is_uuid(local.name)

    sim_add_run(proc)


def test_named_default_name():
    assert(is_uuid(Named(None).name))


def test_named_set_name():
    named = Named("asdf")
    assert named.name == "asdf"


def queuer(name: int, queue: Queue, log: List[int], delay: float):
    local.name = name
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
        run_test_queue_join_pop(Queue(lambda counter: counter + 1000000 * (local.name % 2)))


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


def test_queue_length():
    sim = Simulator()
    queue = Queue()
    assert 0 == len(queue)
    log = []
    for n in range(10):
        sim.add(queuer, n, queue, log, float(n + 1))
    sim.run()
    assert 10 == len(queue)
    sim.add(dequeueing, queue, 0.0)
    sim.run()
    assert 0 == len(queue)


def wait_for(signal: Signal, times_expected: List[float], delay_between: float):
    for expected in times_expected:
        advance(delay_between)
        signal.wait()
        assert pytest.approx(expected) == now()


def test_signal_already_on():
    sim = Simulator()
    signal = Signal().turn_on()
    sim.add(wait_for, signal, [1.0], 1.0)
    sim.run()


def test_signal_wait_a_while():
    sim = Simulator()
    signal = Signal().turn_off()
    sim.add(wait_for, signal, [3.0, 4.0], 1.0)
    sim._schedule(3.0, signal.turn_on)
    sim.run()


def test_signal_toggling():
    sim = Simulator()
    signal = Signal().turn_off()
    sim.add(wait_for, signal, [3.0, 4.0, 10.0, 13.0], 1.0)
    sim._schedule(3.0, signal.turn_on)
    sim._schedule(4.5, signal.turn_off)
    sim._schedule(10.0, signal.turn_on)
    sim._schedule(10.1, signal.turn_off)
    sim._schedule(13.0, signal.turn_on)
    sim.run()


def test_signal_waiter_turning_off():
    def waiter_turning_off(signal: Signal, log: List[float]):
        signal.wait()
        signal.turn_off()
        log.append(now())

    sim = Simulator()
    signal = Signal().turn_off()
    log_time = []
    for n in range(5):
        sim.add(waiter_turning_off, signal, log_time)
    schedule_signal_on = [4.0, 9.0, 9.1, 200.0, 3000.0]
    for moment in schedule_signal_on:
        sim._schedule(moment, signal.turn_on)
    sim.run()
    assert schedule_signal_on == pytest.approx(log_time)


def turn_on(delay: float, signal: Signal) -> None:
    advance(delay)
    signal.turn_on()


def test_select_one_on():
    has_passed = False

    def selecter(sigs: List[Signal]):
        nonlocal has_passed
        select(*sigs)
        has_passed = True

    sim = Simulator()
    signals = [Signal().turn_off() for n in range(5)]
    sim.add(selecter, signals)
    sim.run()
    assert not has_passed
    signals[3].turn_on()
    sim.run()
    assert has_passed


def test_select_multiple_turn_on():
    def selecter(sigs: List[Signal], expected: List[bool]) -> None:
        signals_on = select(*sigs)
        for expd, sig in zip(expected, sigs):
            if expd:
                assert sig in signals_on
            else:
                assert sig not in signals_on

    def enabler(delay: float, sig: Signal) -> None:
        advance(delay)
        sig.turn_on()

    sim = Simulator()
    delays = [4.0, 1.0, 3.0, 1.0, 9.0]
    signals = [Signal().turn_off() for n in range(5)]
    for delay, signal in zip(delays, signals):
        sim.add(enabler, delay, signal)
    sim.add(selecter, signals, [delay < 2.0 for delay in delays])
    sim.run()


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
