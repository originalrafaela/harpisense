"""PostgreSQL issuer; private key is supplied exclusively to this service."""
import hashlib
import hmac
import secrets
import uuid
from contextlib import contextmanager
import psycopg
from psycopg.rows import dict_row
from psycopg.types.json import Jsonb
from . import envelopes as wire

CHALLENGE_FIELDS = ('version','challenge_id','nonce','license_id','installation_id','installation_key_id','platform','issued_at','expires_at')
PROOF_FIELDS = ('version','challenge_id','nonce','license_id','installation_id','installation_key_id','platform')
CONFLICT_MESSAGE = 'Esta licença já foi ativada em outra instalação.'


class IssuerError(Exception):
    def __init__(self, status, code):
        super().__init__(code)
        self.status, self.code = status, code
        self.message = CONFLICT_MESSAGE if code == 'LICENSE_ALREADY_ACTIVATED' else code


def digest(value):
    return hashlib.sha256(value.encode('ascii')).hexdigest()


class LicenseIssuer:
    def __init__(self, conninfo, private_key, *, public_keys=None, random_key=None):
        self.conninfo, self.private_key = conninfo, private_key
        self.keys = dict(public_keys or {})
        self.keys[wire.key_id(private_key.public_key())] = private_key.public_key()
        self.random_key = random_key or (lambda: secrets.token_urlsafe(32))

    @contextmanager
    def transaction(self):
        try:
            with psycopg.connect(self.conninfo, row_factory=dict_row, connect_timeout=5) as conn:
                conn.execute("SET LOCAL lock_timeout='5s'")
                conn.execute("SET LOCAL statement_timeout='10s'")
                yield conn
        except psycopg.Error:
            raise IssuerError(503, 'ISSUER_UNAVAILABLE') from None

    @staticmethod
    def limit(conn, bucket):
        row = conn.execute('INSERT INTO hs_issuer_throttle(bucket,attempts) VALUES(%s,1) '
            'ON CONFLICT(bucket) DO UPDATE SET attempts=CASE WHEN hs_issuer_throttle.window_start '
            "< clock_timestamp()-interval '1 minute' THEN 1 ELSE hs_issuer_throttle.attempts+1 END, "
            'window_start=CASE WHEN hs_issuer_throttle.window_start '
            "< clock_timestamp()-interval '1 minute' THEN clock_timestamp() ELSE hs_issuer_throttle.window_start END RETURNING attempts", (bucket,)).fetchone()
        return row['attempts'] > 60

    def issue(self):
        # Route authorizes distributor credentials BEFORE invoking this method.
        with self.transaction() as conn:
            for _ in range(32):
                value = self.random_key()
                if len(wire.decode(value)) != 32:
                    raise IssuerError(503, 'ISSUER_UNAVAILABLE')
                identifier = uuid.uuid4()
                row = conn.execute('INSERT INTO hs_issuer_license(license_id,key_hash) VALUES(%s,%s) '
                    'ON CONFLICT(key_hash) DO NOTHING RETURNING license_id', (identifier, digest(value))).fetchone()
                if row:
                    return {'license_id': str(identifier), 'activation_key': value}
            raise IssuerError(503, 'ISSUER_UNAVAILABLE')

    def challenge(self, activation_key, installation_id, installation_public_key, platform):
        try:
            if len(wire.decode(activation_key)) != 32 or platform not in ('windows','ubuntu'):
                raise ValueError()
            installation_id = str(uuid.UUID(installation_id))
            public = wire.public(installation_public_key)
            key_id = wire.key_id(public)
        except (ValueError, TypeError, AttributeError):
            raise IssuerError(400, 'INVALID_REQUEST') from None
        error = None
        with self.transaction() as conn:
            if self.limit(conn, 'challenge'):
                error = IssuerError(429, 'RATE_LIMITED')
            else:
                row = conn.execute('SELECT license_id FROM hs_issuer_license WHERE key_hash=%s', (digest(activation_key),)).fetchone()
                if not row:
                    error = IssuerError(401, 'INVALID_ACTIVATION_KEY')
                else:
                    now = int(conn.execute('SELECT floor(extract(epoch FROM clock_timestamp())) AS now').fetchone()['now'])
                    document = dict(version=1, challenge_id=str(uuid.uuid4()), nonce=secrets.token_urlsafe(32),
                        license_id=str(row['license_id']), installation_id=installation_id, installation_key_id=key_id,
                        platform=platform, issued_at=now, expires_at=now+120)
                    conn.execute('INSERT INTO hs_issuer_challenge(challenge_id,license_id,installation_id,installation_key_id,'
                        'installation_public_key,platform,document,expires_at) VALUES(%s,%s,%s,%s,%s,%s,%s,%s)',
                        (document['challenge_id'], row['license_id'], installation_id, key_id,
                         installation_public_key, platform, Jsonb(document), now+120))
                    result = wire.sign(self.private_key, 'challenge', document)
        if error:
            raise error
        return result

    def activate(self, challenge, proof):
        try:
            document = wire.verify(challenge, 'challenge', self.keys, CHALLENGE_FIELDS)
            for field in ('challenge_id','license_id','installation_id'):
                uuid.UUID(document[field])
            if len(wire.decode(document['nonce'])) != 32 or document['platform'] not in ('windows','ubuntu'):
                raise ValueError()
            if document['expires_at'] - document['issued_at'] != 120:
                raise ValueError()
        except (ValueError, TypeError, KeyError, AttributeError, UnicodeError):
            raise IssuerError(401, 'INVALID_PROOF') from None
        error, result = None, None
        with self.transaction() as conn:
            if self.limit(conn, 'activate'):
                error = IssuerError(429, 'RATE_LIMITED')
            else:
                # Every activation takes locks in license -> challenge order.
                license_row = conn.execute('SELECT * FROM hs_issuer_license WHERE license_id=%s FOR UPDATE', (document['license_id'],)).fetchone()
                row = conn.execute('SELECT *,floor(extract(epoch FROM clock_timestamp())) AS now '
                    'FROM hs_issuer_challenge WHERE challenge_id=%s FOR UPDATE', (document['challenge_id'],)).fetchone()
                if not row or not license_row or row['document'] != document:
                    error = IssuerError(401, 'INVALID_PROOF')
                elif row['consumed_at']:
                    error = IssuerError(409, 'CHALLENGE_CONSUMED')
                elif row['now'] >= row['expires_at']:
                    error = IssuerError(410, 'CHALLENGE_EXPIRED')
                elif row['attempts'] >= 5:
                    error = IssuerError(429, 'RATE_LIMITED')
                else:
                    conn.execute('UPDATE hs_issuer_challenge SET attempts=attempts+1 WHERE challenge_id=%s', (document['challenge_id'],))
                    try:
                        key = wire.public(row['installation_public_key'])
                        proven = wire.verify(proof, 'activation-proof', {wire.key_id(key): key}, PROOF_FIELDS)
                        if proven != {field: document[field] for field in PROOF_FIELDS}:
                            raise ValueError()
                    except (ValueError, TypeError, KeyError, AttributeError, UnicodeError):
                        error = IssuerError(401, 'INVALID_PROOF')
                    if error is None:
                        bound = license_row['installation_id']
                        if bound is not None and (str(bound) != document['installation_id'] or
                            license_row['installation_key_id'] != document['installation_key_id'] or license_row['platform'] != document['platform']):
                            error = IssuerError(409, 'LICENSE_ALREADY_ACTIVATED')
                        else:
                            receipt = license_row['receipt']
                            if receipt is None:
                                receipt = wire.sign(self.private_key, 'receipt', dict(version=1, receipt_id=str(uuid.uuid4()),
                                    license_id=document['license_id'], installation_id=document['installation_id'],
                                    installation_key_id=document['installation_key_id'], installation_public_key=row['installation_public_key'],
                                    platform=document['platform'], activated_at=int(row['now']), issuer_key_id=wire.key_id(self.private_key.public_key())))
                                conn.execute('UPDATE hs_issuer_license SET installation_id=%s,installation_key_id=%s,'
                                    'installation_public_key=%s,platform=%s,receipt=%s WHERE license_id=%s',
                                    (document['installation_id'], document['installation_key_id'], row['installation_public_key'],
                                     document['platform'], Jsonb(receipt), document['license_id']))
                            conn.execute('UPDATE hs_issuer_challenge SET consumed_at=clock_timestamp() WHERE challenge_id=%s', (document['challenge_id'],))
                            result = {'status':'activated','receipt':receipt}
        if error:
            raise error
        return result
