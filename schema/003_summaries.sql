-- Odtwarzalne podsumowania; fizyczne pola FIT pozostają bez zmian.
CREATE TABLE dataset_state (
    id BIGINT PRIMARY KEY CHECK(id = 1),
    revision BIGINT NOT NULL CHECK(revision >= 0)
);
INSERT INTO dataset_state VALUES(1, 0);

CREATE FUNCTION invalidate_summaries() RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN
    UPDATE dataset_state SET revision = revision + 1 WHERE id = 1;
    RETURN NULL;
END;
$$;

CREATE TRIGGER decodes_summary_insert AFTER INSERT ON file_decodes
    FOR EACH STATEMENT EXECUTE FUNCTION invalidate_summaries();
CREATE TRIGGER decodes_summary_update AFTER UPDATE ON file_decodes
    FOR EACH STATEMENT EXECUTE FUNCTION invalidate_summaries();
CREATE TRIGGER decodes_summary_delete AFTER DELETE ON file_decodes
    FOR EACH STATEMENT EXECUTE FUNCTION invalidate_summaries();
CREATE TRIGGER origins_summary_insert AFTER INSERT ON archive_entries
    FOR EACH STATEMENT EXECUTE FUNCTION invalidate_summaries();
CREATE TRIGGER origins_summary_update AFTER UPDATE ON archive_entries
    FOR EACH STATEMENT EXECUTE FUNCTION invalidate_summaries();
CREATE TRIGGER origins_summary_delete AFTER DELETE ON archive_entries
    FOR EACH STATEMENT EXECUTE FUNCTION invalidate_summaries();

CREATE TABLE summary_cache (
    parameter_key TEXT PRIMARY KEY,
    method TEXT NOT NULL CHECK(method IN ('sample_mean','value_counts','last_observed')),
    algorithm_version BIGINT NOT NULL,
    data_revision BIGINT NOT NULL,
    from_day TEXT NOT NULL,
    to_day TEXT NOT NULL CHECK(to_day >= from_day),
    computed_at TEXT NOT NULL
);

CREATE TABLE daily_summaries (
    parameter_key TEXT NOT NULL REFERENCES summary_cache(parameter_key) ON DELETE CASCADE,
    day TEXT NOT NULL,
    mean DOUBLE PRECISION,
    minimum DOUBLE PRECISION,
    maximum DOUBLE PRECISION,
    last_value_json TEXT CHECK(last_value_json IS NULL OR (last_value_json::json IS NOT NULL)),
    value_counts_json TEXT NOT NULL CHECK((value_counts_json::json IS NOT NULL)),
    valid_count BIGINT NOT NULL CHECK(valid_count >= 0),
    invalid_count BIGINT NOT NULL CHECK(invalid_count >= 0),
    excluded_count BIGINT NOT NULL CHECK(excluded_count >= 0),
    untimed_count BIGINT NOT NULL CHECK(untimed_count >= 0),
    first_time TEXT,
    last_time TEXT,
    day_basis TEXT NOT NULL CHECK(day_basis IN ('measurement_time','requested_day','mixed')),
    PRIMARY KEY(parameter_key, day),
    CHECK((valid_count = 0 AND first_time IS NULL AND last_time IS NULL)
       OR (valid_count > 0 AND first_time IS NOT NULL AND last_time IS NOT NULL))
);

CREATE VIEW v_current_daily_summaries AS
SELECT d.*, c.method, c.algorithm_version, c.data_revision, c.computed_at
FROM daily_summaries d JOIN summary_cache c USING(parameter_key)
JOIN dataset_state s ON s.id = 1 AND s.revision = c.data_revision
WHERE c.algorithm_version = 1;
