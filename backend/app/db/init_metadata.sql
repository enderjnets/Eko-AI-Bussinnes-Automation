-- Idempotent metadata engine schema setup
-- Safe to run multiple times

CREATE TABLE IF NOT EXISTS object_metadata (
    id VARCHAR(36) PRIMARY KEY DEFAULT gen_random_uuid(),
    workspace_id VARCHAR(36),
    name_singular VARCHAR(255) NOT NULL,
    name_plural VARCHAR(255) NOT NULL,
    label_singular VARCHAR(255) NOT NULL,
    label_plural VARCHAR(255) NOT NULL,
    description TEXT,
    icon VARCHAR(100),
    color VARCHAR(20),
    target_table_name VARCHAR(255),
    is_custom BOOLEAN DEFAULT FALSE,
    is_system BOOLEAN DEFAULT FALSE,
    is_active BOOLEAN DEFAULT TRUE,
    is_searchable BOOLEAN DEFAULT TRUE,
    position INTEGER DEFAULT 0,
    duplicate_criteria JSONB,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW(),
    CONSTRAINT uq_object_name_singular_workspace UNIQUE (name_singular, workspace_id),
    CONSTRAINT uq_object_name_plural_workspace UNIQUE (name_plural, workspace_id)
);

-- Note: ix_object_metadata_workspace_id and ix_object_metadata_name_singular
-- are defined in the SQLAlchemy model (ObjectMetadata.__table_args__)
-- and created automatically by Base.metadata.create_all().

CREATE TABLE IF NOT EXISTS field_metadata (
    id VARCHAR(36) PRIMARY KEY DEFAULT gen_random_uuid(),
    workspace_id VARCHAR(36),
    object_metadata_id VARCHAR(36) NOT NULL REFERENCES object_metadata(id) ON DELETE CASCADE,
    name VARCHAR(255) NOT NULL,
    label VARCHAR(255) NOT NULL,
    type VARCHAR(50) NOT NULL,
    description TEXT,
    icon VARCHAR(100),
    default_value JSONB,
    options JSONB,
    settings JSONB,
    is_custom BOOLEAN DEFAULT FALSE,
    is_system BOOLEAN DEFAULT FALSE,
    is_active BOOLEAN DEFAULT TRUE,
    is_nullable BOOLEAN DEFAULT TRUE,
    is_unique BOOLEAN DEFAULT FALSE,
    is_read_only BOOLEAN DEFAULT FALSE,
    is_label_field BOOLEAN DEFAULT FALSE,
    position INTEGER DEFAULT 0,
    relation_target_object_id VARCHAR(36) REFERENCES object_metadata(id) ON DELETE SET NULL,
    relation_target_field_id VARCHAR(36),
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW(),
    CONSTRAINT uq_field_name_object_workspace UNIQUE (object_metadata_id, name, workspace_id)
);

-- Note: field_metadata indexes are defined in the SQLAlchemy model

CREATE TABLE IF NOT EXISTS dynamic_records (
    id VARCHAR(36) PRIMARY KEY DEFAULT gen_random_uuid(),
    workspace_id VARCHAR(36),
    object_metadata_id VARCHAR(36) NOT NULL REFERENCES object_metadata(id) ON DELETE CASCADE,
    label VARCHAR(500) NOT NULL DEFAULT '',
    data JSONB NOT NULL DEFAULT '{}',
    search_vector TEXT,
    deleted_at TIMESTAMPTZ,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

-- Note: dynamic_records indexes are defined in the SQLAlchemy model

-- Views engine
CREATE TABLE IF NOT EXISTS views (
    id VARCHAR(36) PRIMARY KEY DEFAULT gen_random_uuid(),
    workspace_id VARCHAR(36),
    object_metadata_id VARCHAR(36) NOT NULL REFERENCES object_metadata(id) ON DELETE CASCADE,
    name VARCHAR(255) NOT NULL DEFAULT '',
    type VARCHAR(50) NOT NULL DEFAULT 'table',
    icon VARCHAR(100) NOT NULL DEFAULT 'IconList',
    position FLOAT NOT NULL DEFAULT 0,
    is_default BOOLEAN DEFAULT FALSE,
    is_compact BOOLEAN DEFAULT FALSE,
    is_system BOOLEAN DEFAULT FALSE,
    group_by_field_id VARCHAR(36) REFERENCES field_metadata(id) ON DELETE SET NULL,
    calendar_field_id VARCHAR(36) REFERENCES field_metadata(id) ON DELETE SET NULL,
    visibility VARCHAR(50) NOT NULL DEFAULT 'workspace',
    created_by_user_id INTEGER,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

-- Note: views indexes are defined in the SQLAlchemy model

CREATE TABLE IF NOT EXISTS view_fields (
    id VARCHAR(36) PRIMARY KEY DEFAULT gen_random_uuid(),
    view_id VARCHAR(36) NOT NULL REFERENCES views(id) ON DELETE CASCADE,
    field_metadata_id VARCHAR(36) NOT NULL REFERENCES field_metadata(id) ON DELETE CASCADE,
    position FLOAT DEFAULT 0,
    is_visible BOOLEAN DEFAULT TRUE,
    width INTEGER,
    UNIQUE(view_id, field_metadata_id)
);

CREATE TABLE IF NOT EXISTS view_filters (
    id VARCHAR(36) PRIMARY KEY DEFAULT gen_random_uuid(),
    view_id VARCHAR(36) NOT NULL REFERENCES views(id) ON DELETE CASCADE,
    field_metadata_id VARCHAR(36) NOT NULL REFERENCES field_metadata(id) ON DELETE CASCADE,
    operator VARCHAR(50) NOT NULL,
    value JSONB,
    display_value TEXT
);

CREATE TABLE IF NOT EXISTS view_sorts (
    id VARCHAR(36) PRIMARY KEY DEFAULT gen_random_uuid(),
    view_id VARCHAR(36) NOT NULL REFERENCES views(id) ON DELETE CASCADE,
    field_metadata_id VARCHAR(36) NOT NULL REFERENCES field_metadata(id) ON DELETE CASCADE,
    direction VARCHAR(10) NOT NULL DEFAULT 'asc'
);
