from sim import Process


class PoissonProcess(Process):

    def __init__(self, simulator, max_samples=None):
        super().__init__(simulator)
        self.rand = random.Random()
        self.times = []
        self.delays = []
        self.max_samples = max_samples
        self.count = 0

    def name(self):
        return super().name() + '_1'

    def run(self):
        while True:
            if self.max_samples and self.count > self.max_samples:
                self.log(f"Reached max_samples of {self.max_samples}.")
                return

            self.times.append(self.now())

            delay = self.rand.expovariate(0.2)
            self.delays.append(delay)

            self.log(f"0, delay={delay}")
            yield delay
            self.log(f"1")

            self.count += 1

    def on_end(self):
        self.log(f"on_end")

