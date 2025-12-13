-- Migration: Add role field to users table
-- Date: 2025-01-09
-- Description: Adds role field to users table for role-based access control

-- Add role column to users table
ALTER TABLE users 
ADD COLUMN IF NOT EXISTS role VARCHAR(50) DEFAULT 'cleaner';

-- Create index on role for faster queries
CREATE INDEX IF NOT EXISTS idx_users_role ON users(role);

-- Update existing users to have default role if NULL
UPDATE users 
SET role = 'cleaner' 
WHERE role IS NULL;

-- Add comment to column
COMMENT ON COLUMN users.role IS 'User role: project_lead, operations_manager, manager, supervisor, cleaner';

