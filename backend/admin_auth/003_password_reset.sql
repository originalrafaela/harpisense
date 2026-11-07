-- Separate purpose: these codes never satisfy MFA or create a session.
CREATE TABLE IF NOT EXISTS hs_admin_password_reset_code (
    code_hash text PRIMARY KEY,
    account_id integer NOT NULL REFERENCES hs_admin_account(id),
    created_at timestamptz NOT NULL DEFAULT clock_timestamp(),
    used_at timestamptz
);
