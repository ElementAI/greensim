from random import Random

from greensim import Simulator, advance, add, Resource, now
from greensim.progress import track_progress


# Time convention: 1.0 == 1 minute


rnd = Random()
sim = Simulator()
resource = Resource(1)
RATE_ARRIVAL = 1.0 / 10.0
RATE_SERVICE = 1.0 / 6.0

num_served = 0
NUM_CLIENTS_STOP = 200000
times_service = []


def arrival():
    while True:
        advance(rnd.expovariate(RATE_ARRIVAL))
        add(service)

def service():
    global num_served
    time_start = now()
    with resource.using():
        advance(rnd.expovariate(RATE_SERVICE))
    times_service.append(now() - time_start)
    num_served += 1

sim.add(track_progress, lambda: [num_served], [NUM_CLIENTS_STOP], 0.025 * NUM_CLIENTS_STOP)
sim.add(arrival)
sim.run()

print()
print(f"Average service time: {sum(times_service)/len(times_service):4.1f} min")
print(f"Theoretic value:      {1.0 / (RATE_SERVICE - RATE_ARRIVAL):4.1f} min")
