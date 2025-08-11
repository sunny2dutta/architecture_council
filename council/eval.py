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
        # online update of weights (very simple)
        self._online_calibrate()

    def mark_question_changed_design(self, decision_id: str, q: str):
        with sqlite3.connect(self.db_path) as con:
            cur = con.cursor()
            cur.execute("UPDATE questions SET changed_design=1 WHERE decision_id=? AND q=?", (decision_id, q))
            con.commit()

    def _online_calibrate(self, lr: float = 0.05):
        """Naive gradient step on a single scalar to bring average EDR closer to observed pain rate.
        This keeps things dependency-free. Extend with real calibration as needed."""
        with sqlite3.connect(self.db_path) as con:
            cur = con.cursor()
            cur.execute("SELECT edr FROM decisions")
            edrs = [r[0] for r in cur.fetchall()]
            cur.execute("SELECT pain FROM outcomes")
            pains = [r[0] for r in cur.fetchall()]
        if not edrs or not pains: 
            return
        avg_edr = sum(edrs)/len(edrs)
        avg_pain = sum(pains)/len(pains)
        scale = 1.0
        # store scale in weights file under key '_scale'
        w = self.load_weights()
        scale = w.get('_scale', 1.0)
        # loss = (scale*avg_edr - avg_pain)^2 -> dL/dscale = 2*(scale*avg_edr - avg_pain)*avg_edr
        grad = 2 * (scale*avg_edr - avg_pain) * avg_edr
        new_scale = max(0.5, min(1.5, scale - lr*grad))
        w['_scale'] = float(new_scale)
        self._save_weights(w)

    def scaled_edr(self, edr: float) -> float:
        w = self.load_weights()
        scale = w.get('_scale', 1.0)
        out = max(0.0, min(1.0, edr * scale))
        return out

    def question_value_index(self) -> float:
        with sqlite3.connect(self.db_path) as con:
            cur = con.cursor()
            cur.execute("SELECT SUM(changed_design), COUNT(*) FROM questions WHERE chosen=1")
            row = cur.fetchone()
        if not row or row[1] == 0: 
            return 0.0
        return float(row[0])/float(row[1])
