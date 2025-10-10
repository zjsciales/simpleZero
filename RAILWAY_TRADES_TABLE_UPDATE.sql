-- SQL commands to add missing columns to Railway trades table
-- Run these in your Railway PostgreSQL console

-- Add the 8 new columns to the trades table
ALTER TABLE trades ADD COLUMN IF NOT EXISTS max_loss DECIMAL(10,2);
ALTER TABLE trades ADD COLUMN IF NOT EXISTS prob_prof DECIMAL(5,2);
ALTER TABLE trades ADD COLUMN IF NOT EXISTS risk_reward DECIMAL(10,2);
ALTER TABLE trades ADD COLUMN IF NOT EXISTS net_delta DECIMAL(8,4);
ALTER TABLE trades ADD COLUMN IF NOT EXISTS net_theta DECIMAL(8,4);
ALTER TABLE trades ADD COLUMN IF NOT EXISTS analysis_id VARCHAR(255);
ALTER TABLE trades ADD COLUMN IF NOT EXISTS prompt_text TEXT;
ALTER TABLE trades ADD COLUMN IF NOT EXISTS response_text TEXT;

-- Optional: Add index on analysis_id for better performance
CREATE INDEX IF NOT EXISTS idx_trades_analysis_id ON trades(analysis_id);

-- Verify the new columns were added
SELECT column_name, data_type 
FROM information_schema.columns 
WHERE table_name = 'trades' 
ORDER BY ordinal_position;