import os

from google.cloud import firestore

os.environ["GOOGLE_APPLICATION_CREDENTIALS"] = "keyfile.json"
DB = firestore.Client()
