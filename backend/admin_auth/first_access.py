"""V2 recovery sets. Caller holds the auth singleton transaction lock."""
import secrets
from .service import AuthError, token_hash


def status(conn, account_id):
    conn.execute('INSERT INTO hs_admin_recovery_set_v2(account_id,installation_id) SELECT id,installation_id FROM hs_admin_account WHERE id=%s ON CONFLICT DO NOTHING', (account_id,))
    row = conn.execute('SELECT * FROM hs_admin_recovery_set_v2 WHERE account_id=%s FOR UPDATE', (account_id,)).fetchone()
    remaining = conn.execute('SELECT count(*) AS n FROM hs_admin_recovery_v2 WHERE account_id=%s AND generation=%s AND used_at IS NULL AND revoked_at IS NULL', (account_id, row['generation'])).fetchone()['n']
    return dict(contract_version=2, status='completed' if row['confirmed_at'] else 'pending' if row['issued_at'] else 'not_issued', generation=row['generation'], codes_remaining=remaining, installation_id=str(row['installation_id']), account_id=account_id)


def issue(conn, account_id, *, reissue=False):
    current = status(conn, account_id)
    if current['generation'] and not reissue:
        error = AuthError(409, 'CODES_ALREADY_ISSUED')
        error.first_access = current
        raise error
    generation = current['generation'] + 1
    conn.execute('UPDATE hs_admin_recovery_v2 SET revoked_at=clock_timestamp() WHERE account_id=%s AND revoked_at IS NULL', (account_id,))
    for table in ('hs_admin_password_reset_code', 'hs_admin_recovery_code'):
        conn.execute(f'UPDATE {table} SET revoked_at=clock_timestamp() WHERE account_id=%s AND revoked_at IS NULL', (account_id,))
    codes = set()
    for _ in range(32):
        codes.add(secrets.token_urlsafe(24))
        if len(codes) == 3:
            break
    if len(codes) != 3:
        raise AuthError(503, 'AUTH_UNAVAILABLE')
    codes = list(codes)
    for slot, code in enumerate(codes, 1):
        conn.execute('INSERT INTO hs_admin_recovery_v2(account_id,installation_id,generation,slot,verifier) VALUES(%s,%s,%s,%s,%s)', (account_id, current['installation_id'], generation, slot, token_hash(code)))
    conn.execute('UPDATE hs_admin_recovery_set_v2 SET generation=%s,issued_at=clock_timestamp(),confirmed_at=NULL WHERE account_id=%s', (generation, account_id))
    return {'first_access': status(conn, account_id), 'recovery_codes': codes}


def confirm(conn, account_id, generation):
    current = status(conn, account_id)
    if type(generation) is not int or generation < 1 or current['generation'] != generation:
        raise AuthError(409, 'GENERATION_CONFLICT')
    conn.execute('UPDATE hs_admin_recovery_set_v2 SET confirmed_at=coalesce(confirmed_at,clock_timestamp()) WHERE account_id=%s', (account_id,))
    return status(conn, account_id)
