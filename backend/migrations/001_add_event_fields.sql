-- Миграция: Добавление новых полей в таблицу attendance_events
-- Дата: 2025-01-10
-- Описание: Расширение модели AttendanceEvent для хранения всех полей событий из ISAPI

-- Делаем user_id nullable (для системных событий без пользователя)
ALTER TABLE attendance_events 
    ALTER COLUMN user_id DROP NOT NULL;

-- Добавляем новые поля из ISAPI событий
ALTER TABLE attendance_events 
    ADD COLUMN IF NOT EXISTS employee_no VARCHAR,
    ADD COLUMN IF NOT EXISTS name VARCHAR,
    ADD COLUMN IF NOT EXISTS card_no VARCHAR,
    ADD COLUMN IF NOT EXISTS card_reader_id VARCHAR,
    ADD COLUMN IF NOT EXISTS event_type_code VARCHAR,
    ADD COLUMN IF NOT EXISTS event_type_description VARCHAR,
    ADD COLUMN IF NOT EXISTS remote_host_ip VARCHAR;

-- Создание индекса для employee_no для оптимизации запросов
CREATE INDEX IF NOT EXISTS ix_attendance_events_employee_no ON attendance_events(employee_no);

-- Комментарии к полям (опционально, для документации)
COMMENT ON COLUMN attendance_events.employee_no IS 'ID сотрудника из терминала Hikvision';
COMMENT ON COLUMN attendance_events.name IS 'Имя сотрудника из события';
COMMENT ON COLUMN attendance_events.card_no IS 'Номер карты доступа';
COMMENT ON COLUMN attendance_events.card_reader_id IS 'ID считывателя карт';
COMMENT ON COLUMN attendance_events.event_type_code IS 'Код типа события (majorEventType_subEventType)';
COMMENT ON COLUMN attendance_events.event_type_description IS 'Текстовое описание типа события';
COMMENT ON COLUMN attendance_events.remote_host_ip IS 'IP адрес удаленного хоста';

