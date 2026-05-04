-- Add workspace_id column to all legacy tables that don't have it yet.
-- This is idempotent: safe to run multiple times.

DO $$
DECLARE
    tbl text;
    tables text[] := ARRAY[
        'leads', 'deals', 'campaigns', 'sequences', 'bookings',
        'phone_calls', 'proposals', 'payments', 'interactions',
        'app_settings'
    ];
BEGIN
    FOREACH tbl IN ARRAY tables
    LOOP
        IF EXISTS (
            SELECT 1 FROM information_schema.tables
            WHERE table_schema = 'public' AND table_name = tbl
        ) AND NOT EXISTS (
            SELECT 1 FROM information_schema.columns
            WHERE table_schema = 'public' AND table_name = tbl AND column_name = 'workspace_id'
        ) THEN
            EXECUTE format(
                'ALTER TABLE %I ADD COLUMN workspace_id VARCHAR(36) REFERENCES workspaces(id)',
                tbl
            );
            EXECUTE format(
                'CREATE INDEX IF NOT EXISTS %I ON %I (workspace_id)',
                'ix_' || tbl || '_workspace_id',
                tbl
            );
        END IF;
    END LOOP;
END $$;
