import logging
from math import inf
from typing import cast

import pytest

from greensim import Simulator, advance, pause, local, add, Process, Queue, Signal, Resource
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
        (logging.DEBUG, 20.0, "", "Simulator", sim.name, "exec-event", dict(counter=4)),
        (logging.DEBUG, 20.0, "", "Simulator", sim.name, "out-of-events", {}),
        (logging.INFO, 20.0, "", "Simulator", sim.name, "stop", {})
    )


def test_auto_log_queue(auto_logger):
    def proc(q):
        local.name = "the-process"
        q.join()
        advance(100)

def test_auto_log_change_level():
    pytest.fail()
