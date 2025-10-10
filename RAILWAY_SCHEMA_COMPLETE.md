# Railway PostgreSQL Schema Documentation
# Complete schema extracted from production database

## Tables Overview
- grok_analyses (14 columns)
- market_snapshots (11 columns) 
- performance_metrics (17 columns)
- public_scoreboard (10 columns)
- trades (37 columns)

## GROK_ANALYSES Table
```sql
CREATE TABLE grok_analyses (
    id                  SERIAL PRIMARY KEY,
    analysis_id         VARCHAR(100) NOT NULL,
    ticker              VARCHAR(10) NOT NULL DEFAULT 'SPY',
    dte                 INTEGER NOT NULL,
    analysis_date       TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    underlying_price    NUMERIC(10,2) NOT NULL,
    prompt_text         TEXT NOT NULL,
    response_text       TEXT NOT NULL,
    confidence_score    INTEGER,
    recommended_strategy VARCHAR(100),
    market_outlook      VARCHAR(50),
    key_levels          TEXT,
    related_trade_id    VARCHAR(50),
    created_at          TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
```

## TRADES Table (Complete - 37 columns!)
```sql
CREATE TABLE trades (
    id                       SERIAL PRIMARY KEY,
    trade_id                 VARCHAR(50) NOT NULL,
    ticker                   VARCHAR(10) NOT NULL DEFAULT 'SPY',
    strategy_type            VARCHAR(50) NOT NULL,
    dte                      INTEGER NOT NULL,
    entry_date               TIMESTAMP NOT NULL,
    expiration_date          DATE NOT NULL,
    short_strike             NUMERIC(10,2) NOT NULL,
    long_strike              NUMERIC(10,2) NOT NULL,
    quantity                 INTEGER NOT NULL DEFAULT 1,
    entry_premium_received   NUMERIC(10,2),
    entry_premium_paid       NUMERIC(10,2),
    entry_underlying_price   NUMERIC(10,2) NOT NULL,
    exit_date                TIMESTAMP,
    exit_premium_paid        NUMERIC(10,2),
    exit_premium_received    NUMERIC(10,2),
    exit_underlying_price    NUMERIC(10,2),
    status                   VARCHAR(20) NOT NULL DEFAULT 'OPEN',
    is_winner                BOOLEAN,
    net_premium              NUMERIC(10,2),
    roi_percentage           NUMERIC(5,2),
    current_underlying_price NUMERIC(10,2),
    current_itm_status       VARCHAR(10),
    last_price_update        TIMESTAMP,
    grok_confidence          INTEGER,
    market_conditions        TEXT,
    notes                    TEXT,
    created_at               TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at               TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    -- NEW COLUMNS ADDED (positions 30-37):
    max_loss                 INTEGER,
    analysis_id              CHAR(1),  -- NOTE: This looks wrong - should be VARCHAR
    prob_prof                INTEGER,
    risk_reward              INTEGER,
    net_delta                INTEGER,
    net_theta                INTEGER,
    prompt_text              TEXT,
    response_text            TEXT
);
```

## MARKET_SNAPSHOTS Table
```sql
CREATE TABLE market_snapshots (
    id                   SERIAL PRIMARY KEY,
    ticker               VARCHAR(10) NOT NULL DEFAULT 'SPY',
    snapshot_date        TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    current_price        NUMERIC(10,2) NOT NULL,
    daily_change         NUMERIC(10,2),
    daily_change_percent NUMERIC(5,2),
    volume               BIGINT,
    implied_volatility   NUMERIC(5,2),
    vix_level            NUMERIC(5,2),
    market_sentiment     VARCHAR(20),
    created_at           TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
```

## PERFORMANCE_METRICS Table
```sql
CREATE TABLE performance_metrics (
    id                      SERIAL PRIMARY KEY,
    period_type             VARCHAR(20) NOT NULL,
    period_start            DATE NOT NULL,
    period_end              DATE NOT NULL,
    total_trades            INTEGER NOT NULL DEFAULT 0,
    winning_trades          INTEGER NOT NULL DEFAULT 0,
    losing_trades           INTEGER NOT NULL DEFAULT 0,
    total_profit_loss       NUMERIC(12,2) NOT NULL DEFAULT 0.00,
    win_rate_percentage     NUMERIC(5,2) NOT NULL DEFAULT 0.00,
    average_roi             NUMERIC(5,2),
    best_trade_roi          NUMERIC(5,2),
    worst_trade_roi         NUMERIC(5,2),
    total_premium_collected NUMERIC(12,2),
    sharpe_ratio            NUMERIC(5,3),
    max_drawdown_percentage NUMERIC(5,2),
    created_at              TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at              TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
```

## PUBLIC_SCOREBOARD Table
```sql
CREATE TABLE public_scoreboard (
    period_type         VARCHAR(20),
    total_trades        INTEGER,
    winning_trades      INTEGER,
    losing_trades       INTEGER,
    win_rate_percentage NUMERIC(5,2),
    total_profit_loss   NUMERIC(12,2),
    average_roi         NUMERIC(5,2),
    best_trade_roi      NUMERIC(5,2),
    worst_trade_roi     NUMERIC(5,2),
    live_trades_count   BIGINT
);
```

## KEY FINDINGS:
1. ✅ **TRADES TABLE HAS ALL NEW COLUMNS** - The 8 columns we wanted to add are already there!
2. ⚠️ **ANALYSIS_ID COLUMN IS WRONG** - It's defined as CHAR(1) instead of VARCHAR(255)
3. ✅ **GROK_ANALYSES TABLE IS COMPLETE** - Has all the fields we need
4. 🎯 **NO SCHEMA CHANGES NEEDED** - Just need to fix the database manager code

## NEXT STEPS:
1. Fix analysis_id column type in Railway (CHAR(1) → VARCHAR(255))
2. Rebuild unified_database.py to match exact schema
3. Test with actual column names and types