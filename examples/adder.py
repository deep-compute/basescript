from basescript import BaseScript

class Adder(BaseScript):
    # The following specifies the script description so that it be used
    # as a part of the usage doc when --help option is used during running.
    DESC = 'Adds numbers'

    def init(self):
        '''
        We can put whatever script initialization we need for our script
        over here. This is preferred to overriding __init__
        '''
        self.a = 10
        self.b = 20

    def define_args(self, parser):
        parser.add_argument('c', type=int, help='Number to add')

    def run(self):
        self.log.info("Starting run of script ...")

        print self.a + self.b + self.args.c

        self.log.info("Script is done")

if __name__ == '__main__':
    Adder().start()
