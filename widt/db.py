import os

from google.cloud import firestore

os.environ["GOOGLE_APPLICATION_CREDENTIALS"] = "keyfile.json"

if os.environ.get("TEST_MODE"):
    DB = None
else:
    DB = firestore.Client()
