-- Semantic Index Schema for Acceptance Scenarios
-- Uses HSF (Hybrid Scoring Function) for text-based semantic search
-- HSF(q, d) = alpha * TF-IDF(q, d) + beta * SubstringBoost(q, d)

-------------------------------------------------------------------------------
-- Scenarios: core table for indexed acceptance scenarios
-------------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS scenarios (
    id               INTEGER PRIMARY KEY AUTOINCREMENT,
    name             TEXT    NOT NULL,
    description      TEXT    DEFAULT '',
    feature          TEXT    DEFAULT '',
    tags             TEXT    DEFAULT '[]',
    source_path      TEXT    DEFAULT '',
    status           TEXT    DEFAULT 'active' CHECK (status IN ('active', 'archived')),
    importance_score REAL    DEFAULT 0.5,
    access_count     INTEGER DEFAULT 0,
    last_access      TEXT,
    created_at       TEXT    DEFAULT (datetime('now')),
    updated_at       TEXT    DEFAULT (datetime('now'))
);

-------------------------------------------------------------------------------
-- Terms: inverted index for TF-IDF computation
-------------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS terms (
    term            TEXT    NOT NULL,
    scenario_id     INTEGER NOT NULL,
    tf              REAL    DEFAULT 0,
    idf             REAL    DEFAULT 0,
    PRIMARY KEY (term, scenario_id),
    FOREIGN KEY (scenario_id) REFERENCES scenarios(id) ON DELETE CASCADE
);

-------------------------------------------------------------------------------
-- Scenario stats: cached aggregate statistics
-------------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS scenario_stats (
    total_scenarios        INTEGER DEFAULT 0,
    avg_description_length REAL    DEFAULT 0
);

-------------------------------------------------------------------------------
-- Execution results: historical test run data
-------------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS execution_results (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    scenario_name   TEXT    NOT NULL,
    passed          INTEGER DEFAULT 0,
    step_results    TEXT    DEFAULT '{}',
    duration_ms     REAL    DEFAULT 0,
    timestamp       TEXT    DEFAULT (datetime('now'))
);

-------------------------------------------------------------------------------
-- Config: key-value store for tunable parameters
-------------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS config (
    key         TEXT PRIMARY KEY,
    value       TEXT,
    description TEXT
);

-------------------------------------------------------------------------------
-- Memory votes: co-forgetting / memory pruning votes from agents
-------------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS memory_votes (
    scenario_id     INTEGER NOT NULL,
    agent_id        TEXT    NOT NULL,
    vote            INTEGER DEFAULT 3 CHECK (vote IN (1, 2, 3)),
    confidence_val  REAL    DEFAULT 0.5,
    reason          TEXT    DEFAULT '',
    timestamp       TEXT    DEFAULT (datetime('now')),
    PRIMARY KEY (scenario_id, agent_id),
    FOREIGN KEY (scenario_id) REFERENCES scenarios(id) ON DELETE CASCADE
);

-------------------------------------------------------------------------------
-- Indexes
-------------------------------------------------------------------------------
CREATE INDEX IF NOT EXISTS idx_scenarios_name     ON scenarios(name);
CREATE INDEX IF NOT EXISTS idx_scenarios_feature  ON scenarios(feature);
CREATE INDEX IF NOT EXISTS idx_scenarios_status   ON scenarios(status);
CREATE INDEX IF NOT EXISTS idx_terms_term         ON terms(term);
CREATE INDEX IF NOT EXISTS idx_terms_scenario_id  ON terms(scenario_id);

-------------------------------------------------------------------------------
-- Triggers: auto-update timestamps
-------------------------------------------------------------------------------

-- Auto-update updated_at on any scenario modification
CREATE TRIGGER IF NOT EXISTS trg_scenarios_updated_at
AFTER UPDATE ON scenarios
FOR EACH ROW
BEGIN
    UPDATE scenarios
    SET updated_at = datetime('now')
    WHERE id = NEW.id;
END;

-- Auto-update scenario_stats.total_scenarios on insert
CREATE TRIGGER IF NOT EXISTS trg_stats_after_insert
AFTER INSERT ON scenarios
WHEN NEW.status = 'active'
BEGIN
    UPDATE scenario_stats
    SET total_scenarios = (
        SELECT COUNT(*) FROM scenarios WHERE status = 'active'
    ),
    avg_description_length = (
        SELECT AVG(LENGTH(description)) FROM scenarios WHERE status = 'active'
    );
END;

-- Auto-update scenario_stats on status change (archive / reactivate)
CREATE TRIGGER IF NOT EXISTS trg_stats_after_update
AFTER UPDATE OF status ON scenarios
FOR EACH ROW
WHEN OLD.status <> NEW.status
BEGIN
    UPDATE scenario_stats
    SET total_scenarios = (
        SELECT COUNT(*) FROM scenarios WHERE status = 'active'
    ),
    avg_description_length = (
        SELECT AVG(LENGTH(description)) FROM scenarios WHERE status = 'active'
    );
END;

-- Auto-update scenario_stats on scenario deletion
CREATE TRIGGER IF NOT EXISTS trg_stats_after_delete
AFTER DELETE ON scenarios
BEGIN
    UPDATE scenario_stats
    SET total_scenarios = (
        SELECT COUNT(*) FROM scenarios WHERE status = 'active'
    ),
    avg_description_length = (
        SELECT COALESCE(AVG(LENGTH(description)), 0)
        FROM scenarios WHERE status = 'active'
    );
END;

-- Auto-clean terms and votes when a scenario is deleted
CREATE TRIGGER IF NOT EXISTS trg_cleanup_terms_on_delete
AFTER DELETE ON scenarios
FOR EACH ROW
BEGIN
    DELETE FROM terms WHERE scenario_id = OLD.id;
    DELETE FROM memory_votes WHERE scenario_id = OLD.id;
END;

-------------------------------------------------------------------------------
-- Seed default config values
-------------------------------------------------------------------------------
INSERT OR IGNORE INTO config (key, value, description) VALUES
    ('hsf_alpha',            '0.6', 'TF-IDF weight in HSF formula'),
    ('hsf_beta',             '0.4', 'Substring boost weight in HSF formula'),
    ('similarity_threshold', '0.7', 'Minimum HSF score to consider a match');

-- Seed stats row
INSERT OR IGNORE INTO scenario_stats (total_scenarios, avg_description_length) VALUES (0, 0);
