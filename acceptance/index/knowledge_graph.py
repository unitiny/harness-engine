"""
Knowledge graph for acceptance scenarios using RANGER-style entity-relationship analysis.

Supports impact analysis, test coverage checking, and Mermaid graph export.
Entities: scenarios, features, components, APIs, tests
Relations: tests, covers, depends_on, references
"""
from __future__ import annotations

import sqlite3
import json
import re
from dataclasses import dataclass, field
from enum import Enum
from typing import Dict, List, Optional, Set, Tuple
from pathlib import Path


class EntityType(Enum):
    SCENARIO = "scenario"
    FEATURE = "feature"
    COMPONENT = "component"
    API = "api"
    TEST = "test"
    PAGE = "page"


class RelationType(Enum):
    TESTS = "tests"
    COVERS = "covers"
    DEPENDS_ON = "depends_on"
    REFERENCES = "references"
    BELONGS_TO = "belongs_to"


@dataclass
class GraphEntity:
    id: int
    entity_type: EntityType
    name: str
    description: str = ""
    file_path: str = ""
    tags: List[str] = field(default_factory=list)
    metadata: Dict = field(default_factory=dict)


@dataclass
class GraphRelation:
    id: int
    source_id: int
    target_id: int
    relation_type: RelationType
    weight: float = 1.0
    metadata: Dict = field(default_factory=dict)


@dataclass
class ImpactResult:
    entity_id: int
    entity_name: str
    entity_type: str
    depth: int
    impact_score: float
    path: List[str] = field(default_factory=list)


class KnowledgeGraph:
    """
    RANGER-style knowledge graph for acceptance scenario impact analysis.

    Stores entities (scenarios, features, components, APIs, pages) and
    their relationships. Supports recursive impact analysis via CTE,
    test coverage analysis, and Mermaid visualization export.
    """

    def __init__(self, db_path: str = ":memory:"):
        self._conn = sqlite3.connect(db_path)
        self._conn.row_factory = sqlite3.Row
        self._init_schema()

    def _init_schema(self):
        self._conn.executescript("""
            CREATE TABLE IF NOT EXISTS entities (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                entity_type TEXT NOT NULL,
                name TEXT NOT NULL,
                description TEXT DEFAULT '',
                file_path TEXT DEFAULT '',
                tags TEXT DEFAULT '[]',
                metadata TEXT DEFAULT '{}',
                created_at TEXT DEFAULT (datetime('now'))
            );
            CREATE TABLE IF NOT EXISTS relations (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                source_id INTEGER NOT NULL REFERENCES entities(id),
                target_id INTEGER NOT NULL REFERENCES entities(id),
                relation_type TEXT NOT NULL,
                weight REAL DEFAULT 1.0,
                metadata TEXT DEFAULT '{}',
                UNIQUE(source_id, target_id, relation_type)
            );
            CREATE INDEX IF NOT EXISTS idx_entities_type ON entities(entity_type);
            CREATE INDEX IF NOT EXISTS idx_entities_name ON entities(name);
            CREATE INDEX IF NOT EXISTS idx_relations_source ON relations(source_id);
            CREATE INDEX IF NOT EXISTS idx_relations_target ON relations(target_id);
        """)
        self._conn.commit()

    def add_entity(self, entity_type: EntityType, name: str, description: str = "",
                   file_path: str = "", tags: List[str] = None, metadata: Dict = None) -> int:
        cursor = self._conn.execute(
            "INSERT INTO entities (entity_type, name, description, file_path, tags, metadata) VALUES (?, ?, ?, ?, ?, ?)",
            (entity_type.value, name, description, file_path,
             json.dumps(tags or [], ensure_ascii=False),
             json.dumps(metadata or {}, ensure_ascii=False))
        )
        self._conn.commit()
        return cursor.lastrowid

    def get_entity(self, entity_id: int) -> Optional[GraphEntity]:
        row = self._conn.execute("SELECT * FROM entities WHERE id=?", (entity_id,)).fetchone()
        if not row:
            return None
        return GraphEntity(
            id=row["id"], entity_type=EntityType(row["entity_type"]),
            name=row["name"], description=row["description"],
            file_path=row["file_path"], tags=json.loads(row["tags"]),
            metadata=json.loads(row["metadata"])
        )

    def find_entities_by_name(self, name_pattern: str, entity_type: EntityType = None) -> List[GraphEntity]:
        sql = "SELECT * FROM entities WHERE name LIKE ?"
        params = [f"%{name_pattern}%"]
        if entity_type:
            sql += " AND entity_type=?"
            params.append(entity_type.value)
        rows = self._conn.execute(sql, params).fetchall()
        return [self._row_to_entity(r) for r in rows]

    def add_relation(self, source_id: int, target_id: int, relation_type: RelationType,
                     weight: float = 1.0, metadata: Dict = None) -> int:
        cursor = self._conn.execute(
            "INSERT OR REPLACE INTO relations (source_id, target_id, relation_type, weight, metadata) VALUES (?, ?, ?, ?, ?)",
            (source_id, target_id, relation_type.value, weight, json.dumps(metadata or {}))
        )
        self._conn.commit()
        return cursor.lastrowid

    def get_relations(self, entity_id: int, direction: str = "outgoing") -> List[GraphRelation]:
        if direction == "outgoing":
            sql = "SELECT * FROM relations WHERE source_id=?"
        elif direction == "incoming":
            sql = "SELECT * FROM relations WHERE target_id=?"
        else:
            sql = "SELECT * FROM relations WHERE source_id=? OR target_id=?"

        params = [entity_id] if direction != "both" else [entity_id, entity_id]
        rows = self._conn.execute(sql, params).fetchall()
        return [GraphRelation(
            id=r["id"], source_id=r["source_id"], target_id=r["target_id"],
            relation_type=RelationType(r["relation_type"]), weight=r["weight"],
            metadata=json.loads(r["metadata"])
        ) for r in rows]

    def analyze_impact(self, entity_id: int, max_depth: int = 5) -> List[ImpactResult]:
        """
        Downstream impact analysis using recursive CTE.
        Finds all entities that depend on the target entity.
        Impact score = 1 / (1 + depth).
        """
        entity = self.get_entity(entity_id)
        root_name = entity.name if entity else str(entity_id)

        rows = self._conn.execute("""
            WITH RECURSIVE impact_tree(entity_id, depth, path) AS (
                SELECT ?, 0, CAST(? AS TEXT)
                UNION ALL
                SELECT r.source_id, it.depth + 1,
                       it.path || ' -> ' || e.name
                FROM relations r
                JOIN entities e ON e.id = r.source_id
                JOIN impact_tree it ON it.entity_id = r.target_id
                WHERE it.depth < ? AND r.relation_type IN ('depends_on', 'references', 'covers')
            )
            SELECT it.entity_id, e.name, e.entity_type, it.depth, it.path
            FROM impact_tree it
            JOIN entities e ON e.id = it.entity_id
            WHERE it.depth > 0
            ORDER BY it.depth
        """, (entity_id, root_name, max_depth)).fetchall()

        results = []
        seen = set()
        for r in rows:
            if r["entity_id"] not in seen:
                seen.add(r["entity_id"])
                results.append(ImpactResult(
                    entity_id=r["entity_id"], entity_name=r["name"],
                    entity_type=r["entity_type"], depth=r["depth"],
                    impact_score=1.0 / (1 + r["depth"]),
                    path=r["path"].split(" -> ") if r["path"] else [],
                ))
        return results

    def analyze_dependencies(self, entity_id: int, max_depth: int = 5) -> List[ImpactResult]:
        """
        Upstream dependency analysis using recursive CTE.
        Finds all entities that the target depends on.
        """
        entity = self.get_entity(entity_id)
        root_name = entity.name if entity else str(entity_id)

        rows = self._conn.execute("""
            WITH RECURSIVE dep_tree(entity_id, depth, path) AS (
                SELECT ?, 0, CAST(? AS TEXT)
                UNION ALL
                SELECT r.target_id, dt.depth + 1,
                       dt.path || ' -> ' || e.name
                FROM relations r
                JOIN entities e ON e.id = r.target_id
                JOIN dep_tree dt ON dt.entity_id = r.source_id
                WHERE dt.depth < ? AND r.relation_type IN ('depends_on', 'references')
            )
            SELECT dt.entity_id, e.name, e.entity_type, dt.depth, dt.path
            FROM dep_tree dt
            JOIN entities e ON e.id = dt.entity_id
            WHERE dt.depth > 0
            ORDER BY dt.depth
        """, (entity_id, root_name, max_depth)).fetchall()

        results = []
        seen = set()
        for r in rows:
            if r["entity_id"] not in seen:
                seen.add(r["entity_id"])
                results.append(ImpactResult(
                    entity_id=r["entity_id"], entity_name=r["name"],
                    entity_type=r["entity_type"], depth=r["depth"],
                    impact_score=1.0 / (1 + r["depth"]),
                    path=r["path"].split(" -> ") if r["path"] else [],
                ))
        return results

    def get_test_coverage(self, entity_id: int) -> Dict:
        """Get test coverage info for an entity."""
        direct = self._conn.execute(
            "SELECT e.id, e.name FROM relations r JOIN entities e ON e.id = r.source_id WHERE r.target_id=? AND r.relation_type IN ('tests', 'covers')",
            (entity_id,)
        ).fetchall()
        indirect = self._conn.execute(
            "SELECT e.id, e.name FROM relations r JOIN entities e ON e.id = r.source_id WHERE r.target_id IN (SELECT target_id FROM relations WHERE source_id=? AND relation_type='depends_on') AND r.relation_type IN ('tests', 'covers')",
            (entity_id,)
        ).fetchall()
        coverage_score = min(1.0, len(direct) * 0.3 + len(indirect) * 0.1)
        return {
            "direct_tests": [{"id": r["id"], "name": r["name"]} for r in direct],
            "indirect_tests": [{"id": r["id"], "name": r["name"]} for r in indirect],
            "coverage_score": coverage_score,
            "total_tests": len(direct) + len(indirect),
        }

    def find_untested(self) -> List[GraphEntity]:
        """Find entities with no incoming 'tests' or 'covers' relations."""
        rows = self._conn.execute("""
            SELECT e.* FROM entities e
            WHERE e.entity_type NOT IN ('test', 'scenario')
            AND NOT EXISTS (
                SELECT 1 FROM relations r WHERE r.target_id = e.id AND r.relation_type IN ('tests', 'covers')
            )
        """).fetchall()
        return [self._row_to_entity(r) for r in rows]

    def export_mermaid(self, entity_types: List[EntityType] = None, max_nodes: int = 50) -> str:
        """Export graph as Mermaid diagram."""
        lines = ["graph TD"]
        type_colors = {
            EntityType.SCENARIO: "#ffa",
            EntityType.FEATURE: "#afa",
            EntityType.COMPONENT: "#aaf",
            EntityType.API: "#aff",
            EntityType.TEST: "#faa",
            EntityType.PAGE: "#ddd",
        }

        sql = "SELECT * FROM entities"
        params = []
        if entity_types:
            placeholders = ",".join("?" * len(entity_types))
            sql += f" WHERE entity_type IN ({placeholders})"
            params = [t.value for t in entity_types]
        sql += f" LIMIT {max_nodes}"

        entities = self._conn.execute(sql, params).fetchall()
        entity_ids = {r["id"] for r in entities}

        for r in entities:
            lines.append(f'    E{r["id"]}["{r["name"]}<br>({r["entity_type"]})"]:::style{r["entity_type"]}')

        relations = self._conn.execute("SELECT * FROM relations").fetchall()
        arrow_styles = {
            "tests": "-.->",
            "covers": "-.->",
            "depends_on": "-->",
            "references": "-->",
            "belongs_to": "-->",
        }
        for r in relations:
            if r["source_id"] in entity_ids and r["target_id"] in entity_ids:
                arrow = arrow_styles.get(r["relation_type"], "-->")
                label = r["relation_type"].replace("_", " ")
                lines.append(f'    E{r["source_id"]} {arrow}|" {label} "| E{r["target_id"]}')

        for et, color in type_colors.items():
            lines.append(f'    classDef style{et.value} fill:{color}')

        return "\n".join(lines)

    def get_stats(self) -> Dict:
        by_type = dict(self._conn.execute(
            "SELECT entity_type, COUNT(*) FROM entities GROUP BY entity_type"
        ).fetchall())
        by_relation = dict(self._conn.execute(
            "SELECT relation_type, COUNT(*) FROM relations GROUP BY relation_type"
        ).fetchall())
        total_entities = self._conn.execute("SELECT COUNT(*) FROM entities").fetchone()[0]
        total_relations = self._conn.execute("SELECT COUNT(*) FROM relations").fetchone()[0]
        isolated = self._conn.execute("""
            SELECT COUNT(*) FROM entities e
            WHERE NOT EXISTS (
                SELECT 1 FROM relations r WHERE r.source_id=e.id OR r.target_id=e.id
            )
        """).fetchone()[0]
        return {
            "total_entities": total_entities,
            "total_relations": total_relations,
            "by_type": by_type,
            "by_relation": by_relation,
            "isolated_entities": isolated,
        }

    def _row_to_entity(self, row) -> GraphEntity:
        return GraphEntity(
            id=row["id"], entity_type=EntityType(row["entity_type"]),
            name=row["name"], description=row["description"],
            file_path=row["file_path"], tags=json.loads(row["tags"]),
            metadata=json.loads(row["metadata"])
        )

    def close(self):
        self._conn.close()

    def __enter__(self):
        return self

    def __exit__(self, *args):
        self.close()
