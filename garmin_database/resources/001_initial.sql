-- Schemat docelowy v1. Nie importuje danych i nie tworzy bazy produkcyjnej.
PRAGMA foreign_keys = ON;

CREATE TABLE schema_migrations (
    version INTEGER PRIMARY KEY,
    applied_at TEXT NOT NULL,
    sql_sha256 TEXT NOT NULL CHECK(length(sql_sha256) = 64)
) STRICT;

CREATE TABLE decoder_profiles (
    id INTEGER PRIMARY KEY,
    parser_name TEXT NOT NULL,
    parser_version TEXT NOT NULL,
    profile_version TEXT NOT NULL,
    options_json TEXT NOT NULL CHECK(json_valid(options_json)),
    UNIQUE(parser_name, parser_version, profile_version, options_json)
) STRICT;

CREATE TABLE import_days (
    day TEXT PRIMARY KEY CHECK(length(day) = 10 AND date(day) IS day),
    download_status TEXT NOT NULL CHECK(download_status IN
        ('pending','downloaded','empty_zip','not_found_unverified','no_data_confirmed','failed','local_invalid')),
    attempts INTEGER NOT NULL DEFAULT 0 CHECK(attempts >= 0),
    checked_at TEXT,
    http_status INTEGER CHECK(http_status BETWEEN 100 AND 599),
    error_type TEXT,
    no_data_evidence TEXT
) STRICT;

CREATE TABLE archives (
    id INTEGER PRIMARY KEY,
    day TEXT NOT NULL UNIQUE REFERENCES import_days(day),
    relative_path TEXT NOT NULL UNIQUE,
    sha256 TEXT NOT NULL CHECK(length(sha256) = 64),
    size_bytes INTEGER NOT NULL CHECK(size_bytes >= 0),
    acquired_at TEXT,
    acquisition_origin TEXT NOT NULL CHECK(acquisition_origin IN ('webapi','local_archive','manual'))
) STRICT;

CREATE TABLE fit_files (
    id INTEGER PRIMARY KEY,
    sha256 TEXT NOT NULL UNIQUE CHECK(length(sha256) = 64),
    size_bytes INTEGER NOT NULL CHECK(size_bytes >= 0),
    protocol_version INTEGER,
    header_profile_version INTEGER,
    integrity_status TEXT NOT NULL CHECK(integrity_status IN ('pending','valid','invalid'))
) STRICT;

CREATE TABLE archive_entries (
    id INTEGER PRIMARY KEY,
    archive_id INTEGER NOT NULL REFERENCES archives(id),
    entry_index INTEGER NOT NULL CHECK(entry_index >= 0),
    entry_name TEXT NOT NULL,
    category TEXT NOT NULL,
    fit_file_id INTEGER NOT NULL REFERENCES fit_files(id),
    UNIQUE(archive_id, entry_index)
) STRICT;
CREATE INDEX archive_entries_file ON archive_entries(fit_file_id, archive_id);
CREATE INDEX archive_entries_category ON archive_entries(category, archive_id);

CREATE TABLE decode_runs (
    id INTEGER PRIMARY KEY,
    profile_id INTEGER NOT NULL REFERENCES decoder_profiles(id),
    started_at TEXT NOT NULL,
    finished_at TEXT,
    status TEXT NOT NULL CHECK(status IN ('running','complete','partial','failed','interrupted'))
) STRICT;

CREATE TABLE file_decodes (
    id INTEGER PRIMARY KEY,
    fit_file_id INTEGER NOT NULL REFERENCES fit_files(id),
    profile_id INTEGER NOT NULL REFERENCES decoder_profiles(id),
    run_id INTEGER NOT NULL REFERENCES decode_runs(id),
    status TEXT NOT NULL CHECK(status IN ('pending','complete','partial','failed')),
    decoded_at TEXT,
    is_active INTEGER NOT NULL DEFAULT 0 CHECK(is_active IN (0,1)),
    message_count INTEGER NOT NULL DEFAULT 0 CHECK(message_count >= 0),
    stored_field_count INTEGER NOT NULL DEFAULT 0 CHECK(stored_field_count >= 0),
    unknown_field_count INTEGER NOT NULL DEFAULT 0 CHECK(unknown_field_count >= 0),
    error_type TEXT,
    UNIQUE(fit_file_id, profile_id),
    CHECK(is_active = 0 OR status IN ('complete','partial'))
) STRICT;
CREATE UNIQUE INDEX one_active_decode_per_file ON file_decodes(fit_file_id) WHERE is_active = 1;

CREATE TABLE field_catalog (
    id INTEGER PRIMARY KEY,
    profile_id INTEGER NOT NULL REFERENCES decoder_profiles(id),
    stable_key TEXT NOT NULL,
    message_num INTEGER NOT NULL CHECK(message_num BETWEEN 0 AND 65535),
    field_num INTEGER NOT NULL CHECK(field_num BETWEEN 0 AND 255),
    variant_name TEXT NOT NULL,
    message_name TEXT,
    namespace TEXT NOT NULL CHECK(namespace IN ('native','developer')),
    developer_application_id_hex TEXT,
    developer_description_key TEXT,
    semantics_status TEXT NOT NULL CHECK(semantics_status IN ('profile_known','developer_described','unknown')),
    units TEXT,
    scale REAL CHECK(scale IS NULL OR scale != 0),
    offset REAL,
    semantic_type TEXT,
    numeric_projection_enabled INTEGER NOT NULL DEFAULT 0 CHECK(numeric_projection_enabled IN (0,1)),
    time_role TEXT NOT NULL DEFAULT 'none' CHECK(time_role IN
        ('none','utc_timestamp','local_timestamp','duration','compressed_timestamp','unknown')),
    representation TEXT NOT NULL DEFAULT 'unknown' CHECK(representation IN
        ('sample','source_summary','event','metadata','unknown')),
    profile_metadata_json TEXT NOT NULL CHECK(json_valid(profile_metadata_json)),
    UNIQUE(profile_id, stable_key)
) STRICT;
CREATE INDEX catalog_parameter ON field_catalog(message_num, field_num, variant_name);

CREATE TABLE message_definitions (
    id INTEGER PRIMARY KEY,
    file_decode_id INTEGER NOT NULL REFERENCES file_decodes(id) ON DELETE CASCADE,
    definition_index INTEGER NOT NULL CHECK(definition_index >= 0),
    global_message_num INTEGER NOT NULL CHECK(global_message_num BETWEEN 0 AND 65535),
    local_message_num INTEGER NOT NULL CHECK(local_message_num BETWEEN 0 AND 15),
    byte_order TEXT NOT NULL CHECK(byte_order IN ('little','big')),
    byte_offset INTEGER NOT NULL CHECK(byte_offset >= 0),
    UNIQUE(file_decode_id, definition_index),
    UNIQUE(id, file_decode_id)
) STRICT;

CREATE TABLE field_definitions (
    id INTEGER PRIMARY KEY,
    message_definition_id INTEGER NOT NULL REFERENCES message_definitions(id) ON DELETE CASCADE,
    field_order INTEGER NOT NULL CHECK(field_order >= 0),
    field_num INTEGER NOT NULL CHECK(field_num BETWEEN 0 AND 255),
    namespace TEXT NOT NULL CHECK(namespace IN ('native','developer')),
    developer_data_index INTEGER,
    base_type_id INTEGER NOT NULL,
    size_bytes INTEGER NOT NULL CHECK(size_bytes >= 0),
    UNIQUE(message_definition_id, field_order),
    UNIQUE(id, message_definition_id),
    CHECK((namespace = 'native' AND developer_data_index IS NULL)
       OR (namespace = 'developer' AND developer_data_index IS NOT NULL AND developer_data_index BETWEEN 0 AND 255))
) STRICT;

CREATE TABLE fit_messages (
    id INTEGER PRIMARY KEY,
    file_decode_id INTEGER NOT NULL REFERENCES file_decodes(id) ON DELETE CASCADE,
    message_definition_id INTEGER NOT NULL,
    message_index INTEGER NOT NULL CHECK(message_index >= 0),
    byte_offset INTEGER NOT NULL CHECK(byte_offset >= 0),
    byte_length INTEGER NOT NULL CHECK(byte_length > 0),
    record_header INTEGER NOT NULL DEFAULT 0 CHECK(record_header BETWEEN 0 AND 255),
    compressed_time_offset INTEGER CHECK(compressed_time_offset BETWEEN 0 AND 31),
    time_unix_ms INTEGER,
    time_basis TEXT NOT NULL CHECK(time_basis IN
        ('explicit_utc','compressed_header','timestamp_16','timestamp_min_8','associated_field','unknown','missing')),
    time_field_num INTEGER,
    time_resolution_json TEXT CHECK(time_resolution_json IS NULL OR json_valid(time_resolution_json)),
    UNIQUE(file_decode_id, message_index),
    UNIQUE(id, message_definition_id),
    FOREIGN KEY(message_definition_id, file_decode_id)
        REFERENCES message_definitions(id, file_decode_id),
    CHECK(time_unix_ms IS NULL OR time_basis NOT IN ('missing','unknown')),
    CHECK(((record_header & 128) = 0 AND compressed_time_offset IS NULL)
       OR ((record_header & 128) != 0 AND compressed_time_offset IS NOT NULL
           AND compressed_time_offset = (record_header & 31)))
) STRICT;
CREATE INDEX messages_time ON fit_messages(time_unix_ms, id) WHERE time_unix_ms IS NOT NULL;
CREATE INDEX messages_definition ON fit_messages(message_definition_id, time_unix_ms);

CREATE TABLE fit_fields (
    message_id INTEGER NOT NULL,
    field_definition_id INTEGER NOT NULL,
    message_definition_id INTEGER NOT NULL,
    resolved_catalog_id INTEGER REFERENCES field_catalog(id),
    value_kind TEXT NOT NULL CHECK(value_kind IN ('null','integer','real','text','json','integer_text')),
    integer_value INTEGER,
    real_value REAL,
    text_value TEXT,
    json_value TEXT CHECK(json_value IS NULL OR json_valid(json_value)),
    validity TEXT NOT NULL CHECK(validity IN ('valid','invalid','partial_invalid','decode_error')),
    PRIMARY KEY(message_id, field_definition_id),
    FOREIGN KEY(message_id, message_definition_id)
        REFERENCES fit_messages(id, message_definition_id) ON DELETE CASCADE,
    FOREIGN KEY(field_definition_id, message_definition_id)
        REFERENCES field_definitions(id, message_definition_id),
    CHECK(
       (value_kind = 'null' AND integer_value IS NULL AND real_value IS NULL AND text_value IS NULL AND json_value IS NULL)
       OR (value_kind = 'integer' AND integer_value IS NOT NULL AND real_value IS NULL AND text_value IS NULL AND json_value IS NULL)
       OR (value_kind = 'real' AND integer_value IS NULL AND real_value IS NOT NULL AND text_value IS NULL AND json_value IS NULL)
       OR (value_kind IN ('text','integer_text') AND integer_value IS NULL AND real_value IS NULL AND text_value IS NOT NULL AND json_value IS NULL)
       OR (value_kind = 'json' AND integer_value IS NULL AND real_value IS NULL AND text_value IS NULL AND json_value IS NOT NULL)
    )
) STRICT, WITHOUT ROWID;
CREATE INDEX fields_parameter_message ON fit_fields(resolved_catalog_id, message_id);

CREATE TABLE interpretation_rules (
    id INTEGER PRIMARY KEY,
    profile_id INTEGER NOT NULL REFERENCES decoder_profiles(id),
    source_catalog_id INTEGER NOT NULL REFERENCES field_catalog(id),
    target_catalog_id INTEGER NOT NULL REFERENCES field_catalog(id),
    kind TEXT NOT NULL CHECK(kind IN ('component','subfield','timestamp_resolution')),
    rule_json TEXT NOT NULL CHECK(json_valid(rule_json)),
    UNIQUE(profile_id, source_catalog_id, target_catalog_id, kind)
) STRICT;

CREATE TABLE decode_issues (
    id INTEGER PRIMARY KEY,
    file_decode_id INTEGER NOT NULL REFERENCES file_decodes(id) ON DELETE CASCADE,
    message_index INTEGER,
    field_num INTEGER,
    issue_code TEXT NOT NULL,
    severity TEXT NOT NULL CHECK(severity IN ('info','warning','error')),
    context_json TEXT NOT NULL CHECK(json_valid(context_json))
) STRICT;
CREATE INDEX decode_issues_file ON decode_issues(file_decode_id, severity);

CREATE VIEW v_active_fields AS
SELECT m.id AS message_id, m.message_index, m.time_unix_ms, m.time_basis,
       d.global_message_num, fd.field_num, fd.namespace, fd.developer_data_index,
       f.resolved_catalog_id, c.stable_key, c.message_name, c.variant_name,
       c.semantics_status, c.units, c.scale, c.offset, c.numeric_projection_enabled,
       f.value_kind, f.integer_value, f.real_value, f.text_value, f.json_value, f.validity,
       x.fit_file_id
FROM fit_fields f
JOIN fit_messages m ON m.id = f.message_id
JOIN message_definitions d ON d.id = m.message_definition_id
JOIN field_definitions fd ON fd.id = f.field_definition_id
JOIN file_decodes x ON x.id = m.file_decode_id AND x.is_active = 1
LEFT JOIN field_catalog c ON c.id = f.resolved_catalog_id;

-- Konwersja według profilu FIT: value = raw / scale - offset.
-- Tylko rozpoznane, poprawne pola skalarne; tablice i uint64 wymagają eksportera.
CREATE VIEW v_numeric_parameters AS
SELECT *, (CASE value_kind WHEN 'integer' THEN integer_value ELSE real_value END)
              / coalesce(scale, 1.0) - coalesce(offset, 0.0) AS value
FROM v_active_fields
WHERE value_kind IN ('integer','real') AND validity = 'valid'
  AND numeric_projection_enabled = 1
  AND semantics_status IN ('profile_known','developer_described');

CREATE VIEW v_field_provenance AS
SELECT x.id AS file_decode_id, x.fit_file_id, a.day AS requested_day,
       a.relative_path, e.entry_index, e.entry_name, e.category
FROM file_decodes x
JOIN archive_entries e ON e.fit_file_id = x.fit_file_id
JOIN archives a ON a.id = e.archive_id
WHERE x.is_active = 1;

PRAGMA user_version = 1;
