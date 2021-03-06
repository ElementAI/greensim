import gc
from itertools import repeat
import re
from typing import List, Callable

import greenlet
import pytest

from greensim import GREENSIM_TAG_ATTRIBUTE, Simulator, Process, Named, now, advance, pause, add, happens, local, \
    Queue, Signal, select, Resource, add_in, add_at, tagged, Interrupt, _Event, Timeout
from greensim.tags import Tags


class TestTag(Tags):
    # Prevent Pytest from complaining
    __test__ = False
    ALICE = 0
    BOB = "BOB"


def test_event_order():
    assert _Event(1.0, 89, lambda: None) < _Event(1.1, 1, lambda: None)
    assert _Event(1.0, 43, lambda: None) < _Event(1.0, 89, lambda: None)


def test_event_order_misuse():
    with pytest.raises(ValueError):
        _Event(1.0, 89, lambda: None) < 5


def test_nonevent_inequality():
    assert _Event(1.0, 89, lambda: None) != 5


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


@pytest.fixture
def sim_cancellable():
    ll = []
    sim = Simulator()
    id_event = []
    for n in [1, 3, 5]:
        id_event.append(sim._schedule(n, append, n, ll))
    return ll, sim, id_event


def test_schedule_cancel(sim_cancellable):
    ll, sim, id_event = sim_cancellable
    sim._cancel(id_event[1])
    sim.run()
    assert ll == [1, 5]
    assert sim.now() == 5.0


def test_schedule_cancel_last(sim_cancellable):
    ll, sim, id_event = sim_cancellable
    sim._cancel(id_event[2])
    sim.run()
    assert ll == [1, 3]
    assert sim.now() == 3.0


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


def test_simulator_step():
    def process(ll):
        ll.append(now())
        advance(1.0)
        ll.append(now())
        advance(5.0)
        ll.append(now())

    ll = []
    sim = Simulator()
    sim.add(process, ll)
    sim.step()
    assert ll == pytest.approx([0.0])
    sim.step()
    assert ll == pytest.approx([0.0, 1.0])
    sim.step()
    assert ll == pytest.approx([0.0, 1.0, 6.0])


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
    expectation = [(n, "eleven") for n in range(11, 100, 11)]
    expectation += [(n, "seven") for n in range(7, 100, 7)]
    expectation += [(n, "three") for n in range(3, 100, 3)]
    assert sorted(expectation,
                  key=lambda p: p[0]
                  ) == log


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


def run_test_process_add(launcher):
    when_last = 0.0

    def last_proc():
        nonlocal when_last
        when_last = now()

    sim = Simulator()
    sim.add(launcher, last_proc)
    sim.run()
    assert pytest.approx(50.0) == when_last


def test_process_add_in():
    def launch(last):
        advance(25)
        add_in(25, last)

    run_test_process_add(launch)


def test_process_add_at():
    def launch(last):
        advance(25)
        add_at(50, last)

    run_test_process_add(launch)


def test_process_add_at_past():
    def launch(last):
        advance(51)
        add_at(50, last)

    with pytest.raises(ValueError):
        run_test_process_add(launch)


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


def do_test_with_interrupter(main, ll_expected, now_expected):
    def interrupter(main):
        advance(10.1)
        main.interrupt()

    ll = []
    sim = Simulator()
    proc_main = sim.add(main, ll)
    sim.add(interrupter, proc_main)
    sim.run()
    assert ll == pytest.approx(ll_expected)
    assert sim.now() == pytest.approx(now_expected)


def test_process_interrupt_advancing():
    def main(ll):
        for n in range(4):
            t = n * 5.0
            ll.append(t)
            advance(t)

    do_test_with_interrupter(main, [0.0, 5.0, 10.0], 10.1)


def test_process_interrupt_paused():
    def main(ll):
        ll.append(0)
        pause()
        ll.append(1)

    do_test_with_interrupter(main, [0], 10.1)


def test_process_interrupt_catch():
    def main(ll):
        try:
            ll.append(0)
            advance(15.0)
            ll.append(1)
        except Interrupt:
            ll.append(10)
        advance(5.0)
        ll.append(2)

    do_test_with_interrupter(main, [0, 10, 2], 15.1)


def test_getting_current_process():
    def proc():
        assert isinstance(Process.current(), Process)

    sim = Simulator()
    sim.add(proc)
    sim.run()

    with pytest.raises(TypeError):
        proc()


def test_probing_current_process():
    def proc():
        assert Process.current_exists()

    assert not Process.current_exists()
    sim = Simulator()
    sim.add(proc)
    sim.run()
    assert not Process.current_exists()


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


def test_queue_timeout():
    result = 0
    queue = Queue()
    sim = Simulator()

    def join_then_balk():
        nonlocal result
        try:
            queue.join(10.0)
            result = -1
        except Timeout:
            result = 1
            sim.stop()

    def would_pop():
        nonlocal result
        advance(20.0)
        queue.pop()
        result += 1

    sim.add(join_then_balk)
    sim.add(would_pop)
    sim.run()
    assert result == 1
    assert(sim.now() == pytest.approx(10.0))
    assert len(queue) == 0
    sim.run()
    assert result == 2
    assert(sim.now() == pytest.approx(20.0))


def test_queue_timeout_maintain_order():
    queue = Queue()
    log = []

    def join_and_balk(name, timeout):
        try:
            queue.join(timeout)
            log.append((name, "finish"))
        except Timeout:
            log.append((name, "balk"))

    def pop():
        while len(queue) > 0:
            advance(50)
            queue.pop()

    sim = Simulator()
    for name, timeout_balk in [("a", None), ("b", 10), ("c", None), ("d", 80), ("e", None)]:
        sim.add(join_and_balk, name, timeout_balk)
    sim.add(pop)
    sim.run()
    assert log == [("b", "balk"), ("a", "finish"), ("d", "balk"), ("c", "finish"), ("e", "finish")]


def test_cancel_timeout():
    queue = Queue()
    log = []

    def join_and_balk(name):
        try:
            queue.join(100)
            log.append((name, "finish"))
        except Timeout:
            log.append((name, "balk"))

    def pop():
        queue.pop()

    sim = Simulator()
    sim.add(join_and_balk, "a")
    sim.add_in(50, pop)
    sim.run()
    assert log == [("a", "finish")]


class InterruptCustom(Interrupt):
    pass


def test_timeout_interrupt():
    queue = Queue()
    sim = Simulator()
    log = []

    def queueing():
        log.append("queued")
        try:
            queue.join(timeout=100)
        except InterruptCustom:
            log.append("interrupt")

    proc_queueing = sim.add(queueing)
    sim.run(50)
    assert(log == ["queued"])
    assert(len(queue) == 1)

    proc_queueing.interrupt(InterruptCustom())
    sim.run(10)
    assert(log == ["queued", "interrupt"])
    assert(len(queue) == 0)
    assert(len(list(sim.events())) == 0)


def wait_for(signal: Signal, times_expected: List[float], delay_between: float, log: List[float] = []):
    for expected in times_expected:
        advance(delay_between)
        signal.wait()
        assert pytest.approx(expected) == now()
        log.append(now())


def test_signal_already_on():
    sim = Simulator()
    signal = Signal().turn_on()
    log = []
    expectation = [1.0]
    sim.add(wait_for, signal, expectation, 1.0, log)
    sim.run()
    assert expectation == log


def test_signal_wait_a_while():
    sim = Simulator()
    signal = Signal().turn_off()
    log = []
    expectation = [3.0, 4.0]
    sim.add(wait_for, signal, expectation, 1.0, log)
    sim._schedule(3.0, signal.turn_on)
    sim.run()
    assert expectation == log


def test_signal_toggling():
    sim = Simulator()
    signal = Signal().turn_off()
    log = []
    expectation = [3.0, 4.0, 10.0, 13.0, 14.0, 15.0]
    sim.add(wait_for, signal, expectation, 1.0, log)
    sim._schedule(3.0, signal.turn_on)
    sim._schedule(4.5, signal.turn_off)
    sim._schedule(10.0, signal.turn_on)
    sim._schedule(10.1, signal.turn_off)
    sim._schedule(13.0, signal.turn_on)
    sim.run()
    assert expectation == log


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


def test_signal_timeout():
    log = []
    signal = Signal().turn_off()

    def wait_then_balk(name: str, delay_balk: float) -> None:
        try:
            signal.wait(delay_balk)
            log.append((name, "finish"))
        except Timeout:
            log.append((name, "balk"))

    def turn_on():
        advance(20.0)
        signal.turn_on()

    sim = Simulator()
    sim.add(wait_then_balk, "a", 10.0)
    sim.add(wait_then_balk, "b", 30.0)
    sim.add(turn_on)
    sim.run()
    assert log == [("a", "balk"), ("b", "finish")]


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


def test_select_timeout():
    sigs = [Signal().turn_off() for n in range(5)]
    log = []

    def selecter() -> None:
        try:
            select(*sigs, timeout=10.0)
            log.append(1)
        except Timeout:
            log.append(2)

    def turn_on() -> None:
        advance(25.0)
        sigs[0].turn_on()

    sim = Simulator()
    sim.add(selecter)
    sim.add(turn_on)
    sim.run()
    assert log == [2]


def test_select_timeout_bad_parameter():
    sigs = [Signal().turn_off() for n in range(5)]
    log = []

    def selecter() -> None:
        try:
            select(*sigs, timeout="asdf")
            log.append(1)
        except Timeout:
            log.append(2)

    def turn_on() -> None:
        advance(25.0)
        sigs[0].turn_on()

    sim = Simulator()
    sim.add(selecter)
    sim.add(turn_on)
    with pytest.raises(ValueError):
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


def test_resource_release_while_holding_none():
    def proc(resource: Resource) -> None:
        resource.release()
        pytest.fail()

    sim = Simulator()
    resource = Resource(1)
    sim.add(proc, resource)
    with pytest.raises(RuntimeError):
        sim.run()


def test_resource_timeout():
    resource = Resource(1)
    log = []

    def take_but_balk(name, delay_balk):
        try:
            with resource.using(timeout=delay_balk):
                advance(20.0)
                log.append((name, "finish"))
        except Timeout:
            log.append((name, "balk"))

    sim = Simulator()
    sim.add(take_but_balk, "a", 10.0)
    sim.add_in(5.0, take_but_balk, "b", 10.0)
    sim.run()
    assert log == [("b", "balk"), ("a", "finish")]


class SimulatorWithDestructor(Simulator):

    def __init__(self, log_destroy):
        super().__init__()
        self._log_destroy = log_destroy

    def __del__(self):
        super().__del__()
        self._log_destroy.append("sim")


@pytest.fixture
def log_destroy():
    return []


def just_advance(name, delay, log):
    try:
        local.name = name
        advance(delay)
    except greenlet.GreenletExit:
        log.append(local.name + " EXIT")
    finally:
        log.append(local.name + " finish")


def set_up_simulator_with_destructor(log_destroy):
    sim = SimulatorWithDestructor(log_destroy)
    sim.add(just_advance, "A", 10.0, log_destroy)
    sim.add(just_advance, "B", 20.0, log_destroy)
    sim.add(just_advance, "C", 30.0, log_destroy)
    sim.add(just_advance, "D", 20.0, log_destroy)
    return sim


def test_simulator_gc_all_proceses_done(log_destroy):
    sim = set_up_simulator_with_destructor(log_destroy)
    sim.run()
    assert len(list(sim.events())) == 0
    assert log_destroy == ["A finish", "B finish", "D finish", "C finish"]
    sim = None
    gc.collect()
    assert log_destroy == ["A finish", "B finish", "D finish", "C finish", "sim"]


def test_simulator_gc_processes_hanging(log_destroy):
    sim = set_up_simulator_with_destructor(log_destroy)
    sim.run(15.0)
    assert len(list(sim.events())) > 0
    assert log_destroy == ["A finish"]
    sim = None
    gc.collect(0)
    assert log_destroy == ["A finish", "B EXIT", "B finish", "D EXIT", "D finish", "C EXIT", "C finish", "sim"]


def test_simulator_context_manager(log_destroy):
    with set_up_simulator_with_destructor(log_destroy) as sim:
        sim.run(15.0)
        assert len(list(sim.events())) > 0
        assert log_destroy == ["A finish"]
    # Unsure whether the GC will have reclaimed the Simulator instance yet, but processes *must* have been torn down.
    assert log_destroy[0:7] == ["A finish", "B EXIT", "B finish", "D EXIT", "D finish", "C EXIT", "C finish"]


def test_tagged_constructor():
    @tagged(TestTag.ALICE)
    def f():
        pass

    proc = Process(Simulator(), f, None)
    assert proc.has_tag(TestTag.ALICE)


def test_tag_in_place():
    # Standard usage
    @tagged(TestTag.ALICE)
    def f():
        pass

    assert getattr(f, GREENSIM_TAG_ATTRIBUTE) == (TestTag.ALICE,)

    def g():
        pass

    # Tag function in place
    assert getattr(tagged(TestTag.BOB)(g), GREENSIM_TAG_ATTRIBUTE) == (TestTag.BOB,)
    # SHow that this does not affect the original definition
    assert not hasattr(g, GREENSIM_TAG_ATTRIBUTE)


def test_tagged_constructor_multi():
    @tagged(TestTag.ALICE, TestTag.BOB)
    def f():
        pass

    proc = Process(Simulator(), f, None)
    assert proc.has_tag(TestTag.ALICE)
    assert proc.has_tag(TestTag.BOB)


def run_test_tagged_add(tagged_launcher, stop):
    when_last = 0.0

    def last_proc():
        nonlocal when_last
        when_last = now()
        assert Process.current().has_tag(TestTag.ALICE)

    sim = Simulator()
    sim.add(tagged_launcher, last_proc)
    sim.run()
    assert pytest.approx(stop) == when_last


def run_test_tagged_add_extra_tag(tagged_launcher, stop):
    when_last = 0.0

    @tagged(TestTag.BOB)
    def last_proc():
        nonlocal when_last
        when_last = now()
        assert Process.current().has_tag(TestTag.ALICE)
        assert Process.current().has_tag(TestTag.BOB)

    sim = Simulator()
    sim.add(tagged_launcher, last_proc)
    sim.run()
    assert pytest.approx(stop) == when_last


def test_tagged_process_add_vanilla():

    step = 25

    @tagged(TestTag.ALICE)
    def good_launch(last):
        advance(step)
        add(last)

    run_test_tagged_add(good_launch, step)
    run_test_tagged_add_extra_tag(good_launch, step)


def test_tagged_process_add_in():

    step = 25

    @tagged(TestTag.ALICE)
    def good_launch(last):
        advance(step)
        add_in(step, last)

    run_test_tagged_add(good_launch, 2 * step)
    run_test_tagged_add_extra_tag(good_launch, 2 * step)


def test_tagged_process_add_at():

    step = 25

    @tagged(TestTag.ALICE)
    def good_launch(last):
        advance(step)
        add_at(2 * step, last)

    run_test_tagged_add(good_launch, 2 * step)
    run_test_tagged_add_extra_tag(good_launch, 2 * step)
