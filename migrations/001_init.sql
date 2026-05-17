CREATE EXTENSION IF NOT EXISTS citext;
CREATE EXTENSION IF NOT EXISTS pgcrypto;

CREATE TABLE IF NOT EXISTS users (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    email CITEXT UNIQUE NOT NULL,
    password_hash TEXT NOT NULL,
    is_active BOOLEAN NOT NULL DEFAULT FALSE,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    activated_at TIMESTAMPTZ,
    CONSTRAINT users_email_not_empty CHECK (length(trim(email::text)) > 0),
    CONSTRAINT users_activation_consistency CHECK (
        (is_active = FALSE AND activated_at IS NULL)
        OR (is_active = TRUE AND activated_at IS NOT NULL)
    )
);

CREATE TABLE IF NOT EXISTS activation_codes (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    code CHAR(4) NOT NULL,
    expires_at TIMESTAMPTZ NOT NULL,
    used_at TIMESTAMPTZ,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    CONSTRAINT activation_codes_code_format CHECK (code ~ '^[0-9]{4}$'),
    CONSTRAINT activation_codes_expires_after_created CHECK (expires_at > created_at),
    CONSTRAINT activation_codes_used_after_created CHECK (
        used_at IS NULL OR used_at >= created_at
    )
);

CREATE INDEX IF NOT EXISTS activation_codes_user_id_created_at_idx
    ON activation_codes (user_id, created_at DESC);

CREATE INDEX IF NOT EXISTS activation_codes_user_id_unused_created_at_idx
    ON activation_codes (user_id, created_at DESC)
    WHERE used_at IS NULL;
