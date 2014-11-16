import os
import sys

print(os.getcwd())
print(sys.path)

from . import app

app.run(debug=True)
