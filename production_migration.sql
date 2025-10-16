-- Production Database Migration Script
-- Add missing status column to requests table
-- Run this in Railway PostgreSQL console

-- Check if status column exists (this will fail if it doesn't exist, which is expected)
-- DO $$
-- BEGIN
--     IF NOT EXISTS (
--         SELECT 1 FROM information_schema.columns 
--         WHERE table_name = 'requests' AND column_name = 'status'
--     ) THEN
        ALTER TABLE requests ADD COLUMN status VARCHAR(20) NOT NULL DEFAULT 'PENDING';
--     END IF;
-- END $$;

-- Verify the column was added
SELECT column_name, data_type, is_nullable, column_default 
FROM information_schema.columns 
WHERE table_name = 'requests' 
ORDER BY ordinal_position;

-- Show current requests table structure
\d requests;