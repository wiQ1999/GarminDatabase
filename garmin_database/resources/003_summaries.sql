-- Odtwarzalne podsumowania; fizyczne pola FIT pozostają bez zmian.
CREATE TABLE dataset_state (
    id INTEGER PRIMARY KEY CHECK(id = 1),
    revision INTEGER NOT NULL CHECK(revision >= 0)
) STRICT;
INSERT INTO dataset_state VALUES(1, 0);

CREATE TRIGGER decodes_summary_insert AFTER INSERT ON file_decodes BEGIN
    UPDATE dataset_state SET revision = revision + 1 WHERE id = 1;
END;
CREATE TRIGGER decodes_summary_update AFTER UPDATE ON file_decodes BEGIN
    UPDATE dataset_state SET revision = revision + 1 WHERE id = 1;
END;
CREATE TRIGGER decodes_summary_delete AFTER DELETE ON file_decodes BEGIN
    UPDATE dataset_state SET revision = revision + 1 WHERE id = 1;
END;
CREATE TRIGGER origins_summary_insert AFTER INSERT ON archive_entries BEGIN
    UPDATE dataset_state SET revision = revision + 1 WHERE id = 1;
END;
CREATE TRIGGER origins_summary_update AFTER UPDATE ON archive_entries BEGIN
    UPDATE dataset_state SET revision = revision + 1 WHERE id = 1;
END;
CREATE TRIGGER origins_summary_delete AFTER DELETE ON archive_entries BEGIN
    UPDATE dataset_state SET revision = revision + 1 WHERE id = 1;
END;

CREATE TABLE summary_cache (
    parameter_key TEXT PRIMARY KEY,
    method TEXT NOT NULL CHECK(method IN ('sample_mean','value_counts','last_observed')),
    algorithm_version INTEGER NOT NULL,
    data_revision INTEGER NOT NULL,
    from_day TEXT NOT NULL,
    to_day TEXT NOT NULL CHECK(to_day >= from_day),
    computed_at TEXT NOT NULL
) STRICT;

CREATE TABLE daily_summaries (
    parameter_key TEXT NOT NULL REFERENCES summary_cache(parameter_key) ON DELETE CASCADE,
    day TEXT NOT NULL,
    mean REAL,
    minimum REAL,
    maximum REAL,
    last_value_json TEXT CHECK(last_value_json IS NULL OR json_valid(last_value_json)),
    value_counts_json TEXT NOT NULL CHECK(json_valid(value_counts_json)),
    valid_count INTEGER NOT NULL CHECK(valid_count >= 0),
    invalid_count INTEGER NOT NULL CHECK(invalid_count >= 0),
    excluded_count INTEGER NOT NULL CHECK(excluded_count >= 0),
    untimed_count INTEGER NOT NULL CHECK(untimed_count >= 0),
    first_time TEXT,
    last_time TEXT,
    day_basis TEXT NOT NULL CHECK(day_basis IN ('measurement_time','requested_day','mixed')),
    PRIMARY KEY(parameter_key, day),
    CHECK((valid_count = 0 AND first_time IS NULL AND last_time IS NULL)
       OR (valid_count > 0 AND first_time IS NOT NULL AND last_time IS NOT NULL))
) STRICT, WITHOUT ROWID;

CREATE VIEW v_current_daily_summaries AS
SELECT d.*, c.method, c.algorithm_version, c.data_revision, c.computed_at
FROM daily_summaries d JOIN summary_cache c USING(parameter_key)
JOIN dataset_state s ON s.id = 1 AND s.revision = c.data_revision
WHERE c.algorithm_version = 1;

PRAGMA user_version = 3;
