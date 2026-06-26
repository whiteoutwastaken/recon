import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from database import DatabaseManager

db = DatabaseManager()
db.execute("DELETE FROM events")
print("All events deleted.")
db.close()
