-- Migration: Add device grouping and user-device sync tracking
-- Date: 2025-12-23
-- Description: Adds device_type, location, priority to devices table and creates user_device_sync table for many-to-many relationship

-- Add new fields to devices table
ALTER TABLE devices ADD COLUMN IF NOT EXISTS device_type VARCHAR(20) DEFAULT 'other';
ALTER TABLE devices ADD COLUMN IF NOT EXISTS location VARCHAR(200);
ALTER TABLE devices ADD COLUMN IF NOT EXISTS priority INTEGER DEFAULT 0;

-- Add comments for new device fields
COMMENT ON COLUMN devices.device_type IS 'Тип терминала: entry (вход), exit (выход), both (оба), other (другое)';
COMMENT ON COLUMN devices.location IS 'Местоположение терминала (например, "Главный вход", "Офис 2 этаж")';
COMMENT ON COLUMN devices.priority IS 'Приоритет синхронизации (больше число = выше приоритет)';

-- Create user_device_sync table for tracking which users are synced to which devices
CREATE TABLE IF NOT EXISTS user_device_sync (
    id SERIAL PRIMARY KEY,
    user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    device_id INTEGER NOT NULL REFERENCES devices(id) ON DELETE CASCADE,
    sync_status VARCHAR(20) DEFAULT 'pending',
    last_sync_at TIMESTAMP WITH TIME ZONE,
    error_message TEXT,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT unique_user_device UNIQUE (user_id, device_id)
);

-- Create indexes for performance
CREATE INDEX IF NOT EXISTS idx_user_device_sync_user_id ON user_device_sync(user_id);
CREATE INDEX IF NOT EXISTS idx_user_device_sync_device_id ON user_device_sync(device_id);
CREATE INDEX IF NOT EXISTS idx_user_device_sync_status ON user_device_sync(sync_status);
CREATE INDEX IF NOT EXISTS idx_devices_type ON devices(device_type);
CREATE INDEX IF NOT EXISTS idx_devices_active_type ON devices(is_active, device_type);

-- Add comments
COMMENT ON TABLE user_device_sync IS 'Отслеживание синхронизации пользователей с терминалами (многие-ко-многим)';
COMMENT ON COLUMN user_device_sync.sync_status IS 'Статус синхронизации: pending (ожидает), syncing (в процессе), synced (синхронизирован), failed (ошибка)';
COMMENT ON COLUMN user_device_sync.last_sync_at IS 'Время последней успешной синхронизации';
COMMENT ON COLUMN user_device_sync.error_message IS 'Сообщение об ошибке при неудачной синхронизации';

