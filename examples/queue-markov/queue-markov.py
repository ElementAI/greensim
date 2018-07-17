from random import Random

from greensim import Simulator, advance, add, Resource, now
from greensim.progress import track_progress


# Time convention: 1.0 == 1 minute


# Initial setup.
rng = Random()
sim = Simulator()
resource = Resource(1)  # One server for the queue.

# Rates of customer arrival and service.
RATE_ARRIVAL = 1.0 / 10.0
RATE_SERVICE = 1.0 / 6.0

# Simulation runs until a certain number of customers have been served.
num_served = 0
NUM_CLIENTS_STOP = 200000

# Measure total time spent in the system (the *service time*).
times_service = []


# Arrival process: start the service of another customer according to a Poisson process. In other words, arrival time
# between customers is an exponential random variable of mean the inverse of the arrival rate. The Random class'
# expovariate takes the inverse of the intended mean as parameter.
def arrival():
    while True:
        advance(rng.expovariate(RATE_ARRIVAL))
        add(service)

sim.add(arrival)  # Add this process explicitly to bootstrap the system.


# Service process: the server's exclusive attention is modeled as a resource, which the customer must hold in order to
# be served. Take the service time measurement after the service is over.
def service():
    global num_served
    time_start = now()
    with resource.using():
        advance(rng.expovariate(RATE_SERVICE))
    times_service.append(now() - time_start)
    num_served += 1


# Add a progress tracker process based on measuring the number of customers served.
sim.add(track_progress, lambda: [num_served], [NUM_CLIENTS_STOP], 0.025 * NUM_CLIENTS_STOP)
sim.run()

print()
print(f"Average service time: {sum(times_service)/len(times_service):4.1f} min")
print(f"Theoretic value:      {1.0 / (RATE_SERVICE - RATE_ARRIVAL):4.1f} min")
