-- Row-Level Security policies for workspace isolation
-- These are applied as a safety net even if application code forgets the filter.

-- Helper: set app.current_workspace_id before any query to enable RLS filtering.
-- The application does this via: SET LOCAL app.current_workspace_id = '...';

DO $$
DECLARE
    tbl text;
    tables text[] := ARRAY[
        'leads', 'deals', 'campaigns', 'sequences', 'bookings',
        'phone_calls', 'proposals', 'payments', 'interactions',
        'app_settings', 'object_metadata', 'field_metadata',
        'dynamic_records', 'views', 'view_fields', 'view_filters', 'view_sorts'
    ];
BEGIN
    FOREACH tbl IN ARRAY tables
    LOOP
        -- Only if table exists and has workspace_id column
        IF EXISTS (
            SELECT 1 FROM information_schema.tables
            WHERE table_schema = 'public' AND table_name = tbl
        ) AND EXISTS (
            SELECT 1 FROM information_schema.columns
            WHERE table_schema = 'public' AND table_name = tbl AND column_name = 'workspace_id'
        ) THEN
            EXECUTE format('ALTER TABLE %I ENABLE ROW LEVEL SECURITY', tbl);
            EXECUTE format('ALTER TABLE %I FORCE ROW LEVEL SECURITY', tbl);

            -- Drop existing policy if any to avoid duplicates
            EXECUTE format(
                'DROP POLICY IF EXISTS %I ON %I',
                tbl || '_tenant_isolation',
                tbl
            );

            EXECUTE format(
                'CREATE POLICY %I ON %I USING (workspace_id = current_setting(''app.current_workspace_id'', true))',
                tbl || '_tenant_isolation',
                tbl
            );
        END IF;
    END LOOP;
END $$;
