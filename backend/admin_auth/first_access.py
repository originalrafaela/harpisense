"""Account-scoped onboarding metadata. Original reset codes are never stored."""
import secrets

from .service import AuthError,token_hash


def status(conn,account_id):
    conn.execute('INSERT INTO hs_admin_first_access(account_id) VALUES(%s) ON CONFLICT DO NOTHING',(account_id,))
    row=conn.execute('SELECT * FROM hs_admin_first_access WHERE account_id=%s',(account_id,)).fetchone()
    return {'status':'completed' if row['completed_at'] is not None else 'pending',
        'password_reset_generation':row['password_reset_generation'],
        'password_reset_purpose':'password_reset',
        'codes_issued':row['issued_at'] is not None,
        'issued_at':row['issued_at'].isoformat() if row['issued_at'] is not None else None,
        'completed_at':row['completed_at'].isoformat() if row['completed_at'] is not None else None}


def issue_password_reset_codes(conn,account_id):
    # Caller holds the existing auth singleton row lock. Revocation, issuance,
    # generation and pending state commit together, including the audit event.
    conn.execute('INSERT INTO hs_admin_first_access(account_id) VALUES(%s) ON CONFLICT DO NOTHING',(account_id,))
    generation=conn.execute('UPDATE hs_admin_first_access SET password_reset_generation=password_reset_generation+1, '
        'issued_at=clock_timestamp(),completed_at=NULL WHERE account_id=%s RETURNING password_reset_generation',
        (account_id,)).fetchone()['password_reset_generation']
    conn.execute('UPDATE hs_admin_password_reset_code SET revoked_at=clock_timestamp() '
                 'WHERE account_id=%s AND revoked_at IS NULL',(account_id,))
    codes=[secrets.token_urlsafe(24) for _ in range(10)]
    for value in codes:
        conn.execute('INSERT INTO hs_admin_password_reset_code(code_hash,account_id,generation,purpose) '
                     "VALUES(%s,%s,%s,'password_reset')",(token_hash(value),account_id,generation))
    return codes


def confirm(conn,account_id,generation):
    current=status(conn,account_id)
    if (type(generation) is not int or generation<1 or not current['codes_issued']
            or current['password_reset_generation']!=generation):
        raise AuthError(409,'FIRST_ACCESS_GENERATION_CONFLICT')
    conn.execute('UPDATE hs_admin_first_access SET completed_at=coalesce(completed_at,clock_timestamp()) '
                 'WHERE account_id=%s',(account_id,))
    return status(conn,account_id)


def issue_authenticator_recovery_codes(conn,account_id,generation):
    conn.execute('UPDATE hs_admin_recovery_code SET revoked_at=clock_timestamp() '
                 'WHERE account_id=%s AND revoked_at IS NULL',(account_id,))
    codes=[secrets.token_urlsafe(24) for _ in range(10)]
    for value in codes:
        conn.execute('INSERT INTO hs_admin_recovery_code(code_hash,account_id,purpose,issued_at,generation) '
                     "VALUES(%s,%s,'authenticator_recovery',clock_timestamp(),%s)",
                     (token_hash(value),account_id,generation))
    return codes
