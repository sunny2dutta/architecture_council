
import sqlite3, time, json, os, hashlib
from typing import Dict, Any, List, Optional

class Evaluator:
    """SQLite-backed telemetry + simple online learning for EDR weights."""
    def __init__(self, db_path: str, weights_path: str):
        self.db_path = db_path
        self.weights_path = weights_path
        os.makedirs(os.path.dirname(db_path), exist_ok=True)
        self._init_db()
        if not os.path.exists(weights_path):
            self._save_weights({"risk_mean":0.35,"scope":0.25,"workload":0.15,"compliance":0.10,"data_quality":0.10,"third_party":0.05})

    def _init_db(self):
        with sqlite3.connect(self.db_path) as con:
            cur = con.cursor()
            cur.execute("""
            CREATE TABLE IF NOT EXISTS decisions (
                id TEXT PRIMARY KEY,
                title TEXT, route TEXT, reason TEXT,
                edr REAL, ig_star REAL, created_at INTEGER,
                telemetry TEXT
            )""")
            cur.execute("""
            CREATE TABLE IF NOT EXISTS outcomes (
                decision_id TEXT, rework INTEGER, incidents INTEGER, predictability REAL,
                adopted INTEGER, pain INTEGER, created_at INTEGER,
                FOREIGN KEY(decision_id) REFERENCES decisions(id)
            )""")
            cur.execute("""
            CREATE TABLE IF NOT EXISTS questions (
                decision_id TEXT, q TEXT, chosen INTEGER, changed_design INTEGER
            )""")
            con.commit()

    def _save_weights(self, w: Dict[str, float]):
        with open(self.weights_path, 'w') as f:
            json.dump(w, f, indent=2)

    def load_weights(self) -> Dict[str, float]:
        with open(self.weights_path, 'r') as f:
            return json.load(f)

    def log_decision(self, title: str, route: str, reason: str, edr: float, ig_star: float, telemetry: Dict[str, Any]) -> str:
        decision_id = hashlib.sha1((title + str(time.time())).encode()).hexdigest()[:16]
        with sqlite3.connect(self.db_path) as con:
            cur = con.cursor()
            cur.execute("INSERT INTO decisions VALUES (?,?,?,?,?,?,?,?)",
                        (decision_id, title, route, reason, edr, ig_star, int(time.time()), json.dumps(telemetry)))
            con.commit()
        return decision_id

    def log_questions(self, decision_id: str, questions: List[str], chosen_flags: List[int]):
        with sqlite3.connect(self.db_path) as con:
            cur = con.cursor()
            for q, c in zip(questions, chosen_flags):
                cur.execute("INSERT INTO questions VALUES (?,?,?,?)", (decision_id, q, c, 0))
            con.commit()

    def log_outcome(self, decision_id: str, rework: int, incidents: int, predictability: float, adopted: int):
        pain = 1 if (rework or incidents) else 0
        with sqlite3.connect(self.db_path) as con:
            cur = con.cursor()
            cur.execute("INSERT INTO outcomes VALUES (?,?,?,?,?,?,?)",
                        (decision_id, rework, incidents, predictability, adopted, pain, int(time.time())))
            con.commit()

    def mark_question_changed_design(self, decision_id: str, q: str):
        with sqlite3.connect(self.db_path) as con:
            cur = con.cursor()
            cur.execute("UPDATE questions SET changed_design=1 WHERE decision_id=? AND q=?", (decision_id, q))
            con.commit()

    # Calibration left to prior minimal implementation for simplicity
