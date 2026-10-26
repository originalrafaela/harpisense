
import json
from datetime import datetime, timezone

import psycopg
from psycopg.types.json import Jsonb

KINDS = {
    "asset", "telemetry", "network_event", "window",
    "detection", "xai", "evidence", "incident",
    "risk", "decision", "approval", "execution",
    "verification", "bitnet",
}


class PostgresStore:
    def __init__(self, conninfo):
        self.conninfo = conninfo

    def _connect(self):
        return psycopg.connect(self.conninfo)

    def insert(self, kind, item):
        if kind not in KINDS:
            raise ValueError("unknown kind")

        if (
            not item.id
            or item.revision < 1
            or item.source not in {"synthetic", "trusted-service"}
        ):
            raise ValueError("invalid record")

        payload = json.dumps(
            item.data,
            sort_keys=True,
            ensure_ascii=False,
            separators=(",", ":"),
        )

        with self._connect() as conn:
            # Serializa gravações concorrentes da mesma entidade.
            conn.execute(
                "SELECT pg_advisory_xact_lock(hashtextextended(%s, 0))",
                (json.dumps([kind, item.id]),),
            )

            existing = conn.execute(
                """
                SELECT data, source
                FROM projections
                WHERE kind = %s AND id = %s AND revision = %s
                """,
                (kind, item.id, item.revision),
            ).fetchone()

            if existing is not None:
                old_data, old_source = existing
                old_payload = json.dumps(
                    old_data,
                    sort_keys=True,
                    ensure_ascii=False,
                    separators=(",", ":"),
                )
                if old_payload == payload and old_source == item.source:
                    return False
                raise ValueError("immutable revision conflict")

            latest = conn.execute(
                """
                SELECT MAX(revision)
                FROM projections
                WHERE kind = %s AND id = %s
                """,
                (kind, item.id),
            ).fetchone()[0]

            if latest is None and item.revision != 1:
                raise ValueError("first revision must be 1")

            if latest is not None and item.revision != latest + 1:
                raise ValueError("revision gap or stale update")

            conn.execute(
                """
                INSERT INTO projections
                    (kind, id, revision, source, data, created_at)
                VALUES (%s, %s, %s, %s, %s, %s)
                """,
                (
                    kind,
                    item.id,
                    item.revision,
                    item.source,
                    Jsonb(item.data),
                    datetime.now(timezone.utc),
                ),
            )

            return True

    def list(self, kind, limit=50, offset=0):
        if kind not in KINDS:
            raise ValueError("unknown kind")

        with self._connect() as conn:
            rows = conn.execute(
                """
                SELECT DISTINCT ON (id)
                    id, revision, source, data, created_at
                FROM projections
                WHERE kind = %s
                ORDER BY id, revision DESC
                """,
                (kind,),
            ).fetchall()

        records = [
            {
                "id": row[0],
                "revision": row[1],
                "source": row[2],
                "data": row[3],
                "created_at": row[4].isoformat(),
            }
            for row in rows
        ]

        records.sort(
            key=lambda record: (
                record["created_at"],
                record["id"],
            ),
            reverse=True,
        )

        return records[offset:offset + limit]

    def history(self, kind, id):
        if kind not in KINDS:
            raise ValueError("unknown kind")

        with self._connect() as conn:
            rows = conn.execute(
                """
                SELECT revision, source, data
                FROM projections
                WHERE kind = %s AND id = %s
                ORDER BY revision
                """,
                (kind, id),
            ).fetchall()

        return [
            {
                "revision": row[0],
                "source": row[1],
                "data": row[2],
            }
            for row in rows
        ]
