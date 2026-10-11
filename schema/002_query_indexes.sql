-- Indeks FK potrzebny do wymiany wyników FIT bez skanowania wszystkich pól.
CREATE INDEX IF NOT EXISTS fields_definition_context
    ON fit_fields(field_definition_id, message_definition_id);
CREATE INDEX IF NOT EXISTS catalog_representation
    ON field_catalog(representation, id);
CREATE INDEX IF NOT EXISTS interpretation_target
    ON interpretation_rules(target_catalog_id, kind, source_catalog_id);
PRAGMA user_version = 2;
