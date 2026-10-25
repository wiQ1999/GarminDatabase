"""Bounded SQL batches; the caller owns the entire FIT transaction."""

MESSAGE_COLUMNS = (
    "file_decode_id,message_definition_id,message_index,byte_offset,byte_length,"
    "record_header,compressed_time_offset,time_unix_ms,time_basis,time_field_num,"
    "time_resolution_json"
)
MESSAGE_TYPES = ["bigint"] * 8 + ["text", "bigint", "text"]
FIELD_COLUMNS = (
    "message_id,field_definition_id,message_definition_id,resolved_catalog_id,"
    "value_kind,integer_value,real_value,text_value,json_value,validity"
)


def row_size(row):
    # Include tuple/scalar overhead and encoded variable-length values. A single
    # source message can exceed the budget; it is flushed on its own.
    return 64 + sum(len(v.encode("utf-8")) if isinstance(v, str) else 32 for v in row)


class MessageBatch:
    max_messages = 512
    max_fields = 4096
    max_bytes = 2 * 1024 * 1024

    def __init__(self, conn, check):
        self.conn, self.check = conn, check
        self.messages, self.fields = [], []
        self.size = 0

    def append(self, message, fields):
        size = row_size(message) + sum(row_size(row) for row in fields)
        if self.size + size > self.max_bytes:
            self.flush()
        self.messages.append(message)
        self.fields.extend(fields)
        self.size += size
        if self.full():
            self.flush()

    def full(self):
        return (
            len(self.messages) >= self.max_messages
            or len(self.fields) >= self.max_fields
            or self.size >= self.max_bytes
        )

    def flush(self):
        if not self.messages:
            return
        self.check()
        arrays = [list(values) for values in zip(*self.messages)]
        casts = ",".join("%s::" + kind + "[]" for kind in MESSAGE_TYPES)
        # Match returned identities by the source message index, never by the
        # order of RETURNING rows or by assumptions about consecutive IDs.
        identities = {
            index: identity
            for identity, index in self.conn.execute(
                f"INSERT INTO fit_messages({MESSAGE_COLUMNS}) "
                f"SELECT * FROM unnest({casts}) RETURNING id,message_index",
                arrays,
            )
        }
        with self.conn.cursor() as cursor:
            with cursor.copy(f"COPY fit_fields({FIELD_COLUMNS}) FROM STDIN") as copy:
                for index, *values in self.fields:
                    self.check()
                    copy.write_row((identities[index], *values))
        self.messages.clear()
        self.fields.clear()
        self.size = 0
