"""
PostgreSQL Database Connection and Models for SimpleZero Public Library
=======================================================================

This module provides database connectivity and ORM models for the public
trading scoreboard and Grok analysis library.
"""

import os
import psycopg2
import psycopg2.extras
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any
from dataclasses import dataclass
from decimal import Decimal
import json
import logging

# Set up logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Database configuration
DATABASE_URL = os.getenv('DATABASE_URL')  # Railway PostgreSQL URL
if not DATABASE_URL:
    # Fallback for local development
    DATABASE_URL = f"postgresql://{os.getenv('DB_USER', 'postgres')}:{os.getenv('DB_PASSWORD', 'password')}@{os.getenv('DB_HOST', 'localhost')}:{os.getenv('DB_PORT', '5432')}/{os.getenv('DB_NAME', 'simplezero')}"

@dataclass
class Trade:
    """Trade data model matching database schema"""
    id: Optional[int] = None
    trade_id: str = ""
    ticker: str = "SPY"
    strategy_type: str = ""
    dte: int = 0
    entry_date: Optional[datetime] = None
    expiration_date: Optional[datetime] = None
    short_strike: Decimal = Decimal('0')
    long_strike: Decimal = Decimal('0')
    quantity: int = 1
    entry_premium_received: Optional[Decimal] = None
    entry_premium_paid: Optional[Decimal] = None
    entry_underlying_price: Decimal = Decimal('0')
    exit_date: Optional[datetime] = None
    exit_premium_paid: Optional[Decimal] = None
    exit_premium_received: Optional[Decimal] = None
    exit_underlying_price: Optional[Decimal] = None
    status: str = "OPEN"
    is_winner: Optional[bool] = None
    net_premium: Optional[Decimal] = None
    roi_percentage: Optional[Decimal] = None
    current_underlying_price: Optional[Decimal] = None
    current_itm_status: Optional[str] = None
    last_price_update: Optional[datetime] = None
    grok_confidence: Optional[int] = None
    market_conditions: Optional[str] = None
    source: str = "automated"
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None

@dataclass 
class GrokAnalysis:
    """Grok analysis data model"""
    id: Optional[int] = None
    analysis_id: str = ""
    ticker: str = "SPY"
    dte: int = 0
    analysis_date: Optional[datetime] = None
    prompt_text: str = ""
    response_text: str = ""
    include_sentiment: bool = False
    underlying_price: Decimal = Decimal('0')
    market_conditions: Optional[Dict] = None
    recommended_strategy: Optional[str] = None
    recommended_strikes: Optional[List] = None
    confidence_score: Optional[int] = None
    executed_trade_id: Optional[str] = None
    is_featured: bool = False
    public_title: Optional[str] = None
    created_at: Optional[datetime] = None

@dataclass
class PerformanceMetrics:
    """Performance metrics data model"""
    id: Optional[int] = None
    period_type: str = ""
    period_start: Optional[datetime] = None
    period_end: Optional[datetime] = None
    total_trades: int = 0
    winning_trades: int = 0
    losing_trades: int = 0
    total_premium_collected: Decimal = Decimal('0')
    total_profit_loss: Decimal = Decimal('0')
    win_rate_percentage: Decimal = Decimal('0')
    avg_trade_profit: Optional[Decimal] = None
    avg_win_amount: Optional[Decimal] = None
    avg_loss_amount: Optional[Decimal] = None
    largest_win: Optional[Decimal] = None
    largest_loss: Optional[Decimal] = None
    max_drawdown: Optional[Decimal] = None
    strategy_performance: Optional[Dict] = None
    calculated_at: Optional[datetime] = None

class DatabaseManager:
    """PostgreSQL database manager for SimpleZero public library"""
    
    def __init__(self):
        self.connection_string = DATABASE_URL
        self._connection = None
        
    def get_connection(self):
        """Get database connection, create new if needed"""
        if self._connection is None or self._connection.closed:
            try:
                self._connection = psycopg2.connect(
                    self.connection_string,
                    cursor_factory=psycopg2.extras.RealDictCursor
                )
                logger.info("✅ Connected to PostgreSQL database")
            except Exception as e:
                logger.error(f"❌ Database connection failed: {e}")
                raise
        return self._connection
    
    def execute_query(self, query: str, params: tuple = None, fetch: bool = True) -> Optional[List[Dict]]:
        """Execute a database query safely"""
        try:
            conn = self.get_connection()
            with conn.cursor() as cursor:
                cursor.execute(query, params)
                
                if fetch and cursor.description:
                    result = cursor.fetchall()
                    # Convert RealDictRow to regular dict
                    return [dict(row) for row in result]
                else:
                    conn.commit()
                    return None
                    
        except Exception as e:
            logger.error(f"❌ Query execution failed: {e}")
            logger.error(f"Query: {query}")
            if self._connection:
                self._connection.rollback()
            raise
    
    def close(self):
        """Close database connection"""
        if self._connection and not self._connection.closed:
            self._connection.close()
            logger.info("🔒 Database connection closed")

# Global database manager instance
db = DatabaseManager()

# =============================================================================
# TRADE MANAGEMENT FUNCTIONS
# =============================================================================

def store_trade(trade: Trade) -> bool:
    """Store a new trade in the database"""
    try:
        query = """
        INSERT INTO trades (
            trade_id, ticker, strategy_type, dte, entry_date, expiration_date,
            short_strike, long_strike, quantity, entry_premium_received, 
            entry_premium_paid, entry_underlying_price, grok_confidence,
            market_conditions, source
        ) VALUES (
            %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s
        ) ON CONFLICT (trade_id) DO UPDATE SET
            updated_at = CURRENT_TIMESTAMP
        """
        
        params = (
            trade.trade_id, trade.ticker, trade.strategy_type, trade.dte,
            trade.entry_date, trade.expiration_date, trade.short_strike,
            trade.long_strike, trade.quantity, trade.entry_premium_received,
            trade.entry_premium_paid, trade.entry_underlying_price,
            trade.grok_confidence, trade.market_conditions, trade.source
        )
        
        db.execute_query(query, params, fetch=False)
        logger.info(f"✅ Stored trade: {trade.trade_id}")
        return True
        
    except Exception as e:
        logger.error(f"❌ Failed to store trade: {e}")
        return False

def update_trade_current_price(trade_id: str, current_price: Decimal, itm_status: str) -> bool:
    """Update current price and ITM status for an open trade"""
    try:
        query = """
        UPDATE trades 
        SET current_underlying_price = %s, 
            current_itm_status = %s,
            last_price_update = CURRENT_TIMESTAMP,
            updated_at = CURRENT_TIMESTAMP
        WHERE trade_id = %s AND status = 'OPEN'
        """
        
        db.execute_query(query, (current_price, itm_status, trade_id), fetch=False)
        return True
        
    except Exception as e:
        logger.error(f"❌ Failed to update trade price: {e}")
        return False

def close_trade(trade_id: str, exit_price: Decimal, exit_premium: Decimal, 
                exit_underlying_price: Decimal) -> bool:
    """Close a trade and calculate profitability"""
    try:
        # First get the trade details to calculate profit/loss
        trade_query = """
        SELECT entry_premium_received, entry_premium_paid, strategy_type
        FROM trades WHERE trade_id = %s
        """
        trade_data = db.execute_query(trade_query, (trade_id,))
        
        if not trade_data:
            logger.error(f"Trade {trade_id} not found")
            return False
            
        trade_info = trade_data[0]
        
        # Calculate net premium based on strategy type
        if trade_info['entry_premium_received']:  # Credit spread
            net_premium = trade_info['entry_premium_received'] - exit_premium
        else:  # Debit spread
            net_premium = exit_premium - trade_info['entry_premium_paid']
        
        is_winner = net_premium > 0
        
        # Update trade with exit information
        query = """
        UPDATE trades 
        SET exit_date = CURRENT_TIMESTAMP,
            exit_premium_paid = %s,
            exit_underlying_price = %s,
            status = 'CLOSED',
            is_winner = %s,
            net_premium = %s,
            updated_at = CURRENT_TIMESTAMP
        WHERE trade_id = %s
        """
        
        db.execute_query(query, (exit_premium, exit_underlying_price, 
                                is_winner, net_premium, trade_id), fetch=False)
        
        logger.info(f"✅ Closed trade: {trade_id} - {'WIN' if is_winner else 'LOSS'}: ${net_premium}")
        return True
        
    except Exception as e:
        logger.error(f"❌ Failed to close trade: {e}")
        return False

def get_open_trades() -> List[Dict]:
    """Get all open trades with current status"""
    try:
        query = """
        SELECT * FROM open_trades_status
        ORDER BY entry_date DESC
        """
        
        result = db.execute_query(query)
        return result or []
        
    except Exception as e:
        logger.error(f"❌ Failed to get open trades: {e}")
        return []

def get_recent_performance() -> Dict:
    """Get recent performance summary"""
    try:
        query = "SELECT * FROM recent_performance"
        result = db.execute_query(query)
        
        if result and len(result) > 0:
            return result[0]
        else:
            return {
                'total_trades': 0,
                'winning_trades': 0,
                'losing_trades': 0,
                'win_rate_percentage': 0,
                'total_profit_loss': 0,
                'open_trades': 0
            }
        
    except Exception as e:
        logger.error(f"❌ Failed to get performance: {e}")
        return {}

# =============================================================================
# GROK ANALYSIS FUNCTIONS
# =============================================================================

def store_grok_analysis(analysis: GrokAnalysis) -> bool:
    """Store a Grok analysis in the database"""
    try:
        query = """
        INSERT INTO grok_analyses (
            analysis_id, ticker, dte, analysis_date, prompt_text, response_text,
            include_sentiment, underlying_price, market_conditions, 
            recommended_strategy, recommended_strikes, confidence_score,
            executed_trade_id, is_featured, public_title
        ) VALUES (
            %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s
        ) ON CONFLICT (analysis_id) DO UPDATE SET
            response_text = EXCLUDED.response_text,
            recommended_strategy = EXCLUDED.recommended_strategy,
            recommended_strikes = EXCLUDED.recommended_strikes,
            confidence_score = EXCLUDED.confidence_score
        """
        
        # Convert complex types to JSON
        market_conditions_json = json.dumps(analysis.market_conditions) if analysis.market_conditions else None
        recommended_strikes_json = json.dumps(analysis.recommended_strikes) if analysis.recommended_strikes else None
        
        params = (
            analysis.analysis_id, analysis.ticker, analysis.dte, analysis.analysis_date,
            analysis.prompt_text, analysis.response_text, analysis.include_sentiment,
            analysis.underlying_price, market_conditions_json, analysis.recommended_strategy,
            recommended_strikes_json, analysis.confidence_score, analysis.executed_trade_id,
            analysis.is_featured, analysis.public_title
        )
        
        db.execute_query(query, params, fetch=False)
        logger.info(f"✅ Stored Grok analysis: {analysis.analysis_id}")
        return True
        
    except Exception as e:
        logger.error(f"❌ Failed to store Grok analysis: {e}")
        return False

def get_recent_grok_analyses(limit: int = 10) -> List[Dict]:
    """Get recent Grok analyses for public display"""
    try:
        query = """
        SELECT 
            analysis_id, ticker, dte, analysis_date, response_text,
            underlying_price, recommended_strategy, confidence_score,
            is_featured, public_title, executed_trade_id
        FROM grok_analyses 
        ORDER BY analysis_date DESC 
        LIMIT %s
        """
        
        result = db.execute_query(query, (limit,))
        return result or []
        
    except Exception as e:
        logger.error(f"❌ Failed to get Grok analyses: {e}")
        return []

def get_featured_analysis() -> Optional[Dict]:
    """Get the most recent featured analysis for homepage"""
    try:
        query = """
        SELECT 
            analysis_id, ticker, dte, analysis_date, response_text,
            underlying_price, recommended_strategy, confidence_score,
            public_title, executed_trade_id
        FROM grok_analyses 
        WHERE is_featured = true
        ORDER BY analysis_date DESC 
        LIMIT 1
        """
        
        result = db.execute_query(query)
        return result[0] if result else None
        
    except Exception as e:
        logger.error(f"❌ Failed to get featured analysis: {e}")
        return None

# =============================================================================
# MARKET DATA FUNCTIONS
# =============================================================================

def update_market_snapshot(spy_price: Decimal, spy_change: Decimal, 
                          spy_change_percent: Decimal, is_market_open: bool) -> bool:
    """Update current market snapshot"""
    try:
        query = """
        INSERT INTO market_snapshots (
            spy_price, spy_change, spy_change_percent, is_market_open
        ) VALUES (%s, %s, %s, %s)
        """
        
        db.execute_query(query, (spy_price, spy_change, spy_change_percent, is_market_open), fetch=False)
        
        # Keep only last 24 hours of snapshots
        cleanup_query = """
        DELETE FROM market_snapshots 
        WHERE snapshot_time < NOW() - INTERVAL '24 hours'
        """
        db.execute_query(cleanup_query, fetch=False)
        
        return True
        
    except Exception as e:
        logger.error(f"❌ Failed to update market snapshot: {e}")
        return False

def get_latest_market_snapshot() -> Optional[Dict]:
    """Get the latest market snapshot"""
    try:
        query = """
        SELECT * FROM market_snapshots 
        ORDER BY snapshot_time DESC 
        LIMIT 1
        """
        
        result = db.execute_query(query)
        return result[0] if result else None
        
    except Exception as e:
        logger.error(f"❌ Failed to get market snapshot: {e}")
        return None

# =============================================================================
# UTILITY FUNCTIONS
# =============================================================================

def initialize_database():
    """Initialize database with schema if needed"""
    try:
        # Check if tables exist
        check_query = """
        SELECT table_name FROM information_schema.tables 
        WHERE table_schema = 'public' AND table_name = 'trades'
        """
        
        result = db.execute_query(check_query)
        
        if not result:
            logger.info("🔧 Initializing database schema...")
            
            # Read and execute schema file
            schema_file = os.path.join(os.path.dirname(__file__), 'database_schema.sql')
            if os.path.exists(schema_file):
                with open(schema_file, 'r') as f:
                    schema = f.read()
                    
                # Execute schema (split by ; and execute each statement)
                statements = [s.strip() for s in schema.split(';') if s.strip()]
                for statement in statements:
                    db.execute_query(statement, fetch=False)
                    
                logger.info("✅ Database schema initialized")
            else:
                logger.error("❌ Schema file not found")
                return False
                
        return True
        
    except Exception as e:
        logger.error(f"❌ Database initialization failed: {e}")
        return False

def update_all_performance_metrics():
    """Update all performance metrics using stored procedure"""
    try:
        query = "SELECT update_performance_metrics()"
        db.execute_query(query, fetch=False)
        logger.info("✅ Performance metrics updated")
        return True
        
    except Exception as e:
        logger.error(f"❌ Failed to update performance metrics: {e}")
        return False

# =============================================================================
# TESTING FUNCTIONS
# =============================================================================

def test_database_connection():
    """Test database connectivity and basic operations"""
    try:
        logger.info("🧪 Testing database connection...")
        
        # Test basic connection
        conn = db.get_connection()
        logger.info("✅ Database connection successful")
        
        # Test query execution
        result = db.execute_query("SELECT 1 as test")
        if result and result[0]['test'] == 1:
            logger.info("✅ Query execution successful")
        
        # Test performance metrics view
        performance = get_recent_performance()
        logger.info(f"✅ Performance data: {performance}")
        
        # Test open trades view
        trades = get_open_trades()
        logger.info(f"✅ Open trades count: {len(trades)}")
        
        return True
        
    except Exception as e:
        logger.error(f"❌ Database test failed: {e}")
        return False

if __name__ == "__main__":
    # Run database tests
    test_database_connection()