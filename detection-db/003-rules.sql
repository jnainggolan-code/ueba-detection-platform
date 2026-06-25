-- custom_rules table for Rule Engine
CREATE TABLE IF NOT EXISTS custom_rules (
    id SERIAL PRIMARY KEY,
    name VARCHAR(255) NOT NULL,
    description TEXT,
    conditions JSONB NOT NULL DEFAULT '{}',
    action JSONB NOT NULL DEFAULT '{}',
    enabled BOOLEAN DEFAULT true,
    priority INTEGER DEFAULT 0,
    created_at TIMESTAMPTZ DEFAULT now(),
    updated_at TIMESTAMPTZ DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_custom_rules_enabled ON custom_rules(enabled);
CREATE INDEX IF NOT EXISTS idx_custom_rules_priority ON custom_rules(priority DESC);
