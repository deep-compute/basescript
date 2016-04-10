from basescript import BaseScript

class CollectingStats(BaseScript):
    def run(self):
        # increment a counter by 1
        self.stats.incr("eventA")

        # increment a counter by 10
        self.stats.incr("eventB", 10)

        # decrement a counter by 1
        self.stats.decr("eventB")

        # set a gauge level
        self.stats.gauge("gaugeA", 99)

if __name__ == '__main__':
    CollectingStats().run()

