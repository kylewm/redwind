import os
import sys

print(os.getcwd())
print(sys.path)

from . import create_app

app.run(debug=True)
