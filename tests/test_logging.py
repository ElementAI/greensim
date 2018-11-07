import logging
from math import inf
from typing import cast

import pytest

from greensim import Simulator, advance, pause, local, add, Process, Queue, Signal, Resource, \
    enable_logging, disable_logging, Interrupt
from greensim.logging import Filter


class HandlerTestsGeneral(logging.Handler):

    def __init__(self):
        super().__init__(logging.DEBUG)
        self.log = []

    def handle(self, record):
        self.log.append(
            (
                record.levelno,
                record.sim_time,
                record.sim_process,
                record.msg
            )
        )


@pytest.fixture
def logger():
    disable_logging()
    logger = logging.getLogger(__name__)

    for h in [handler for handler in logger.handlers if isinstance(handler, HandlerTestsGeneral)]:
        logger.removeHandler(h)
    logger.addHandler(HandlerTestsGeneral())

    if len(logger.filters) == 0:
        logger.addFilter(Filter())
    logger.setLevel(logging.DEBUG)

    return logger


def test_sanity_logging(logger):
    logger.debug("a")
    logger.info("b")
    logger.warning("c")
    logger.error("d")
    logger.critical("e")
    assert [
        (level, -1.0, "", msg)
        for level, msg in [
            (logging.DEBUG, "a"),
            (logging.INFO, "b"),
            (logging.WARNING, "c"),
            (logging.ERROR, "d"),
            (logging.CRITICAL, "e")
        ]
    ] == logger.handlers[0].log


def test_log_additional_fields(logger):
    def ordeal(queue, signal, resource):
        logger.debug("debug")
        advance(10)
        logger.info("info")
        pause()
        logger.warning("warning")
        queue.join()
        logger.error("error", extra=dict(sim_process="the-process"))
        signal.wait()
        logger.critical("critical")
        resource.take()
        advance(10)
        logger.critical("finish", extra=dict(sim_time=1000.0))
        resource.release()

    def do_resume(proc_ordeal):
        advance(15)
        proc_ordeal.resume()

    def do_pop(queue):
        advance(30)
        queue.pop()

    def do_open(signal):
        advance(50)
        signal.turn_on()

    sim = Simulator()
    queue = Queue()
    signal = Signal().turn_off()
    resource = Resource(1)
    proc_ordeal = sim.add(ordeal, queue, signal, resource)
    name_ordeal = proc_ordeal.local.name
    sim.add(do_resume, proc_ordeal)
    sim.add(do_pop, queue)
    sim.add(do_open, signal)
    sim.run()

    assert [
        (logging.DEBUG, 0.0, name_ordeal, "debug"),
        (logging.INFO, 10.0, name_ordeal, "info"),
        (logging.WARNING, 15.0, name_ordeal, "warning"),
        (logging.ERROR, 30.0, "the-process", "error"),
        (logging.CRITICAL, 50.0, name_ordeal, "critical"),
        (logging.CRITICAL, 1000.0, name_ordeal, "finish")
    ] == logger.handlers[0].log


class HandlerTestsAutoLog(HandlerTestsGeneral):

    def __init__(self):
        super().__init__()
        self.log = []

    def handle(self, record):
        self.log.append(
            (
                record.levelno,
                record.sim_time,
                record.sim_process,
                record.sim_object,
                record.sim_name,
                record.sim_event,
                record.sim_params
            )
        )


@pytest.fixture
def auto_logger():
    enable_logging()
    logger = logging.getLogger("greensim")
    logger.setLevel(logging.INFO)

    handlers_test = [h for h in logger.handlers if isinstance(h, HandlerTestsAutoLog)]
    if len(handlers_test) == 0:
        logger.addHandler(HandlerTestsAutoLog())
    else:
        for h in handlers_test:
            cast(HandlerTestsAutoLog, h).log.clear()

    return logger


def check_log(auto_logger, *entries):
    for handler in auto_logger.handlers:
        if isinstance(handler, HandlerTestsAutoLog):
            assert list(entries) == handler.log
            break


def test_auto_log_process(auto_logger):
    proc_resumer = None
    auto_logger.setLevel(logging.DEBUG)

    def resumer(i_am_process):
        advance(10)
        i_am_process.resume()

    def proc():
        nonlocal proc_resumer
        local.name = "i-am-process"
        advance(10)
        proc_resumer = add(resumer, Process.current())
        pause()

    sim = Simulator()
    proc_proc = sim.add(proc)
    name_proc_orig = proc_proc.local.name
    sim.run()

    name_proc = proc_proc.local.name
    check_log(
        auto_logger,
        (logging.INFO, 0.0, "", "Simulator", sim.name, "add", dict(fn=proc, args=(), kwargs={})),
        (
            logging.DEBUG, 0.0, "", "Simulator", sim.name, "schedule",
            dict(delay=0.0, fn=proc_proc.switch, args=(), kwargs={}, counter=0)
        ),
        (logging.INFO, 0.0, "", "Simulator", sim.name, "run", dict(duration=inf)),
        (logging.DEBUG, 0.0, "", "Simulator", sim.name, "exec-event", dict(counter=0)),
        (logging.DEBUG, 0.0, name_proc_orig, "Process", name_proc_orig, "rename", dict(new="i-am-process")),
        (logging.INFO, 0.0, name_proc, "Process", name_proc, "advance", dict(delay=10.0)),
        (
            logging.DEBUG, 0.0, name_proc, "Simulator", sim.name, "schedule",
            dict(delay=10.0, fn=proc_proc.switch, args=(), kwargs={}, counter=1)
        ),
        (logging.DEBUG, 10.0, "", "Simulator", sim.name, "exec-event", dict(counter=1)),
        (logging.INFO, 10.0, name_proc, "Simulator", sim.name, "add", dict(fn=resumer, args=(proc_proc,), kwargs={})),
        (
            logging.DEBUG, 10.0, name_proc, "Simulator", sim.name, "schedule",
            dict(delay=0.0, fn=proc_resumer.switch, args=(proc_proc,), kwargs={}, counter=2)
        ),
        (logging.INFO, 10.0, name_proc, "Process", name_proc, "pause", {}),
        (logging.DEBUG, 10.0, "", "Simulator", sim.name, "exec-event", dict(counter=2)),
        (logging.INFO, 10.0, proc_resumer.local.name, "Process", proc_resumer.local.name, "advance", dict(delay=10.0)),
        (
            logging.DEBUG, 10.0, proc_resumer.local.name, "Simulator", sim.name, "schedule",
            dict(delay=10.0, fn=proc_resumer.switch, args=(), kwargs={}, counter=3)
        ),
        (logging.DEBUG, 20.0, "", "Simulator", sim.name, "exec-event", dict(counter=3)),
        (logging.INFO, 20.0, proc_resumer.local.name, "Process", name_proc, "resume", {}),
        (
            logging.DEBUG, 20.0, proc_resumer.local.name, "Simulator", sim.name, "schedule",
            dict(delay=0.0, fn=proc_proc.switch, args=(), kwargs={}, counter=4)
        ),
        (logging.INFO, 20.0, proc_resumer.local.name, "Process", proc_resumer.local.name, "die-finish", {}),
        (logging.DEBUG, 20.0, "", "Simulator", sim.name, "exec-event", dict(counter=4)),
        (logging.INFO, 20.0, name_proc, "Process", name_proc, "die-finish", {}),
        (logging.DEBUG, 20.0, "", "Simulator", sim.name, "out-of-events", {}),
        (logging.INFO, 20.0, "", "Simulator", sim.name, "stop", {})
    )


def test_auto_log_interrupt(auto_logger):
    proc_interrupter = None
    auto_logger.setLevel(logging.DEBUG)

    def interrupter(main):
        advance(15)
        main.interrupt()

    def proc():
        nonlocal proc_interrupter
        local.name = "main"
        proc_interrupter = add(interrupter, Process.current())
        advance(10)
        advance(10)

    sim = Simulator()
    proc_proc = sim.add(proc)
    name_proc_orig = proc_proc.local.name
    sim.run()

    name_proc = proc_proc.local.name
    check_log(
        auto_logger,
        (logging.INFO, 0.0, "", "Simulator", sim.name, "add", dict(fn=proc, args=(), kwargs={})),
        (
            logging.DEBUG, 0.0, "", "Simulator", sim.name, "schedule",
            dict(delay=0.0, fn=proc_proc.switch, args=(), kwargs={}, counter=0)
        ),
        (logging.INFO, 0.0, "", "Simulator", sim.name, "run", dict(duration=inf)),
        (logging.DEBUG, 0.0, "", "Simulator", sim.name, "exec-event", dict(counter=0)),
        (logging.DEBUG, 0.0, name_proc_orig, "Process", name_proc_orig, "rename", dict(new="main")),
        (
            logging.INFO, 0.0, name_proc, "Simulator", sim.name, "add",
            dict(fn=interrupter, args=(proc_proc,), kwargs={})
        ),
        (
            logging.DEBUG, 0.0, name_proc, "Simulator", sim.name, "schedule",
            dict(delay=0.0, fn=proc_interrupter.switch, args=(proc_proc,), kwargs={}, counter=1)
        ),
        (logging.INFO, 0.0, name_proc, "Process", name_proc, "advance", dict(delay=10.0)),
        (
            logging.DEBUG, 0.0, name_proc, "Simulator", sim.name, "schedule",
            dict(delay=10.0, fn=proc_proc.switch, args=(), kwargs={}, counter=2)
        ),
        (logging.DEBUG, 0.0, "", "Simulator", sim.name, "exec-event", dict(counter=1)),
        (
            logging.INFO, 0.0, proc_interrupter.local.name, "Process", proc_interrupter.local.name, "advance",
            dict(delay=15.0)
        ),
        (
            logging.DEBUG, 0.0, proc_interrupter.local.name, "Simulator", sim.name, "schedule",
            dict(delay=15.0, fn=proc_interrupter.switch, args=(), kwargs={}, counter=3)
        ),
        (logging.DEBUG, 10.0, "", "Simulator", sim.name, "exec-event", dict(counter=2)),
        (logging.INFO, 10.0, name_proc, "Process", name_proc, "advance", dict(delay=10.0)),
        (
            logging.DEBUG, 10.0, name_proc, "Simulator", sim.name, "schedule",
            dict(delay=10.0, fn=proc_proc.switch, args=(), kwargs={}, counter=4)
        ),
        (logging.DEBUG, 15.0, "", "Simulator", sim.name, "exec-event", dict(counter=3)),
        (logging.INFO, 15.0, proc_interrupter.local.name, "Process", name_proc, "interrupt", dict(type="Interrupt")),
        (
            logging.DEBUG, 15.0, proc_interrupter.local.name, "Simulator", sim.name, "schedule",
            dict(delay=0.0, fn=proc_proc.throw, args=(Interrupt(),), kwargs={}, counter=5)
        ),
        (logging.INFO, 15.0, proc_interrupter.local.name, "Process", proc_interrupter.local.name, "die-finish", {}),
        (logging.DEBUG, 15.0, "", "Simulator", sim.name, "exec-event", dict(counter=5)),
        (logging.DEBUG, 15.0, name_proc, "Simulator", sim.name, "cancel", dict(id=4)),
        (logging.INFO, 15.0, name_proc, "Process", name_proc, "die-interrupt", {}),
        (logging.DEBUG, 15.0, "", "Simulator", sim.name, "cancelled-event", dict(counter=4)),
        (logging.DEBUG, 15.0, "", "Simulator", sim.name, "out-of-events", {}),
        (logging.INFO, 15.0, "", "Simulator", sim.name, "stop", {})
    )


def test_auto_log_queue(auto_logger):
    def proc(q):
        local.name = "the-process"
        q.join()
        advance(100)

    sim = Simulator()
    queue = Queue(name="the-queue")
    sim.add(proc, queue)
    sim.run()
    queue.pop()
    sim.run(10)

    check_log(
        auto_logger,
        (logging.INFO, 0.0, "", "Simulator", sim.name, "add", dict(fn=proc, args=(queue,), kwargs={})),
        (logging.INFO, 0.0, "", "Simulator", sim.name, "run", dict(duration=inf)),
        (logging.INFO, 0.0, "the-process", "Queue", "the-queue", "join", {}),
        (logging.INFO, 0.0, "the-process", "Process", "the-process", "pause", {}),
        (logging.INFO, 0.0, "", "Simulator", sim.name, "stop", {}),
        (logging.INFO, -1.0, "", "Queue", "the-queue", "pop", dict(process="the-process")),
        (logging.INFO, -1.0, "", "Process", "the-process", "resume", {}),
        (logging.INFO, 0.0, "", "Simulator", sim.name, "run", dict(duration=10.0)),
        (logging.INFO, 0.0, "the-process", "Process", "the-process", "advance", dict(delay=100.0)),
        (logging.INFO, 10.0, "", "Simulator", sim.name, "stop", {})
    )


def test_auto_log_signal(auto_logger):
    def proc(sig):
        local.name = "the-process"
        sig.wait()
        advance(10)
        sig.wait()

    sim = Simulator()
    signal = Signal(name="the-signal").turn_off()
    sim.add(proc, signal)
    sim.run()
    signal.turn_on()
    sim.run()

    check_log(
        auto_logger,
        (logging.INFO, -1.0, "", "Signal", "the-signal", "turn-off", {}),
        (logging.INFO, 0.0, "", "Simulator", sim.name, "add", dict(fn=proc, args=(signal,), kwargs={})),
        (logging.INFO, 0.0, "", "Simulator", sim.name, "run", dict(duration=inf)),
        (logging.INFO, 0.0, "the-process", "Signal", "the-signal", "wait", {}),
        (logging.INFO, 0.0, "the-process", "Queue", "the-signal-queue", "join", {}),
        (logging.INFO, 0.0, "the-process", "Process", "the-process", "pause", {}),
        (logging.INFO, 0.0, "", "Simulator", sim.name, "stop", {}),
        (logging.INFO, -1.0, "", "Signal", "the-signal", "turn-on", {}),
        (logging.INFO, -1.0, "", "Queue", "the-signal-queue", "pop", dict(process="the-process")),
        (logging.INFO, -1.0, "", "Process", "the-process", "resume", {}),
        (logging.INFO, 0.0, "", "Simulator", sim.name, "run", dict(duration=inf)),
        (logging.INFO, 0.0, "the-process", "Process", "the-process", "advance", dict(delay=10.0)),
        (logging.INFO, 10.0, "the-process", "Signal", "the-signal", "wait", {}),
        (logging.INFO, 10.0, "the-process", "Process", "the-process", "die-finish", {}),
        (logging.INFO, 10.0, "", "Simulator", sim.name, "stop", {})
    )


def test_auto_log_resource(auto_logger):
    def proc(res, name, delay_before, delay_with):
        local.name = name
        advance(delay_before)
        with res.using():
            advance(delay_with)

    resource = Resource(1, name="the-resource")
    sim = Simulator(name="sim")
    sim.add(proc, resource, "alpha", 10, 50)
    sim.add(proc, resource, "beta", 30, 10)
    sim.run()

    check_log(
        auto_logger,
        (
            logging.INFO, 0.0, "", "Simulator", "sim", "add",
            dict(fn=proc, args=(resource, "alpha", 10.0, 50.0), kwargs={})
        ),
        (
            logging.INFO, 0.0, "", "Simulator", "sim", "add",
            dict(fn=proc, args=(resource, "beta", 30.0, 10.0), kwargs={})
        ),
        (logging.INFO, 0.0, "", "Simulator", "sim", "run", dict(duration=inf)),
        (logging.INFO, 0.0, "alpha", "Process", "alpha", "advance", dict(delay=10.0)),
        (logging.INFO, 0.0, "beta", "Process", "beta", "advance", dict(delay=30.0)),
        (logging.INFO, 10.0, "alpha", "Resource", "the-resource", "take", dict(num_instances=1, free=1)),
        (logging.INFO, 10.0, "alpha", "Process", "alpha", "advance", dict(delay=50.0)),
        (logging.INFO, 30.0, "beta", "Resource", "the-resource", "take", dict(num_instances=1, free=0)),
        (logging.INFO, 30.0, "beta", "Queue", "the-resource-queue", "join", {}),
        (logging.INFO, 30.0, "beta", "Process", "beta", "pause", {}),
        (logging.INFO, 60.0, "alpha", "Resource", "the-resource", "release", dict(num_instances=1, keeping=0, free=1)),
        (logging.INFO, 60.0, "alpha", "Queue", "the-resource-queue", "pop", dict(process="beta")),
        (logging.INFO, 60.0, "alpha", "Process", "beta", "resume", {}),
        (logging.INFO, 60.0, "alpha", "Process", "alpha", "die-finish", {}),
        (logging.INFO, 60.0, "beta", "Process", "beta", "advance", dict(delay=10.0)),
        (logging.INFO, 70.0, "beta", "Resource", "the-resource", "release", dict(num_instances=1, keeping=0, free=1)),
        (logging.INFO, 70.0, "beta", "Process", "beta", "die-finish", {}),
        (logging.INFO, 70.0, "", "Simulator", "sim", "stop", {})
    )


def test_auto_log_resource_take_again(auto_logger):
    def process(res):
        local.name = "proc"
        res.take(2)
        advance(10)
        res.take(3)
        advance(10)
        res.release(5)

    sim = Simulator(name="sim")
    resource = Resource(5, name="res")
    sim.add(process, resource)
    sim.run()

    check_log(
        auto_logger,
        (logging.INFO, 0.0, "", "Simulator", "sim", "add", dict(fn=process, args=(resource,), kwargs={})),
        (logging.INFO, 0.0, "", "Simulator", "sim", "run", dict(duration=inf)),
        (logging.INFO, 0.0, "proc", "Resource", "res", "take", dict(num_instances=2, free=5)),
        (logging.INFO, 0.0, "proc", "Process", "proc", "advance", dict(delay=10.0)),
        (logging.INFO, 10.0, "proc", "Resource", "res", "take", dict(num_instances=3, free=3)),
        (logging.WARNING, 10.0, "proc", "Resource", "res", "take-again", dict(already=2, more=3)),
        (logging.INFO, 10.0, "proc", "Process", "proc", "advance", dict(delay=10.0)),
        (logging.INFO, 20.0, "proc", "Resource", "res", "release", dict(num_instances=5, keeping=0, free=5)),
        (logging.INFO, 20.0, "proc", "Process", "proc", "die-finish", {}),
        (logging.INFO, 20.0, "", "Simulator", "sim", "stop", {})
    )
