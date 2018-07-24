from logging import debug, info, getLogger, basicConfig, INFO
from statistics import mean, stdev
from time import time, localtime, strftime

from greensim import Simulator, Process, advance, add, now, local, Queue, Signal, Resource
import greensim.logging as gs_logging
from greensim.random import constant, project_int, bounded, uniform, expo, normal, distribution
from greensim.progress import track_progress, sim_time


logger_root = getLogger()
logger_root.addFilter(gs_logging.Filter())
basicConfig(
    filename=strftime("checkpoint_%Y-%m-%d_%H-%M-%S.log", localtime(time())),
    format="%(levelname)5s | %(sim_time)12.1f -- %(message)s",
    level=INFO
)


# Time convention: 1.0 == 1 minute
MINUTE = 1.0
SECOND = MINUTE / 60.0
HOUR = 60.0 * MINUTE
DAY = 24.0 * HOUR

traveler_priority = distribution({0: 1, 1: 99})
traveler_preparation = bounded(normal(45 * SECOND, 15 * SECOND), lower=5 * SECOND)
traveler_processing_type = distribution({"scan": 80, "patdown": 20})
traveler_processing_time = {
    "scan": constant(15.0 * SECOND),
    "patdown": bounded(normal(40 * SECOND, 5.0 * SECOND), lower=15 * SECOND)
}

agent_time_work = bounded(normal(2 * HOUR, 3 * MINUTE), lower=100 * MINUTE)
agent_time_break = bounded(normal(10 * MINUTE, 2 * MINUTE), lower=6 * MINUTE, upper=20 * MINUTE)

interval_lone_departure = expo(5 * MINUTE)
interval_layover = expo(45 * MINUTE)
num_passengers_layover = project_int(uniform(20, 51))

NUM_BELTS = 4
LIMIT_TRAVELERS_BELT_AVAILABLE = 5
NUM_TRAVELERS_PER_BATCH = 5
PERIOD = 10 * DAY


class LuggageBodyScanner(object):

    def __init__(self, sim: Simulator, num: str) -> None:
        self.num = num
        self._num_standing = 0
        self._moment_empty = sim.now()
        self._time_empty = 0
        self._travelers_waiting = Queue()
        self._traveler_ready = Signal()
        self._agents_working = Signal()

        sim.add(self._work_then_break)
        for name in ["alpha", "beta"]:
            sim.add(self._agent_accepting_travelers, name)

    def _work_then_break(self) -> None:
        while True:
            advance(next(agent_time_work))
            info(f"Agents on belt {self.num} going on BREAK")
            self._agents_working.turn_off()
            advance(next(agent_time_break))
            info(f"Agents on belt {self.num} coming back to work")
            self._agents_working.turn_on()

    def _agent_accepting_travelers(self, name) -> None:
        agent = Resource(1)  # Models how the agent is busy processing a traveler.
        while True:
            # Are we on break yet? That coffee won't drink itself.
            self._agents_working.wait()
            info(f"Agent {name}/{self.num} ready")

            # Is anybody in there?
            if self._travelers_waiting.is_empty():
                debug(f"Agent {name}/{self.num} waiting for travelers")
                self._traveler_ready.turn_off().wait()
                continue  # Check back if we've gone on break while waiting for somebody.

            # Accept the next traveler traversing the checkpoint.
            traveler_next = self._travelers_waiting.peek()
            debug(f"Agent {name}/{self.num} about to process traveler {traveler_next.local.name}")
            traveler_next.local.agent = agent
            traveler_next.local.agent_name = f"{name}/{self.num}"
            self._travelers_waiting.pop()

            # Allow the next traveler to "use" this agent, so we may then wait until it's done traversing.
            advance(0.0)
            debug(f"Agent {name}/{self.num} doing the processing.")
            with agent.using():
                debug(f"Agent {name}/{self.num} done with the processing.")

    @property
    def num_standing(self) -> int:
        return self._num_standing

    @property
    def time_empty(self) -> float:
        return self._time_empty

    def traverse(self) -> None:
        # Invoked by crossing passengers in order to get through their luggage and body scan.
        me = local.name
        if self._num_standing == 0:
            period_empty = now() - self._moment_empty
            self._time_empty += period_empty
            debug(f"Belt {self.num} -- Empty period: {period_empty:.1f} -- Time empty: {self.time_empty:.1f}")
        self._num_standing += 1
        info(f"Traveler {me} entering belt {self.num}; now {self.num_standing} travelers here")

        # Prepare for check.
        advance(next(traveler_preparation))

        # Wait for an agent to beckon.
        info(f"Traveler {me} (belt {self.num}) prepared and ready for processing")
        self._traveler_ready.turn_on()
        self._travelers_waiting.join()

        with local.agent.using():  # Make agent busy with me.
            # Administer scan or patdown.
            agent_name = Process.current().local.agent_name
            processing_type = next(traveler_processing_type)
            info(f"Traveler {me} processed by agent {agent_name}: {processing_type}")
            advance(next(traveler_processing_time[processing_type]))

        info(f"Traveler {me} (belt {self.num}) buckling back up")
        advance(next(traveler_preparation))

        self._num_standing -= 1
        if self._num_standing == 0:
            debug(f"Belt {self.num} now empty")
            self._moment_empty = now()


def order_traveler(counter: int) -> int:
    return counter + local.priority * 1000000000


# Simulation setup.
sim = Simulator()
main_queue = Queue(order_traveler)
traveler_enters_main_queue = Signal()
traveler_exits_belt = Signal()
belts = [LuggageBodyScanner(sim, n + 1) for n in range(NUM_BELTS)]

log_time_through_checkpoint = []
log_main_queue_empty = []
traveler_name = 0


# Journey of a traveler (hahaha) through the checkpoint.
def traveler():
    global traveler_name
    traveler_name += 1
    name = traveler_name

    local.name = name
    local.priority = next(traveler_priority)
    time_arrival = now()

    # Kick the agent awake so he gets me a belt.
    info(f"Traveler {name} entering checkpoint's main queue")
    traveler_enters_main_queue.turn_on()
    main_queue.join()

    # Got a belt -- traverse it.
    local.belt.traverse()

    # Leaving the belt -- kick the agent awake in case this frees up the progress of some passengers stuck in the main
    # queue.
    info(f"Traveler {name} coming out of checkpoint")
    traveler_exits_belt.turn_on()
    log_time_through_checkpoint.append(now() - time_arrival)


# Process injecting departing travelers into the system.
def lone_departures():
    while True:
        advance(next(interval_lone_departure))
        info(f"Lone departing traveler")
        add(traveler)


sim.add(lone_departures)


# Process injecting layover planes into the system.
def layovers():
    while True:
        advance(next(interval_layover))
        num_passengers = next(num_passengers_layover)
        info(f"Layover plane with {num_passengers}")
        for n in range(num_passengers):
            add(traveler)


sim.add(layovers)


# Management of the main queue for assigning passengers to belts.
def agent_main_queue():
    while True:
        if main_queue.is_empty():
            debug(f"MQA waiting for travelers")
            traveler_enters_main_queue.turn_off().wait()
        info(f"MQA ready")

        # Is there a belt where 10 people or less are standing?
        while True:
            debug("MQA checks belts -- " + " ".join(f"{b.num}:{b.num_standing}" for b in belts))
            belts_available = [belt for belt in belts if belt.num_standing <= LIMIT_TRAVELERS_BELT_AVAILABLE]
            if len(belts_available) > 0:
                break
            # No belt available? Wait for some passengers to leave.
            debug(f"MQA waiting for a belt to free up")
            traveler_exits_belt.turn_off().wait()

        # Assign the least populated suitable belt to the next 5 passengers.
        belt_best = min(belts_available, key=lambda b: b.num_standing)
        for _ in range(NUM_TRAVELERS_PER_BATCH):
            if main_queue.is_empty():
                break
            traveler_next = main_queue.peek()
            info(f"MQA ushers traveler {traveler_next.local.name} towards belt {belt_best.num}")
            traveler_next.local.belt = belt_best
            main_queue.pop()

        # Let travelers walk over to their belt before addressing the next batch.
        advance(0.0)


sim.add(agent_main_queue)


# Run the simulation.
sim.add(track_progress, sim_time, [PERIOD], 1.0 * HOUR)
sim.run()

# Statistics report.
print()
print("Statistics:")
print()
print("Number of travelers")
print(f"    Entered:                     {traveler_name}")
print(f"    Processed:                   {len(log_time_through_checkpoint)}")
print()
print("Time spent in checkpoint")
print(f"    Mean:                      {mean(log_time_through_checkpoint):5.1f} min")
print(f"    Std deviation:             {stdev(log_time_through_checkpoint):5.1f} min")
print()
print("Fraction of time running empty:")
for belt in belts:
    print(f"    Belt {belt.num}:                      {100.0 * belt.time_empty / PERIOD:4.1f}%")
