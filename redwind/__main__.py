import os
import sys

print(os.getcwd())
print(sys.path)

from . import manager

manager.run()
