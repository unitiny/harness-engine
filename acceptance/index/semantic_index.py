"""
Semantic index for acceptance scenarios using HSF (Hybrid Scoring Function).

HSF(query, doc) = alpha * TF-IDF(query, doc) + beta * SubstringBoost(query, doc)

This enables fast semantic search over scenario names, descriptions,
and tags without requiring vector embeddings.
"""

import sqlite3
import json
import math
import re
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional, Tuple


@dataclass
class IndexedScenario:
    """A scenario stored in the index."""

    id: int
    name: str
    description: str
    feature: str
    tags: List[str]
    source_path: str
    importance_score: float = 0.5
    access_count: int = 0
    last_access: Optional[str] = None


@dataclass
class SearchResult:
    """A search result with HSF score."""

    scenario: IndexedScenario
    score: float
    score_components: Dict[str, float] = field(default_factory=dict)


class ScenarioIndex:
    """
    SQLite-based semantic index for acceptance scenarios.

    Uses HSF (Hybrid Scoring Function) from RAGdb research:
    HSF(q, d) = alpha * TF-IDF(q, d) + beta * SubstringBoost(q, d)
    """

    # Tokenisation pattern: Chinese characters, English words, numbers
    _TOKEN_RE = re.compile(r"[一-鿿]|[a-zA-Z]+|[0-9]+")

    def __init__(
        self,
        db_path: str = ":memory:",
        hsf_alpha: float = 0.6,
        hsf_beta: float = 0.4,
    ):
        self._db_path = db_path
        self._alpha = hsf_alpha
        self._beta = hsf_beta
        self._conn = sqlite3.connect(db_path)
        self._conn.row_factory = sqlite3.Row
        self._conn.execute("PRAGMA foreign_keys = ON")
        self._init_schema()

    # ------------------------------------------------------------------
    # Schema initialisation
    # ------------------------------------------------------------------

    def _init_schema(self):
        """Initialize database schema from schema.sql or inline fallback."""
        schema_path = Path(__file__).parent / "schema.sql"
        try:
            if schema_path.exists():
                sql = schema_path.read_text(encoding="utf-8")
                # Remove PRAGMA statements that fail in executescript
                import re
                sql = re.sub(r'PRAGMA\s+[^;]+;', '', sql)
                self._conn.executescript(sql)
            else:
                raise RuntimeError("No schema file")
        except Exception:
            # Inline fallback schema
            self._conn.executescript(
                """
                CREATE TABLE IF NOT EXISTS scenarios (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    name TEXT NOT NULL,
                    description TEXT DEFAULT '',
                    feature TEXT DEFAULT '',
                    tags TEXT DEFAULT '[]',
                    source_path TEXT DEFAULT '',
                    status TEXT DEFAULT 'active',
                    importance_score REAL DEFAULT 0.5,
                    access_count INTEGER DEFAULT 0,
                    last_access TEXT,
                    created_at TEXT DEFAULT (datetime('now')),
                    updated_at TEXT DEFAULT (datetime('now'))
                );
                CREATE TABLE IF NOT EXISTS terms (
                    term TEXT NOT NULL,
                    scenario_id INTEGER NOT NULL,
                    tf REAL DEFAULT 0,
                    idf REAL DEFAULT 0,
                    PRIMARY KEY (term, scenario_id)
                );
                CREATE TABLE IF NOT EXISTS scenario_stats (
                    total_scenarios INTEGER DEFAULT 0,
                    avg_description_length REAL DEFAULT 0
                );
                CREATE TABLE IF NOT EXISTS execution_results (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    scenario_name TEXT NOT NULL,
                    passed INTEGER DEFAULT 0,
                    step_results TEXT DEFAULT '{}',
                    duration_ms REAL DEFAULT 0,
                    timestamp TEXT DEFAULT (datetime('now'))
                );
                CREATE TABLE IF NOT EXISTS config (
                    key TEXT PRIMARY KEY,
                    value TEXT,
                    description TEXT
                );
                CREATE TABLE IF NOT EXISTS memory_votes (
                    scenario_id INTEGER,
                    agent_id TEXT,
                    vote INTEGER DEFAULT 3,
                    confidence_val REAL DEFAULT 0.5,
                    reason TEXT DEFAULT '',
                    timestamp TEXT DEFAULT (datetime('now')),
                    PRIMARY KEY (scenario_id, agent_id)
                );
                CREATE INDEX IF NOT EXISTS idx_scenarios_name ON scenarios(name);
                CREATE INDEX IF NOT EXISTS idx_scenarios_feature ON scenarios(feature);
                CREATE INDEX IF NOT EXISTS idx_scenarios_status ON scenarios(status);
                CREATE INDEX IF NOT EXISTS idx_terms_term ON terms(term);
                INSERT OR IGNORE INTO scenario_stats VALUES (0, 0);
                INSERT OR IGNORE INTO config VALUES ('hsf_alpha', '0.6', 'TF-IDF weight');
                INSERT OR IGNORE INTO config VALUES ('hsf_beta', '0.4', 'Substring boost weight');
                """
            )
        self._conn.commit()

    # ------------------------------------------------------------------
    # Tokenisation helpers
    # ------------------------------------------------------------------

    @classmethod
    def _tokenize(cls, text: str) -> List[str]:
        """Tokenize text into Chinese chars, English words, and numbers."""
        return cls._TOKEN_RE.findall(text.lower())

    # ------------------------------------------------------------------
    # Indexing
    # ------------------------------------------------------------------

    def add_scenario(
        self,
        name: str,
        description: str = "",
        feature: str = "",
        tags: List[str] = None,
        source_path: str = "",
        importance_score: float = 0.5,
    ) -> int:
        """Add a scenario to the index.  Returns the scenario ID."""
        tags_json = json.dumps(tags or [], ensure_ascii=False)
        cursor = self._conn.execute(
            "INSERT INTO scenarios "
            "(name, description, feature, tags, source_path, importance_score) "
            "VALUES (?, ?, ?, ?, ?, ?)",
            (name, description, feature, tags_json, source_path, importance_score),
        )
        scenario_id = cursor.lastrowid

        # Build text corpus from all relevant fields
        text = f"{name} {description} {feature} {' '.join(tags or [])}"
        self._index_terms(scenario_id, text)

        self._conn.commit()
        return scenario_id

    def remove_scenario(self, scenario_id: int) -> bool:
        """Remove a scenario (and its terms) from the index."""
        cursor = self._conn.execute(
            "DELETE FROM scenarios WHERE id = ?", (scenario_id,)
        )
        self._conn.commit()
        return cursor.rowcount > 0

    def _index_terms(self, scenario_id: int, text: str):
        """Tokenize text and compute TF for every unique token, then store."""
        tokens = self._tokenize(text)
        if not tokens:
            return

        # Term frequency
        token_counts: Dict[str, int] = {}
        for t in tokens:
            token_counts[t] = token_counts.get(t, 0) + 1

        total_tokens = len(tokens)
        for term, count in token_counts.items():
            tf = count / total_tokens
            self._conn.execute(
                "INSERT OR REPLACE INTO terms (term, scenario_id, tf) VALUES (?, ?, ?)",
                (term, scenario_id, tf),
            )

        # Recompute IDF across all terms
        self._update_idf()

    def _update_idf(self):
        """Recompute IDF for every term in the index.

        Smoothed IDF formula:  idf = log((N+1)/(df+1)) + 1
        where N = total active scenarios, df = document frequency of the term.
        """
        total = self._conn.execute(
            "SELECT COUNT(*) FROM scenarios WHERE status='active'"
        ).fetchone()[0]
        if total == 0:
            return

        rows = self._conn.execute(
            "SELECT term, COUNT(DISTINCT scenario_id) AS df FROM terms GROUP BY term"
        ).fetchall()

        for row in rows:
            idf = math.log((total + 1) / (row["df"] + 1)) + 1
            self._conn.execute(
                "UPDATE terms SET idf = ? WHERE term = ?", (idf, row["term"])
            )

    # ------------------------------------------------------------------
    # Search -- HSF
    # ------------------------------------------------------------------

    def search(
        self,
        query: str,
        limit: int = 10,
        feature: str = None,
    ) -> List[SearchResult]:
        """Search scenarios using HSF.

        HSF(query, doc) = alpha * TF-IDF(query, doc) + beta * SubstringBoost(query, doc)
        """
        query_tokens = self._tokenize(query)
        if not query_tokens:
            return []

        # Retrieve active scenarios (optionally filtered by feature)
        sql = "SELECT * FROM scenarios WHERE status='active'"
        params: list = []
        if feature:
            sql += " AND feature=?"
            params.append(feature)
        scenarios = self._conn.execute(sql, params).fetchall()

        query_lower = query.lower()
        results: List[SearchResult] = []

        for row in scenarios:
            scenario = IndexedScenario(
                id=row["id"],
                name=row["name"],
                description=row["description"],
                feature=row["feature"],
                tags=json.loads(row["tags"]),
                source_path=row["source_path"],
                importance_score=row["importance_score"],
                access_count=row["access_count"],
                last_access=row["last_access"],
            )

            # TF-IDF component
            tfidf = self._compute_tfidf(query_tokens, scenario.id)

            # Substring-boost component
            full_text = (
                f"{scenario.name} {scenario.description} {scenario.feature}"
            )
            substring = self._compute_substring_boost(query_lower, full_text.lower())

            # Combine via HSF
            hsf = self._alpha * tfidf + self._beta * substring

            if hsf > 0:
                results.append(
                    SearchResult(
                        scenario=scenario,
                        score=hsf,
                        score_components={"tfidf": tfidf, "substring": substring},
                    )
                )

        results.sort(key=lambda r: r.score, reverse=True)
        return results[:limit]

    def _compute_tfidf(self, query_tokens: List[str], scenario_id: int) -> float:
        """Compute mean TF-IDF score of query tokens against a scenario."""
        if not query_tokens:
            return 0.0

        score = 0.0
        for token in query_tokens:
            row = self._conn.execute(
                "SELECT tf, idf FROM terms WHERE term=? AND scenario_id=?",
                (token, scenario_id),
            ).fetchone()
            if row:
                score += row["tf"] * row["idf"]

        return score / len(query_tokens)

    def _compute_substring_boost(self, query: str, document: str) -> float:
        """Compute substring boost: exact-match occurrences normalised by query length."""
        if not query or not document:
            return 0.0

        count = document.count(query)
        if count == 0:
            # Fall back to individual token matches
            tokens = query.split()
            for t in tokens:
                if t in document:
                    count += 1
        return min(count / max(len(query.split()), 1), 1.0)

    # ------------------------------------------------------------------
    # Execution tracking
    # ------------------------------------------------------------------

    def record_execution(
        self,
        scenario_name: str,
        passed: bool,
        step_results: dict = None,
        duration_ms: float = 0,
    ):
        """Record an execution result for a scenario."""
        self._conn.execute(
            "INSERT INTO execution_results "
            "(scenario_name, passed, step_results, duration_ms) "
            "VALUES (?, ?, ?, ?)",
            (
                scenario_name,
                1 if passed else 0,
                json.dumps(step_results or {}),
                duration_ms,
            ),
        )
        self._conn.commit()

    def get_execution_history(
        self, scenario_name: str, limit: int = 20
    ) -> List[Dict]:
        """Return recent execution results for a scenario."""
        rows = self._conn.execute(
            "SELECT * FROM execution_results WHERE scenario_name=? "
            "ORDER BY timestamp DESC LIMIT ?",
            (scenario_name, limit),
        ).fetchall()
        return [
            {
                "id": r["id"],
                "passed": bool(r["passed"]),
                "step_results": json.loads(r["step_results"]),
                "duration_ms": r["duration_ms"],
                "timestamp": r["timestamp"],
            }
            for r in rows
        ]

    # ------------------------------------------------------------------
    # Co-Forgetting (memory pruning)
    # ------------------------------------------------------------------

    def vote_for_memory(
        self,
        scenario_id: int,
        agent_id: str,
        vote: int,
        confidence: float = 0.5,
        reason: str = "",
    ):
        """Record a vote for memory pruning.

        vote: 1 = RETAIN, 2 = PRUNE, 3 = ABSTAIN
        """
        self._conn.execute(
            "INSERT OR REPLACE INTO memory_votes "
            "(scenario_id, agent_id, vote, confidence_val, reason) "
            "VALUES (?, ?, ?, ?, ?)",
            (scenario_id, agent_id, vote, confidence, reason),
        )
        self._conn.commit()

    def check_prune_consensus(
        self, scenario_id: int, threshold: float = 0.67
    ) -> bool:
        """Check if enough agents voted to prune (consensus >= threshold)."""
        votes = self._conn.execute(
            "SELECT vote FROM memory_votes WHERE scenario_id=?", (scenario_id,)
        ).fetchall()
        if not votes:
            return False
        total = len(votes)
        prune_count = sum(1 for v in votes if v["vote"] == 2)
        return (prune_count / total) >= threshold

    def auto_prune(
        self,
        importance_threshold: float = 0.3,
        access_threshold: int = 2,
    ) -> List[int]:
        """Find and prune low-importance, rarely-accessed scenarios.

        Only prunes scenarios that also have consensus from memory_votes.
        Returns list of pruned scenario IDs.
        """
        candidates = self._conn.execute(
            "SELECT id FROM scenarios "
            "WHERE importance_score < ? AND access_count < ? AND status='active'",
            (importance_threshold, access_threshold),
        ).fetchall()

        pruned: List[int] = []
        for row in candidates:
            if self.check_prune_consensus(row["id"]):
                self._conn.execute(
                    "UPDATE scenarios SET status='archived' WHERE id=?",
                    (row["id"],),
                )
                pruned.append(row["id"])

        if pruned:
            self._conn.commit()
        return pruned

    # ------------------------------------------------------------------
    # Access tracking
    # ------------------------------------------------------------------

    def access_scenario(self, scenario_id: int):
        """Increment access count and update last_access timestamp."""
        self._conn.execute(
            "UPDATE scenarios "
            "SET access_count = access_count + 1, "
            "    last_access = datetime('now') "
            "WHERE id=?",
            (scenario_id,),
        )
        self._conn.commit()

    # ------------------------------------------------------------------
    # Statistics
    # ------------------------------------------------------------------

    def get_stats(self) -> Dict:
        """Return aggregate index statistics."""
        total = self._conn.execute(
            "SELECT COUNT(*) FROM scenarios WHERE status='active'"
        ).fetchone()[0]
        by_feature = dict(
            self._conn.execute(
                "SELECT feature, COUNT(*) FROM scenarios "
                "WHERE status='active' GROUP BY feature"
            ).fetchall()
        )
        exec_count = self._conn.execute(
            "SELECT COUNT(*) FROM execution_results"
        ).fetchone()[0]
        archived = self._conn.execute(
            "SELECT COUNT(*) FROM scenarios WHERE status='archived'"
        ).fetchone()[0]
        return {
            "total_scenarios": total,
            "archived_scenarios": archived,
            "by_feature": by_feature,
            "execution_count": exec_count,
        }

    # ------------------------------------------------------------------
    # Lifecycle
    # ------------------------------------------------------------------

    def close(self):
        """Close the underlying SQLite connection."""
        if self._conn:
            self._conn.close()
            self._conn = None

    def __enter__(self):
        return self

    def __exit__(self, *args):
        self.close()
