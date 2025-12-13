-- Migration: Create work_shifts and user_shift_assignments tables
-- Date: 2025-01-09
-- Description: Creates tables for work shifts and user shift assignments

-- Create work_shifts table
CREATE TABLE IF NOT EXISTS work_shifts (
    id SERIAL PRIMARY KEY,
    name VARCHAR(255) NOT NULL,
    description TEXT,
    schedule JSONB NOT NULL,
    is_active BOOLEAN DEFAULT TRUE,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

-- Create user_shift_assignments table
CREATE TABLE IF NOT EXISTS user_shift_assignments (
    id SERIAL PRIMARY KEY,
    user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    shift_id INTEGER NOT NULL REFERENCES work_shifts(id) ON DELETE CASCADE,
    start_date TIMESTAMP WITH TIME ZONE,
    end_date TIMESTAMP WITH TIME ZONE,
    is_active BOOLEAN DEFAULT TRUE,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

-- Create indexes
CREATE INDEX IF NOT EXISTS idx_work_shifts_is_active ON work_shifts(is_active);
CREATE INDEX IF NOT EXISTS idx_user_shift_assignments_user_id ON user_shift_assignments(user_id);
CREATE INDEX IF NOT EXISTS idx_user_shift_assignments_shift_id ON user_shift_assignments(shift_id);
CREATE INDEX IF NOT EXISTS idx_user_shift_assignments_is_active ON user_shift_assignments(is_active);

-- Add comments
COMMENT ON TABLE work_shifts IS 'Рабочие смены с настройкой по дням недели';
COMMENT ON COLUMN work_shifts.schedule IS 'JSON расписание по дням недели: {"0": {"start": "09:00", "end": "18:00", "enabled": true}, ...}';
COMMENT ON TABLE user_shift_assignments IS 'Привязка пользователей к рабочим сменам';

