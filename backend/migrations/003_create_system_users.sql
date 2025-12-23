-- Migration: Create system_users table for authentication
-- Date: 2025-01-09
-- Description: Creates table for system users (web interface authentication)

CREATE TABLE IF NOT EXISTS system_users (
    id SERIAL PRIMARY KEY,
    username VARCHAR(255) UNIQUE NOT NULL,
    email VARCHAR(255) UNIQUE,
    hashed_password VARCHAR(255) NOT NULL,
    full_name VARCHAR(255),
    role VARCHAR(50) NOT NULL DEFAULT 'cleaner',
    is_active BOOLEAN DEFAULT TRUE,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    last_login TIMESTAMP WITH TIME ZONE
);

-- Create indexes
CREATE INDEX IF NOT EXISTS idx_system_users_username ON system_users(username);
CREATE INDEX IF NOT EXISTS idx_system_users_email ON system_users(email);
CREATE INDEX IF NOT EXISTS idx_system_users_role ON system_users(role);

-- Note: Default admin user should be created using the script:
-- python scripts/create_admin_user.py
-- This ensures proper password hashing and avoids hardcoding credentials in migrations

COMMENT ON TABLE system_users IS 'System users for web interface authentication';
COMMENT ON COLUMN system_users.role IS 'User role: project_lead, operations_manager, manager, supervisor, cleaner';

