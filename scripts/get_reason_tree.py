#!/usr/bin/env python
import sys
import sqlite3

db_path = sys.argv[1]

conn = sqlite3.connect(db_path)

cur = conn.cursor()

causes = cur.execute("SELECT DISTINCT FireCause FROM fires;").fetchall()

for cause in causes:
    cause = cause[0]
    general_causes = cur.execute(f"SELECT DISTINCT FireCauseGeneral from fires where FireCause ='{cause}';").fetchall()
    for general_cause in general_causes:
        general_cause = general_cause[0]
        specific_causes = cur.execute(f"SELECT DISTINCT FireCauseSpecific from fires where FireCause = '{cause}' and FireCauseGeneral ='{general_cause}';").fetchall()
        for specific_cause in specific_causes:
            print(f"{cause} -> {general_cause} -> {specific_cause[0]}")

    # print(cause)
    # print(general_causes)
