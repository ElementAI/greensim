import logging

import pytest

from greensim import Simulator, advance, pause, Queue, Signal, Resource
from greensim.logging import Filter


class HandlerForTests(logging.Handler):

    def __init__(self, level=logging.NOTSET):
        super().__init__(level)
        self.log = []
        self.setLevel(logging.DEBUG)

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

    for h in [handler for handler in logger.handlers if isinstance(handler, HandlerForTests)]:
        logger.removeHandler(h)
    logger.addHandler(HandlerForTests())

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
        (level, None, None, msg)
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


def test_auto_log_process():
    pytest.fail()


def test_auto_log_queue():
    pytest.fail()


def test_auto_log_signal():
    pytest.fail()


def test_auto_log_resource():
    pytest.fail()


def test_auto_log_higher_level():
    pytest.fail()


def test_auto_log_change_level():
    pytest.fail()
