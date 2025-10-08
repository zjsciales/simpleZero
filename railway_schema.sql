-- SimpleZero PostgreSQL Schema - Copy & Paste into Railway
-- This creates the complete production database structure

-- Trades table for core trading data
CREATE TABLE IF NOT EXISTS trades (
    id SERIAL PRIMARY KEY,
    trade_id VARCHAR(50) UNIQUE NOT NULL,
    ticker VARCHAR(10) NOT NULL DEFAULT 'SPY',
    strategy_type VARCHAR(50) NOT NULL,
    dte INTEGER NOT NULL,
    entry_date TIMESTAMP NOT NULL,
    expiration_date DATE NOT NULL,
    short_strike DECIMAL(10,2) NOT NULL,
    long_strike DECIMAL(10,2) NOT NULL,
    quantity INTEGER NOT NULL DEFAULT 1,
    entry_premium_received DECIMAL(10,2),
    entry_premium_paid DECIMAL(10,2),
    entry_underlying_price DECIMAL(10,2) NOT NULL,
    exit_date TIMESTAMP NULL,
    exit_premium_paid DECIMAL(10,2) NULL,
    exit_premium_received DECIMAL(10,2) NULL,
    exit_underlying_price DECIMAL(10,2) NULL,
    status VARCHAR(20) NOT NULL DEFAULT 'OPEN',
    is_winner BOOLEAN NULL,
    net_premium DECIMAL(10,2) NULL,
    roi_percentage DECIMAL(5,2) NULL,
    current_underlying_price DECIMAL(10,2) NULL,
    current_itm_status VARCHAR(10) NULL,
    last_price_update TIMESTAMP NULL,
    grok_confidence INTEGER NULL,
    market_conditions TEXT NULL,
    notes TEXT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Grok analyses table for AI trading insights
CREATE TABLE IF NOT EXISTS grok_analyses (
    id SERIAL PRIMARY KEY,
    analysis_id VARCHAR(100) UNIQUE NOT NULL,
    ticker VARCHAR(10) NOT NULL DEFAULT 'SPY',
    dte INTEGER NOT NULL,
    analysis_date TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    underlying_price DECIMAL(10,2) NOT NULL,
    prompt_text TEXT NOT NULL,
    response_text TEXT NOT NULL,
    include_sentiment BOOLEAN DEFAULT TRUE,
    confidence_score INTEGER NULL,
    recommended_strategy VARCHAR(100) NULL,
    market_outlook VARCHAR(50) NULL,
    key_levels TEXT NULL,
    related_trade_id VARCHAR(50) NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Performance metrics for public scoreboard
CREATE TABLE IF NOT EXISTS performance_metrics (
    id SERIAL PRIMARY KEY,
    period_type VARCHAR(20) NOT NULL,
    period_start DATE NOT NULL,
    period_end DATE NOT NULL,
    total_trades INTEGER NOT NULL DEFAULT 0,
    winning_trades INTEGER NOT NULL DEFAULT 0,
    losing_trades INTEGER NOT NULL DEFAULT 0,
    total_profit_loss DECIMAL(12,2) NOT NULL DEFAULT 0.00,
    win_rate_percentage DECIMAL(5,2) NOT NULL DEFAULT 0.00,
    average_roi DECIMAL(5,2) NULL,
    best_trade_roi DECIMAL(5,2) NULL,
    worst_trade_roi DECIMAL(5,2) NULL,
    total_premium_collected DECIMAL(12,2) NULL,
    sharpe_ratio DECIMAL(5,3) NULL,
    max_drawdown_percentage DECIMAL(5,2) NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(period_type, period_start, period_end)
);

-- Market snapshots for historical data
CREATE TABLE IF NOT EXISTS market_snapshots (
    id SERIAL PRIMARY KEY,
    ticker VARCHAR(10) NOT NULL DEFAULT 'SPY',
    snapshot_date TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    current_price DECIMAL(10,2) NOT NULL,
    daily_change DECIMAL(10,2) NULL,
    daily_change_percent DECIMAL(5,2) NULL,
    volume BIGINT NULL,
    implied_volatility DECIMAL(5,2) NULL,
    vix_level DECIMAL(5,2) NULL,
    market_sentiment VARCHAR(20) NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Create indexes for better performance
CREATE INDEX IF NOT EXISTS idx_trades_ticker_dte ON trades(ticker, dte);
CREATE INDEX IF NOT EXISTS idx_trades_entry_date ON trades(entry_date);
CREATE INDEX IF NOT EXISTS idx_trades_status ON trades(status);
CREATE INDEX IF NOT EXISTS idx_grok_analyses_ticker_date ON grok_analyses(ticker, analysis_date);
CREATE INDEX IF NOT EXISTS idx_performance_metrics_period ON performance_metrics(period_type, period_start);
CREATE INDEX IF NOT EXISTS idx_market_snapshots_ticker_date ON market_snapshots(ticker, snapshot_date);

-- Insert initial performance metrics
INSERT INTO performance_metrics (
    period_type, period_start, period_end,
    total_trades, winning_trades, losing_trades,
    total_profit_loss, win_rate_percentage
) VALUES 
('all_time', '2024-01-01', CURRENT_DATE, 0, 0, 0, 0.00, 0.00),
('monthly', DATE_TRUNC('month', CURRENT_DATE), CURRENT_DATE, 0, 0, 0, 0.00, 0.00),
('weekly', DATE_TRUNC('week', CURRENT_DATE), CURRENT_DATE, 0, 0, 0, 0.00, 0.00)
ON CONFLICT (period_type, period_start, period_end) DO NOTHING;

-- Create a view for easy scoreboard queries
CREATE OR REPLACE VIEW public_scoreboard AS
SELECT 
    pm.period_type,
    pm.total_trades,
    pm.winning_trades,
    pm.losing_trades,
    pm.win_rate_percentage,
    pm.total_profit_loss,
    pm.average_roi,
    pm.best_trade_roi,
    pm.worst_trade_roi,
    COUNT(t.id) as live_trades_count
FROM performance_metrics pm
LEFT JOIN trades t ON t.status = 'OPEN'
WHERE pm.period_type = 'all_time'
GROUP BY pm.id, pm.period_type, pm.total_trades, pm.winning_trades, 
         pm.losing_trades, pm.win_rate_percentage, pm.total_profit_loss,
         pm.average_roi, pm.best_trade_roi, pm.worst_trade_roi;

-- Success message
SELECT 'SimpleZero PostgreSQL schema created successfully! 🎉' as status;