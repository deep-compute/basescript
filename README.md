# Base Script

Python is an excellent language that makes writing scripts very straightforward. Over the course of writing many scripts, we realized that we were doing some things over and over like creating a logger and accepting command line arguments. Base script is a very simple abstraction that takes care of setting up logging and other basics so you can focus on your application specific logic.

Here are some facilities that Base Script offers:
- Logging
- Accepting command-line arguments using argparse

## Installation

``` bash
pip install basescript
```

## Usage

Here is a simple example to get started

### Hello World

helloworld.py
```python
from basescript import BaseScript

class HelloWorld(BaseScript):
    def run(self):
        print "Hello world"

if __name__ == '__main__':
    HelloWorld().start()
```

> NOTE: all examples showcased here are available under the `examples` directory

Run the above by doing:

```bash
python helloworld.py run
```

Run script with log level set to DEBUG

```bash
python helloworld.py --log-level DEBUG run
```

Run script with custom log file

```bash
python helloworld.py --log-level DEBUG --log mylog run
```

### Command line args, Using the logger
The following is a more involved example

adder.py
```python
from basescript import BaseScript

class Adder(BaseScript):
    # The following specifies the script description so that it be used
    # as a part of the usage doc when --help option is used during running.
    DESC = 'Adds numbers'

    def __init__(self):
        super(Adder, self).__init__()
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
```

Run the script as follows and observe the usage information shown. Note how the
description appears along with the `c` argument.
```bash
python adder.py --help
usage: adder.py [-h] [--name NAME] [--log LOG] [--log-level LOG_LEVEL]
                [--quiet]
                {run} ...

Adds numbers

optional arguments:
  -h, --help            show this help message and exit
  --name NAME           Name to identify this instance
  --log LOG             Name of log file
  --log-level LOG_LEVEL
                        Logging level as picked from the logging module
  --quiet

commands:
  {run}
```
```bash
python adder.py run --help
usage: adder.py run [-h] c

positional arguments:
  c           Number to add

optional arguments:
  -h, --help  show this help message and exit
```

Run the script now to see the intended output
```shell
python adder.py run 30
60
```

Run the same with info and higher level logs enabled
```bash
python adder.py --log-level INFO 30
2016-04-10 13:48:27,356 INFO Starting run of script ...
60
2016-04-10 13:48:27,356 INFO Script is done
```

`--log-level` accepts all the values shown at
https://docs.python.org/2/library/logging.html#logging-levels.

`log` is a log object created using python's standard `logging` module. You can
read more about it at https://docs.python.org/2/library/logging.html.
