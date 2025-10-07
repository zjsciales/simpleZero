-- SimpleZero Public Trading Library Database Schema
-- PostgreSQL Database for Railway Deployment

-- =============================================================================
-- TRADES TABLE - Core trade data and performance tracking
-- =============================================================================
CREATE TABLE IF NOT EXISTS trades (
    id SERIAL PRIMARY KEY,
    trade_id VARCHAR(50) UNIQUE NOT NULL,
    
    -- Trade Identification
    ticker VARCHAR(10) NOT NULL DEFAULT 'SPY',
    strategy_type VARCHAR(50) NOT NULL, -- 'Bull Put Spread', 'Bear Call Spread', etc.
    dte INTEGER NOT NULL, -- Days to expiration when opened
    
    -- Trade Setup
    entry_date TIMESTAMP NOT NULL,
    expiration_date DATE NOT NULL,
    short_strike DECIMAL(10,2) NOT NULL,
    long_strike DECIMAL(10,2) NOT NULL,
    quantity INTEGER NOT NULL DEFAULT 1,
    
    -- Entry Financials
    entry_premium_received DECIMAL(10,2), -- For credit spreads
    entry_premium_paid DECIMAL(10,2), -- For debit spreads
    entry_underlying_price DECIMAL(10,2) NOT NULL,
    
    -- Exit Financials (NULL if still open)
    exit_date TIMESTAMP NULL,
    exit_premium_paid DECIMAL(10,2) NULL, -- To close credit spreads
    exit_premium_received DECIMAL(10,2) NULL, -- To close debit spreads
    exit_underlying_price DECIMAL(10,2) NULL,
    
    -- Trade Status
    status VARCHAR(20) NOT NULL DEFAULT 'OPEN', -- 'OPEN', 'CLOSED', 'EXPIRED'
    is_winner BOOLEAN NULL, -- NULL for open trades, TRUE/FALSE for closed
    
    -- Profitability Calculations
    net_premium DECIMAL(10,2) NULL, -- Final profit/loss
    roi_percentage DECIMAL(5,2) NULL, -- Return on investment %
    
    -- Current Status (for open trades)
    current_underlying_price DECIMAL(10,2) NULL,
    current_itm_status VARCHAR(10) NULL, -- 'ITM', 'OTM', 'ATM'
    last_price_update TIMESTAMP NULL,
    
    -- Confidence and Analysis
    grok_confidence INTEGER NULL, -- 1-100 confidence score from Grok
    market_conditions TEXT NULL, -- Brief description of market when opened
    
    -- Metadata
    source VARCHAR(20) DEFAULT 'automated', -- 'automated', 'manual', 'backtest'
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- =============================================================================
-- GROK_ANALYSES TABLE - Store all Grok prompts and responses
-- =============================================================================
CREATE TABLE IF NOT EXISTS grok_analyses (
    id SERIAL PRIMARY KEY,
    analysis_id VARCHAR(50) UNIQUE NOT NULL,
    
    -- Analysis Details
    ticker VARCHAR(10) NOT NULL DEFAULT 'SPY',
    dte INTEGER NOT NULL,
    analysis_date TIMESTAMP NOT NULL,
    
    -- Grok Interaction
    prompt_text TEXT NOT NULL,
    response_text TEXT NOT NULL,
    include_sentiment BOOLEAN DEFAULT FALSE,
    
    -- Market Data Context
    underlying_price DECIMAL(10,2) NOT NULL,
    market_conditions JSONB NULL, -- Store technical indicators, VIX, etc.
    
    -- Parsed Trade Recommendation
    recommended_strategy VARCHAR(50) NULL,
    recommended_strikes JSONB NULL, -- Array of strike prices
    confidence_score INTEGER NULL, -- 1-100
    
    -- Associated Trade (if executed)
    executed_trade_id VARCHAR(50) NULL,
    
    -- Public Display
    is_featured BOOLEAN DEFAULT FALSE, -- For highlighting in public library
    public_title VARCHAR(200) NULL, -- Custom title for public display
    
    -- Metadata
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    
    FOREIGN KEY (executed_trade_id) REFERENCES trades(trade_id)
);

-- =============================================================================
-- MARKET_SNAPSHOTS TABLE - Cache current market data for public display
-- =============================================================================
CREATE TABLE IF NOT EXISTS market_snapshots (
    id SERIAL PRIMARY KEY,
    
    -- Market Data
    spy_price DECIMAL(10,2) NOT NULL,
    spy_change DECIMAL(10,2) NOT NULL,
    spy_change_percent DECIMAL(5,2) NOT NULL,
    
    -- Market Indices
    spx_price DECIMAL(10,2) NULL,
    qqq_price DECIMAL(10,2) NULL,
    vix_level DECIMAL(5,2) NULL,
    
    -- Options Activity
    total_spy_volume BIGINT NULL,
    put_call_ratio DECIMAL(5,3) NULL,
    
    -- Timestamp
    snapshot_time TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    
    -- Cache Control
    is_market_open BOOLEAN NOT NULL,
    data_source VARCHAR(20) DEFAULT 'tastytrade'
);

-- =============================================================================
-- PERFORMANCE_METRICS TABLE - Aggregate performance stats for scoreboard
-- =============================================================================
CREATE TABLE IF NOT EXISTS performance_metrics (
    id SERIAL PRIMARY KEY,
    
    -- Time Period
    period_type VARCHAR(20) NOT NULL, -- 'daily', 'weekly', 'monthly', 'all_time'
    period_start DATE NOT NULL,
    period_end DATE NOT NULL,
    
    -- Trade Counts
    total_trades INTEGER NOT NULL DEFAULT 0,
    winning_trades INTEGER NOT NULL DEFAULT 0,
    losing_trades INTEGER NOT NULL DEFAULT 0,
    
    -- Financial Performance
    total_premium_collected DECIMAL(12,2) NOT NULL DEFAULT 0,
    total_profit_loss DECIMAL(12,2) NOT NULL DEFAULT 0,
    win_rate_percentage DECIMAL(5,2) NOT NULL DEFAULT 0,
    
    -- Average Performance
    avg_trade_profit DECIMAL(10,2) NULL,
    avg_win_amount DECIMAL(10,2) NULL,
    avg_loss_amount DECIMAL(10,2) NULL,
    
    -- Risk Metrics
    largest_win DECIMAL(10,2) NULL,
    largest_loss DECIMAL(10,2) NULL,
    max_drawdown DECIMAL(10,2) NULL,
    
    -- Strategy Breakdown
    strategy_performance JSONB NULL, -- Performance by strategy type
    
    -- Last Updated
    calculated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    
    UNIQUE(period_type, period_start, period_end)
);

-- =============================================================================
-- INDICES FOR PERFORMANCE
-- =============================================================================
CREATE INDEX IF NOT EXISTS idx_trades_status ON trades(status);
CREATE INDEX IF NOT EXISTS idx_trades_entry_date ON trades(entry_date);
CREATE INDEX IF NOT EXISTS idx_trades_ticker_dte ON trades(ticker, dte);
CREATE INDEX IF NOT EXISTS idx_grok_analyses_date ON grok_analyses(analysis_date);
CREATE INDEX IF NOT EXISTS idx_grok_analyses_ticker_dte ON grok_analyses(ticker, dte);
CREATE INDEX IF NOT EXISTS idx_market_snapshots_time ON market_snapshots(snapshot_time);
CREATE INDEX IF NOT EXISTS idx_performance_metrics_period ON performance_metrics(period_type, period_start);

-- =============================================================================
-- VIEWS FOR COMMON QUERIES
-- =============================================================================

-- Current open trades with ITM/OTM status
CREATE OR REPLACE VIEW open_trades_status AS
SELECT 
    t.*,
    CASE 
        WHEN t.strategy_type LIKE '%Put%' THEN 
            CASE WHEN t.current_underlying_price < t.short_strike THEN 'ITM' ELSE 'OTM' END
        WHEN t.strategy_type LIKE '%Call%' THEN 
            CASE WHEN t.current_underlying_price > t.short_strike THEN 'ITM' ELSE 'OTM' END
        ELSE 'UNKNOWN'
    END as itm_otm_status,
    EXTRACT(DAYS FROM (t.expiration_date - CURRENT_DATE)) as days_to_expiration
FROM trades t 
WHERE t.status = 'OPEN'
ORDER BY t.entry_date DESC;

-- Recent performance summary
CREATE OR REPLACE VIEW recent_performance AS
SELECT 
    COUNT(*) as total_trades,
    COUNT(CASE WHEN is_winner = TRUE THEN 1 END) as winning_trades,
    COUNT(CASE WHEN is_winner = FALSE THEN 1 END) as losing_trades,
    ROUND(
        (COUNT(CASE WHEN is_winner = TRUE THEN 1 END) * 100.0 / 
         NULLIF(COUNT(CASE WHEN is_winner IS NOT NULL THEN 1 END), 0)), 1
    ) as win_rate_percentage,
    COALESCE(SUM(net_premium), 0) as total_profit_loss,
    COUNT(CASE WHEN status = 'OPEN' THEN 1 END) as open_trades
FROM trades 
WHERE entry_date >= CURRENT_DATE - INTERVAL '30 days';

-- =============================================================================
-- FUNCTIONS FOR DATA MANAGEMENT
-- =============================================================================

-- Function to update trade performance metrics
CREATE OR REPLACE FUNCTION update_performance_metrics()
RETURNS VOID AS $$
BEGIN
    -- Update all-time metrics
    INSERT INTO performance_metrics (
        period_type, period_start, period_end,
        total_trades, winning_trades, losing_trades,
        total_profit_loss, win_rate_percentage
    )
    SELECT 
        'all_time',
        MIN(entry_date::date),
        CURRENT_DATE,
        COUNT(*),
        COUNT(CASE WHEN is_winner = TRUE THEN 1 END),
        COUNT(CASE WHEN is_winner = FALSE THEN 1 END),
        COALESCE(SUM(net_premium), 0),
        ROUND(
            (COUNT(CASE WHEN is_winner = TRUE THEN 1 END) * 100.0 / 
             NULLIF(COUNT(CASE WHEN is_winner IS NOT NULL THEN 1 END), 0)), 2
        )
    FROM trades
    WHERE is_winner IS NOT NULL
    ON CONFLICT (period_type, period_start, period_end) 
    DO UPDATE SET
        total_trades = EXCLUDED.total_trades,
        winning_trades = EXCLUDED.winning_trades,
        losing_trades = EXCLUDED.losing_trades,
        total_profit_loss = EXCLUDED.total_profit_loss,
        win_rate_percentage = EXCLUDED.win_rate_percentage,
        calculated_at = CURRENT_TIMESTAMP;
        
    -- Update monthly metrics for current month
    INSERT INTO performance_metrics (
        period_type, period_start, period_end,
        total_trades, winning_trades, losing_trades,
        total_profit_loss, win_rate_percentage
    )
    SELECT 
        'monthly',
        DATE_TRUNC('month', CURRENT_DATE)::date,
        (DATE_TRUNC('month', CURRENT_DATE) + INTERVAL '1 month - 1 day')::date,
        COUNT(*),
        COUNT(CASE WHEN is_winner = TRUE THEN 1 END),
        COUNT(CASE WHEN is_winner = FALSE THEN 1 END),
        COALESCE(SUM(net_premium), 0),
        ROUND(
            (COUNT(CASE WHEN is_winner = TRUE THEN 1 END) * 100.0 / 
             NULLIF(COUNT(CASE WHEN is_winner IS NOT NULL THEN 1 END), 0)), 2
        )
    FROM trades
    WHERE entry_date >= DATE_TRUNC('month', CURRENT_DATE)
      AND is_winner IS NOT NULL
    ON CONFLICT (period_type, period_start, period_end) 
    DO UPDATE SET
        total_trades = EXCLUDED.total_trades,
        winning_trades = EXCLUDED.winning_trades,
        losing_trades = EXCLUDED.losing_trades,
        total_profit_loss = EXCLUDED.total_profit_loss,
        win_rate_percentage = EXCLUDED.win_rate_percentage,
        calculated_at = CURRENT_TIMESTAMP;
END;
$$ LANGUAGE plpgsql;

-- =============================================================================
-- SAMPLE DATA FOR TESTING
-- =============================================================================

-- Insert sample performance data
INSERT INTO performance_metrics (
    period_type, period_start, period_end,
    total_trades, winning_trades, losing_trades,
    total_profit_loss, win_rate_percentage
) VALUES 
(
    'all_time', 
    '2024-01-01', 
    CURRENT_DATE,
    247, 189, 58, 
    12450.75, 76.5
) ON CONFLICT (period_type, period_start, period_end) DO NOTHING;

-- Insert sample open trades
INSERT INTO trades (
    trade_id, ticker, strategy_type, dte,
    entry_date, expiration_date, short_strike, long_strike,
    quantity, entry_premium_received, entry_underlying_price,
    current_underlying_price, current_itm_status, grok_confidence
) VALUES 
(
    'SPY_2025_10_17_001', 'SPY', 'Bull Put Spread', 10,
    '2025-10-07 09:35:00', '2025-10-17', 565.00, 560.00,
    1, 120, 572.50, 571.80, 'OTM', 85
),
(
    'QQQ_2025_10_24_001', 'QQQ', 'Bear Call Spread', 17,
    '2025-10-07 10:15:00', '2025-10-24', 485.00, 480.00,
    1, 95, 478.20, 479.15, 'OTM', 78
),
(
    'IWM_2025_10_31_001', 'IWM', 'Bull Put Spread', 24,
    '2025-10-07 11:00:00', '2025-10-31', 200.00, 195.00,
    1, 150, 202.30, 198.75, 'ITM', 62
),
(
    'SPY_2025_11_07_001', 'SPY', 'Iron Condor', 31,
    '2025-10-07 14:20:00', '2025-11-07', 567.00, 564.00,
    1, 210, 570.80, 571.20, 'OTM', 88
),
(
    'DIA_2025_10_17_001', 'DIA', 'Bull Put Spread', 10,
    '2025-10-07 15:10:00', '2025-10-17', 425.00, 420.00,
    1, 85, 427.90, 426.45, 'OTM', 81
) ON CONFLICT (trade_id) DO NOTHING;

-- Insert sample market snapshot
INSERT INTO market_snapshots (
    spy_price, spy_change, spy_change_percent,
    spx_price, qqq_price, vix_level,
    is_market_open
) VALUES (
    571.80, 2.35, 0.41,
    5738.50, 479.15, 16.8,
    true
);

-- Create trigger to auto-update timestamps
CREATE OR REPLACE FUNCTION update_updated_at_column()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = CURRENT_TIMESTAMP;
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER update_trades_updated_at 
    BEFORE UPDATE ON trades 
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();