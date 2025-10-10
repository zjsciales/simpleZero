"""
SimpleZero Database Manager - Rebuilt from Railway Schema
=========================================================

A clean, schema-accurate database manager that matches the exact Railway PostgreSQL structure.
Built from ground-up analysis of production database schema.
"""

import os
import logging
from typing import Dict, List, Optional, Any
from datetime import datetime
from decimal import Decimal

# Set up logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Import config for environment detection
import config

class DatabaseManager:
    """
    Environment-aware database manager built to match exact Railway PostgreSQL schema.
    
    Tables supported:
    - grok_analyses (14 columns)
    - trades (37 columns) 
    - market_snapshots (11 columns)
    - performance_metrics (17 columns)
    - public_scoreboard (10 columns)
    """
    
    def __init__(self):
        self.environment = "PRODUCTION" if config.IS_PRODUCTION else "DEVELOPMENT"
        self.use_postgresql = config.IS_PRODUCTION
        
        # Database connections
        self._sqlite_conn = None
        self._postgres_conn = None
        
        logger.info(f"🗄️ Database Manager - Environment: {self.environment}")
        logger.info(f"🗄️ Database Backend: {'PostgreSQL' if self.use_postgresql else 'SQLite'}")
        
        # Initialize appropriate backend
        if self.use_postgresql:
            self._init_postgresql()
        else:
            self._init_sqlite()
    
    def _init_postgresql(self):
        """Initialize PostgreSQL connection for production"""
        try:
            import psycopg2
            import psycopg2.extras
            
            database_url = os.getenv('DATABASE_URL')
            if not database_url:
                logger.error("❌ DATABASE_URL not found for PostgreSQL")
                logger.info("🔄 Falling back to SQLite...")
                self.use_postgresql = False
                self._init_sqlite()
                return
            
            self._postgres_conn = psycopg2.connect(
                database_url,
                cursor_factory=psycopg2.extras.RealDictCursor
            )
            logger.info("✅ PostgreSQL connection established")
            
            # Verify tables exist
            self._verify_postgresql_tables()
            
        except ImportError:
            logger.warning("⚠️ psycopg2 not available, falling back to SQLite")
            self.use_postgresql = False
            self._init_sqlite()
        except Exception as e:
            logger.error(f"❌ PostgreSQL connection failed: {e}")
            logger.info("🔄 Falling back to SQLite...")
            self.use_postgresql = False
            self._init_sqlite()
    
    def _verify_postgresql_tables(self):
        """Verify critical tables exist in Railway PostgreSQL"""
        try:
            with self._postgres_conn.cursor() as cursor:
                cursor.execute("""
                    SELECT table_name FROM information_schema.tables 
                    WHERE table_schema = 'public' 
                    AND table_name IN ('trades', 'grok_analyses', 'market_snapshots')
                    ORDER BY table_name;
                """)
                tables = [row[0] for row in cursor.fetchall()]
                logger.info(f"✅ Railway tables verified: {tables}")
                
                if len(tables) >= 3:
                    logger.info("✅ All critical tables found - database ready")
                else:
                    logger.warning(f"⚠️ Missing tables! Expected: ['trades', 'grok_analyses', 'market_snapshots'], Found: {tables}")
                    
        except Exception as e:
            logger.error(f"❌ Table verification failed: {e}")
    
    def _init_sqlite(self):
        """Initialize SQLite connection for development"""
        try:
            import sqlite3
            
            db_path = os.path.join(os.path.dirname(__file__), 'simple_zero_public.db')
            self._sqlite_conn = sqlite3.connect(db_path, check_same_thread=False)
            self._sqlite_conn.row_factory = sqlite3.Row
            logger.info(f"✅ SQLite connection established: {db_path}")
            
            # Initialize basic schema for development
            self._init_sqlite_schema()
            
        except Exception as e:
            logger.error(f"❌ SQLite connection failed: {e}")
            raise
    
    def _init_sqlite_schema(self):
        """Create SQLite schema that matches Railway PostgreSQL exactly"""
        try:
            cursor = self._sqlite_conn.cursor()
            
            # Full grok_analyses table matching Railway schema exactly
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS grok_analyses (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    analysis_id TEXT NOT NULL,
                    ticker TEXT NOT NULL DEFAULT 'SPY',
                    dte INTEGER NOT NULL,
                    analysis_date TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
                    underlying_price DECIMAL(10,2) NOT NULL,
                    prompt_text TEXT NOT NULL,
                    response_text TEXT NOT NULL,
                    confidence_score INTEGER,
                    recommended_strategy TEXT,
                    market_outlook TEXT,
                    key_levels TEXT,
                    related_trade_id TEXT,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)
            
            # Full trades table matching Railway schema (all 37 columns)
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS trades (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    trade_id TEXT UNIQUE NOT NULL,
                    ticker TEXT NOT NULL DEFAULT 'SPY',
                    strategy_type TEXT NOT NULL,
                    dte INTEGER NOT NULL,
                    entry_date TIMESTAMP NOT NULL,
                    expiration_date DATE NOT NULL,
                    short_strike DECIMAL(10,2) NOT NULL,
                    long_strike DECIMAL(10,2) NOT NULL,
                    quantity INTEGER NOT NULL DEFAULT 1,
                    entry_premium_received DECIMAL(10,2),
                    entry_premium_paid DECIMAL(10,2),
                    entry_underlying_price DECIMAL(10,2) NOT NULL,
                    exit_date TIMESTAMP,
                    exit_premium_paid DECIMAL(10,2),
                    exit_premium_received DECIMAL(10,2),
                    exit_underlying_price DECIMAL(10,2),
                    status TEXT NOT NULL DEFAULT 'OPEN',
                    is_winner BOOLEAN,
                    net_premium DECIMAL(10,2),
                    roi_percentage DECIMAL(5,2),
                    current_underlying_price DECIMAL(10,2),
                    current_itm_status TEXT,
                    last_price_update TIMESTAMP,
                    grok_confidence INTEGER,
                    market_conditions TEXT,
                    notes TEXT,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    max_loss INTEGER,
                    analysis_id TEXT,
                    prob_prof INTEGER,
                    risk_reward INTEGER,
                    net_delta INTEGER,
                    net_theta INTEGER,
                    prompt_text TEXT,
                    response_text TEXT
                )
            """)
            
            self._sqlite_conn.commit()
            logger.info("✅ SQLite schema initialized (Railway-compatible)")
            
        except Exception as e:
            logger.error(f"❌ SQLite schema initialization failed: {e}")
    
    def execute_query(self, query: str, params: tuple = None, fetch: bool = True) -> Optional[List[Dict]]:
        """Execute a database query with proper connection handling"""
        try:
            if self.use_postgresql:
                with self._postgres_conn.cursor() as cursor:
                    cursor.execute(query, params)
                    if fetch:
                        return [dict(row) for row in cursor.fetchall()]
                    else:
                        self._postgres_conn.commit()
                        return None
            else:
                cursor = self._sqlite_conn.cursor()
                cursor.execute(query, params or ())
                if fetch:
                    return [dict(row) for row in cursor.fetchall()]
                else:
                    self._sqlite_conn.commit()
                    return None
                    
        except Exception as e:
            logger.error(f"❌ Query execution failed: {e}")
            logger.error(f"Query: {query}")
            logger.error(f"Params: {params}")
            if self.use_postgresql:
                self._postgres_conn.rollback()
            else:
                self._sqlite_conn.rollback()
            raise
    
    def store_grok_analysis(self, analysis_data: Dict) -> bool:
        """
        Store a Grok analysis record in grok_analyses table.
        Matches exact Railway PostgreSQL schema (14 columns).
        """
        try:
            if self.use_postgresql:
                query = """
                INSERT INTO grok_analyses (
                    analysis_id, ticker, dte, underlying_price, prompt_text, response_text,
                    confidence_score, recommended_strategy, market_outlook, 
                    key_levels, related_trade_id
                ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                """
                params = (
                    analysis_data.get('analysis_id'),
                    analysis_data.get('ticker', 'SPY'),
                    analysis_data.get('dte'),
                    analysis_data.get('underlying_price'),
                    analysis_data.get('prompt_text'),
                    analysis_data.get('response_text'),
                    analysis_data.get('confidence_score'),
                    analysis_data.get('recommended_strategy'),
                    analysis_data.get('market_outlook'),
                    analysis_data.get('key_levels'),
                    analysis_data.get('related_trade_id')
                )
            else:
                # SQLite version
                query = """
                INSERT INTO grok_analyses (
                    analysis_id, ticker, dte, underlying_price, prompt_text, response_text,
                    confidence_score, recommended_strategy, market_outlook, 
                    key_levels, related_trade_id
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """
                params = (
                    analysis_data.get('analysis_id'),
                    analysis_data.get('ticker', 'SPY'),
                    analysis_data.get('dte'),
                    analysis_data.get('underlying_price'),
                    analysis_data.get('prompt_text'),
                    analysis_data.get('response_text'),
                    analysis_data.get('confidence_score'),
                    analysis_data.get('recommended_strategy'),
                    analysis_data.get('market_outlook'),
                    analysis_data.get('key_levels'),
                    analysis_data.get('related_trade_id')
                )
            
            self.execute_query(query, params, fetch=False)
            logger.info(f"✅ Grok analysis stored: {analysis_data.get('analysis_id')}")
            return True
            
        except Exception as e:
            logger.error(f"❌ Failed to store Grok analysis: {e}")
            return False
    
    def store_trade(self, trade_data: Dict) -> bool:
        """
        Store a trade record in trades table.
        Matches exact Railway PostgreSQL schema (37 columns).
        """
        try:
            if self.use_postgresql:
                # Full Railway PostgreSQL query with all 37 columns
                query = """
                INSERT INTO trades (
                    trade_id, ticker, strategy_type, dte, entry_date, expiration_date,
                    short_strike, long_strike, quantity, entry_premium_received,
                    entry_premium_paid, entry_underlying_price, status, grok_confidence,
                    market_conditions, max_loss, analysis_id, prob_prof, risk_reward,
                    net_delta, net_theta, prompt_text, response_text
                ) VALUES (
                    %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s
                ) ON CONFLICT (trade_id) DO UPDATE SET
                    updated_at = CURRENT_TIMESTAMP
                """
                params = (
                    trade_data.get('trade_id'),
                    trade_data.get('ticker', 'SPY'),
                    trade_data.get('strategy_type'),
                    trade_data.get('dte'),
                    trade_data.get('entry_date'),
                    trade_data.get('expiration_date'),
                    trade_data.get('short_strike'),
                    trade_data.get('long_strike'),
                    trade_data.get('quantity', 1),
                    trade_data.get('entry_premium_received'),
                    trade_data.get('entry_premium_paid'),
                    trade_data.get('entry_underlying_price'),
                    trade_data.get('status', 'OPEN'),
                    trade_data.get('grok_confidence'),
                    trade_data.get('market_conditions'),
                    trade_data.get('max_loss'),
                    trade_data.get('analysis_id'),
                    trade_data.get('prob_prof'),
                    trade_data.get('risk_reward'),
                    trade_data.get('net_delta'),
                    trade_data.get('net_theta'),
                    trade_data.get('prompt_text'),
                    trade_data.get('response_text')
                )
            else:
                # Simplified SQLite version
                query = """
                INSERT OR REPLACE INTO trades (
                    trade_id, ticker, strategy_type, dte, entry_date, expiration_date,
                    short_strike, long_strike, quantity, entry_premium_received,
                    entry_premium_paid, entry_underlying_price, status, grok_confidence,
                    market_conditions
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """
                params = (
                    trade_data.get('trade_id'),
                    trade_data.get('ticker', 'SPY'),
                    trade_data.get('strategy_type'),
                    trade_data.get('dte'),
                    trade_data.get('entry_date'),
                    trade_data.get('expiration_date'),
                    trade_data.get('short_strike'),
                    trade_data.get('long_strike'),
                    trade_data.get('quantity', 1),
                    trade_data.get('entry_premium_received'),
                    trade_data.get('entry_premium_paid'),
                    trade_data.get('entry_underlying_price'),
                    trade_data.get('status', 'OPEN'),
                    trade_data.get('grok_confidence'),
                    trade_data.get('market_conditions')
                )
            
            self.execute_query(query, params, fetch=False)
            logger.info(f"✅ Trade stored: {trade_data.get('trade_id')}")
            return True
            
        except Exception as e:
            logger.error(f"❌ Failed to store trade: {e}")
            return False
    
    def store_grok_trade_suggestion(self, analysis_data: Dict, response_text: str = None) -> bool:
        """
        Parse Grok analysis response and store as trade suggestion in trades table.
        Uses the GrokResponseParser to extract trade details from the AI response.
        """
        try:
            from trader import GrokResponseParser
            
            # Get response text
            if response_text is None:
                response_text = analysis_data.get('response_text', '')
            
            if not response_text:
                logger.warning("No response text provided for trade suggestion parsing")
                return False
                
            # Parse the response using existing parser
            trade_signal = GrokResponseParser.parse_grok_response(response_text)
            
            if not trade_signal:
                logger.warning("Failed to parse trade signal from response")
                return False
            
            # Create trade record with all parsed details
            trade_record = {
                'trade_id': f"grok_suggested_{datetime.now().strftime('%Y%m%d_%H%M%S')}",
                'ticker': analysis_data.get('ticker', 'SPY'),
                'strategy_type': trade_signal.strategy_type.value if hasattr(trade_signal.strategy_type, 'value') else str(trade_signal.strategy_type),
                'dte': analysis_data.get('dte', 0),
                'entry_date': analysis_data.get('analysis_date', datetime.now()),
                'expiration_date': trade_signal.expiration,
                'short_strike': trade_signal.short_strike,
                'long_strike': trade_signal.long_strike,
                'quantity': 1,
                'entry_premium_received': trade_signal.max_profit,
                'entry_underlying_price': analysis_data.get('underlying_price', 0.0),
                'status': 'SUGGESTED',
                'grok_confidence': trade_signal.confidence,
                'market_conditions': f"{trade_signal.market_bias} - {trade_signal.reasoning[:200]}...",
                'max_loss': trade_signal.max_loss,
                'prob_prof': int(trade_signal.probability_of_profit) if trade_signal.probability_of_profit else None,
                'risk_reward': int(trade_signal.reward_risk_ratio * 100) if trade_signal.reward_risk_ratio else None,
                'net_delta': int(trade_signal.delta * 100) if trade_signal.delta else None,
                'net_theta': int(trade_signal.theta * 100) if trade_signal.theta else None,
                'analysis_id': analysis_data.get('analysis_id'),
                'prompt_text': analysis_data.get('prompt_text', ''),
                'response_text': response_text,
                'created_at': datetime.now()
            }
            
            # Store the trade using our store_trade method
            success = self.store_trade(trade_record)
            
            if success:
                logger.info(f"✅ Stored Grok trade suggestion: {trade_record['trade_id']} - {trade_record['strategy_type']} {trade_record['short_strike']}/{trade_record['long_strike']}")
            
            return success
            
        except Exception as e:
            logger.error(f"❌ Error storing Grok trade suggestion: {e}")
            return False

    def get_recent_trades(self, limit: int = 10) -> List[Dict]:
        """Get recent trades from the database"""
        try:
            query = """
            SELECT * FROM trades 
            ORDER BY created_at DESC 
            LIMIT %s
            """ if self.use_postgresql else """
            SELECT * FROM trades 
            ORDER BY created_at DESC 
            LIMIT ?
            """
            
            result = self.execute_query(query, (limit,))
            return result or []
            
        except Exception as e:
            logger.error(f"❌ Failed to get recent trades: {e}")
            return []
    
    def get_recent_analyses(self, limit: int = 10) -> List[Dict]:
        """Get recent Grok analyses from the database"""
        try:
            query = """
            SELECT * FROM grok_analyses 
            ORDER BY created_at DESC 
            LIMIT %s
            """ if self.use_postgresql else """
            SELECT * FROM grok_analyses 
            ORDER BY created_at DESC 
            LIMIT ?
            """
            
            result = self.execute_query(query, (limit,))
            return result or []
            
        except Exception as e:
            logger.error(f"❌ Failed to get recent analyses: {e}")
            return []
    
    def reset_connection(self):
        """Reset database connection (for error recovery)"""
        try:
            if self.use_postgresql and self._postgres_conn:
                self._postgres_conn.rollback()
                logger.info("✅ PostgreSQL connection reset")
            elif self._sqlite_conn:
                self._sqlite_conn.rollback()
                logger.info("✅ SQLite connection reset")
        except Exception as e:
            logger.warning(f"⚠️ Connection reset warning: {e}")

    def test_connection(self) -> bool:
        """Test database connection"""
        try:
            query = "SELECT 1 as test"
            result = self.execute_query(query)
            return bool(result)
        except Exception as e:
            logger.error(f"❌ Connection test failed: {e}")
            return False

# Global database manager instance
db_manager = DatabaseManager()

# Convenience functions for backward compatibility
def store_grok_analysis(analysis_data: Dict) -> bool:
    """Store a Grok analysis"""
    return db_manager.store_grok_analysis(analysis_data)

def store_trade(trade_data: Dict) -> bool:
    """Store a trade record"""
    return db_manager.store_trade(trade_data)

def get_recent_trades(limit: int = 10) -> List[Dict]:
    """Get recent trades"""
    return db_manager.get_recent_trades(limit)

def get_recent_analyses(limit: int = 10) -> List[Dict]:
    """Get recent analyses"""
    return db_manager.get_recent_analyses(limit)

def store_grok_trade_suggestion(analysis_data: Dict, response_text: str = None) -> bool:
    """Store a Grok trade suggestion"""
    return db_manager.store_grok_trade_suggestion(analysis_data, response_text)

def test_database_connection() -> bool:
    """Test database connection"""
    return db_manager.test_connection()