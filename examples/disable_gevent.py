from gevent import monkey; monkey.patch_all = lambda: None

from basescript import BaseScript

class MyScript(BaseScript):
    def run(self):
        # do something here including using
        # `multiprocessing` module
        pass

if __name__ == '__main__':
    MyScript().run()

