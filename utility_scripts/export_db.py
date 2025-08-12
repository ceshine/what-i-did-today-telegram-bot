"""Firestore Database Exporter

This module exports all documents from a Google Cloud Firestore database to local JSON files.
Each collection in the database is exported to its own subdirectory, with each document
saved as a separate JSON file named after the document ID.

Requirements:
- Valid Google Cloud service account credentials (keyfile.json)

The exported data is saved in a 'db_export' directory in the current working directory.

Example usage: `uv run python -m utility_scripts.export_db`
"""

import os
import json
from google.cloud import firestore

os.environ["GOOGLE_APPLICATION_CREDENTIALS"] = "keyfile.json"

db = firestore.Client()

if not os.path.exists("db_export"):
    os.makedirs("db_export")

for collection in db.collections():
    collection_path = os.path.join("db_export", collection.id)
    if not os.path.exists(collection_path):
        os.makedirs(collection_path)
    docs = list(collection.stream())
    print(f"Found {len(docs)} documents in {collection.id}")
    for doc in docs:
        file_path = os.path.join(collection_path, f"{doc.id}.json")
        with open(file_path, "w") as f:
            json.dump(doc.to_dict(), f, indent=4)

print("Export complete.")
