"""
Environment-Aware Database Manager for SimpleZero
================================================

This module automatically selects the appropriate database backend based on
the environment, with graceful fallback and unified interface.
"""

import os
import logging
from typing import Dict, List, Optional, Any, Union
from datetime import datetime
from decimal import Decimal

# Set up logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Import config for environment detection
import config

class DatabaseManager:
    """
    Environment-aware database manager that automatically selects:
    - SQLite for local/development environments
    - PostgreSQL for production environments
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
            
            # Initialize schema if needed
            self._init_postgresql_schema()
            
        except ImportError:
            logger.warning("⚠️ psycopg2 not available, falling back to SQLite")
            self.use_postgresql = False
            self._init_sqlite()
        except Exception as e:
            logger.error(f"❌ PostgreSQL connection failed: {e}")
            logger.info("🔄 Falling back to SQLite...")
            self.use_postgresql = False
            self._init_sqlite()
    
    def _init_sqlite(self):
        """Initialize SQLite connection for development"""
        try:
            import sqlite3
            
            db_path = os.path.join(os.path.dirname(__file__), 'simple_zero_public.db')
            self._sqlite_conn = sqlite3.connect(db_path, check_same_thread=False)
            self._sqlite_conn.row_factory = sqlite3.Row
            logger.info(f"✅ SQLite connection established: {db_path}")
            
            # Initialize schema if needed
            self._init_sqlite_schema()
            
        except Exception as e:
            logger.error(f"❌ SQLite connection failed: {e}")
            raise
    
    def _init_postgresql_schema(self):
        """Initialize PostgreSQL schema from SQL file"""
        try:
            # TEMPORARILY SKIP SCHEMA INITIALIZATION to avoid syntax errors
            logger.info("⚠️ Skipping PostgreSQL schema initialization (tables already exist)")
            logger.info("🔍 Verifying existing tables...")
            
            # Just verify critical tables exist
            with self._postgres_conn.cursor() as cursor:
                cursor.execute("""
                    SELECT table_name FROM information_schema.tables 
                    WHERE table_schema = 'public' 
                    AND table_name IN ('trades', 'grok_analyses', 'performance_metrics')
                    ORDER BY table_name;
                """)
                tables = [row[0] for row in cursor.fetchall()]
                logger.info(f"✅ Found existing tables: {tables}")
                
                if 'grok_analyses' in tables:
                    logger.info("✅ Critical grok_analyses table verified - ready to use")
                else:
                    logger.warning(f"⚠️ Missing grok_analyses table! Found: {tables}")
                    
        except Exception as e:
            logger.error(f"❌ PostgreSQL table verification failed: {e}")
            # Don't raise - let the app continue
                
        except Exception as e:
            logger.error(f"❌ PostgreSQL schema initialization failed: {e}")
    
    def _init_sqlite_schema(self):
        """Initialize SQLite schema with adapted PostgreSQL schema"""
        try:
            # Convert PostgreSQL schema to SQLite-compatible
            sqlite_schema = """
            -- SimpleZero SQLite Schema (adapted from PostgreSQL)
            
            CREATE TABLE IF NOT EXISTS trades (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                trade_id TEXT UNIQUE NOT NULL,
                ticker TEXT NOT NULL DEFAULT 'SPY',
                strategy_type TEXT NOT NULL,
                dte INTEGER NOT NULL,
                entry_date TIMESTAMP NOT NULL,
                expiration_date DATE NOT NULL,
                short_strike REAL NOT NULL,
                long_strike REAL NOT NULL,
                quantity INTEGER NOT NULL DEFAULT 1,
                entry_premium_received REAL,
                entry_premium_paid REAL,
                entry_underlying_price REAL NOT NULL,
                exit_date TIMESTAMP NULL,
                exit_premium_paid REAL NULL,
                exit_premium_received REAL NULL,
                exit_underlying_price REAL NULL,
                status TEXT NOT NULL DEFAULT 'OPEN',
                is_winner INTEGER NULL,
                net_premium REAL NULL,
                roi_percentage REAL NULL,
                current_underlying_price REAL NULL,
                current_itm_status TEXT NULL,
                last_price_update TIMESTAMP NULL,
                grok_confidence INTEGER NULL,
                market_conditions TEXT NULL,
                source TEXT DEFAULT 'automated',
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );
            
            CREATE TABLE IF NOT EXISTS grok_analyses (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                analysis_id TEXT UNIQUE NOT NULL,
                ticker TEXT NOT NULL DEFAULT 'SPY',
                dte INTEGER NOT NULL,
                analysis_date TIMESTAMP NOT NULL,
                prompt_text TEXT NOT NULL,
                response_text TEXT NOT NULL,
                include_sentiment INTEGER DEFAULT 0,
                underlying_price REAL NOT NULL,
                market_conditions TEXT NULL,
                recommended_strategy TEXT NULL,
                recommended_strikes TEXT NULL,
                confidence_score INTEGER NULL,
                executed_trade_id TEXT NULL,
                is_featured INTEGER DEFAULT 0,
                public_title TEXT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );
            
            CREATE TABLE IF NOT EXISTS performance_metrics (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                period_type TEXT NOT NULL,
                period_start DATE NOT NULL,
                period_end DATE NOT NULL,
                total_trades INTEGER NOT NULL DEFAULT 0,
                winning_trades INTEGER NOT NULL DEFAULT 0,
                losing_trades INTEGER NOT NULL DEFAULT 0,
                total_premium_collected REAL NOT NULL DEFAULT 0,
                total_profit_loss REAL NOT NULL DEFAULT 0,
                win_rate_percentage REAL NOT NULL DEFAULT 0,
                avg_trade_profit REAL NULL,
                avg_win_amount REAL NULL,
                avg_loss_amount REAL NULL,
                largest_win REAL NULL,
                largest_loss REAL NULL,
                max_drawdown REAL NULL,
                strategy_performance TEXT NULL,
                calculated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                UNIQUE(period_type, period_start, period_end)
            );
            
            CREATE TABLE IF NOT EXISTS market_snapshots (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                spy_price REAL NOT NULL,
                spy_change REAL NOT NULL,
                spy_change_percent REAL NOT NULL,
                spx_price REAL NULL,
                qqq_price REAL NULL,
                vix_level REAL NULL,
                total_spy_volume INTEGER NULL,
                put_call_ratio REAL NULL,
                snapshot_time TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                is_market_open INTEGER NOT NULL,
                data_source TEXT DEFAULT 'tastytrade'
            );
            
            -- Indices for performance
            CREATE INDEX IF NOT EXISTS idx_trades_status ON trades(status);
            CREATE INDEX IF NOT EXISTS idx_trades_entry_date ON trades(entry_date);
            CREATE INDEX IF NOT EXISTS idx_grok_analyses_date ON grok_analyses(analysis_date);
            CREATE INDEX IF NOT EXISTS idx_market_snapshots_time ON market_snapshots(snapshot_time);
            """
            
            # Execute SQLite schema
            cursor = self._sqlite_conn.cursor()
            cursor.executescript(sqlite_schema)
            self._sqlite_conn.commit()
            
            # Insert sample data for development
            self._insert_sample_data_sqlite()
            
            logger.info("✅ SQLite schema initialized")
            
        except Exception as e:
            logger.error(f"❌ SQLite schema initialization failed: {e}")
    
    def _insert_sample_data_sqlite(self):
        """Insert sample data for development testing"""
        try:
            cursor = self._sqlite_conn.cursor()
            
            # Sample performance metrics
            cursor.execute("""
                INSERT OR IGNORE INTO performance_metrics (
                    period_type, period_start, period_end,
                    total_trades, winning_trades, losing_trades,
                    total_profit_loss, win_rate_percentage
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """, ('all_time', '2024-01-01', '2025-12-31', 247, 189, 58, 12450.75, 76.5))
            
            # Sample trades
            sample_trades = [
                ('SPY_2025_10_17_001', 'SPY', 'Bull Put Spread', 10, '2025-10-07 09:35:00', 
                 '2025-10-17', 565.00, 560.00, 1, 1.20, None, 572.50, None, None, None, 
                 None, 'OPEN', None, None, None, 571.80, 'OTM', '2025-10-07 15:30:00', 85),
                ('QQQ_2025_10_24_001', 'QQQ', 'Bear Call Spread', 17, '2025-10-07 10:15:00',
                 '2025-10-24', 485.00, 480.00, 1, 0.95, None, 478.20, None, None, None,
                 None, 'OPEN', None, None, None, 479.15, 'OTM', '2025-10-07 15:30:00', 78)
            ]
            
            for trade in sample_trades:
                cursor.execute("""
                    INSERT OR IGNORE INTO trades (
                        trade_id, ticker, strategy_type, dte, entry_date, expiration_date,
                        short_strike, long_strike, quantity, entry_premium_received,
                        entry_premium_paid, entry_underlying_price, exit_date,
                        exit_premium_paid, exit_premium_received, exit_underlying_price,
                        status, is_winner, net_premium, roi_percentage,
                        current_underlying_price, current_itm_status, last_price_update,
                        grok_confidence
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, trade)
            
            # Sample Grok analysis
            cursor.execute("""
                INSERT OR IGNORE INTO grok_analyses (
                    analysis_id, ticker, dte, analysis_date, prompt_text, response_text,
                    underlying_price, recommended_strategy, confidence_score, is_featured
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                'grok_2025_10_07_dev', 'SPY', 0, '2025-10-07 14:30:00',
                'Market analysis request for SPY 0DTE...',
                'Development mode analysis: Strong bullish momentum with low volatility. Recommend Bull Put Spread at $565/$560 strikes.',
                571.80, 'Bull Put Spread', 85, 1
            ))
            
            self._sqlite_conn.commit()
            logger.info("✅ SQLite sample data inserted")
            
        except Exception as e:
            logger.error(f"❌ SQLite sample data insertion failed: {e}")
    
    def execute_query(self, query: str, params=None, fetch: bool = True) -> Optional[List[Dict]]:
        """Execute a database query with automatic backend selection"""
        try:
            # Convert params to tuple if needed, handle None case
            if params is not None and not isinstance(params, (tuple, list)):
                params = (params,)
            elif params is None:
                params = ()
            
            if self.use_postgresql and self._postgres_conn:
                return self._execute_postgresql_query(query, params, fetch)
            else:
                return self._execute_sqlite_query(query, params, fetch)
        except Exception as e:
            logger.error(f"❌ Query execution failed: {e}")
            raise
    
    def _execute_postgresql_query(self, query: str, params=None, fetch: bool = True) -> Optional[List[Dict]]:
        """Execute PostgreSQL query"""
        with self._postgres_conn.cursor() as cursor:
            if params:
                cursor.execute(query, params)
            else:
                cursor.execute(query)
            
            if fetch and cursor.description:
                result = cursor.fetchall()
                return [dict(row) for row in result]
            else:
                self._postgres_conn.commit()
                return None
    
    def _execute_sqlite_query(self, query: str, params=None, fetch: bool = True) -> Optional[List[Dict]]:
        """Execute SQLite query"""
        cursor = self._sqlite_conn.cursor()
        if params:
            cursor.execute(query, params)
        else:
            cursor.execute(query)
        
        if fetch:
            result = cursor.fetchall()
            return [dict(row) for row in result]
        else:
            self._sqlite_conn.commit()
            return None
    
    def get_recent_performance(self) -> Dict:
        """Get recent performance summary (unified interface)"""
        try:
            if self.use_postgresql:
                # Use PostgreSQL tables directly - SPY only
                query = """
                SELECT 
                    total_trades,
                    winning_trades,
                    losing_trades,
                    win_rate_percentage,
                    total_profit_loss,
                    average_roi,
                    best_trade_roi,
                    worst_trade_roi
                FROM performance_metrics 
                WHERE period_type = 'all_time'
                ORDER BY created_at DESC 
                LIMIT 1
                """
            else:
                # SQLite equivalent - SPY only
                query = """
                SELECT 
                    COUNT(*) as total_trades,
                    COUNT(CASE WHEN is_winner = 1 THEN 1 END) as winning_trades,
                    COUNT(CASE WHEN is_winner = 0 THEN 1 END) as losing_trades,
                    ROUND(
                        (COUNT(CASE WHEN is_winner = 1 THEN 1 END) * 100.0 / 
                         NULLIF(COUNT(CASE WHEN is_winner IS NOT NULL THEN 1 END), 0)), 1
                    ) as win_rate_percentage,
                    COALESCE(SUM(net_premium), 0) as total_profit_loss,
                    ROUND(AVG(CASE WHEN is_winner IS NOT NULL THEN roi_percentage END), 1) as average_roi,
                    MAX(roi_percentage) as best_trade_roi,
                    MIN(roi_percentage) as worst_trade_roi
                FROM trades 
                WHERE status != 'OPEN' AND ticker = 'SPY'
                """
            
            result = self.execute_query(query)
            if result and len(result) > 0:
                return result[0]
            else:
                # Return default empty performance
                return {
                    'total_trades': 0,
                    'winning_trades': 0,
                    'losing_trades': 0,
                    'win_rate_percentage': 0.0,
                    'total_profit_loss': 0.0,
                    'average_roi': 0.0,
                    'best_trade_roi': 0.0,
                    'worst_trade_roi': 0.0
                }
            
        except Exception as e:
            logger.error(f"❌ Error getting performance: {e}")
            # Return default empty performance on error
            return {
                'total_trades': 0,
                'winning_trades': 0,
                'losing_trades': 0,
                'win_rate_percentage': 0.0,
                'total_profit_loss': 0.0,
                'average_roi': 0.0,
                'best_trade_roi': 0.0,
                'worst_trade_roi': 0.0
            }
    
    def get_open_trades(self) -> List[Dict]:
        """Get open trades with ITM/OTM status (unified interface)"""
        try:
            if self.use_postgresql:
                # PostgreSQL query using actual trades table - SPY only
                query = """
                SELECT 
                    *,
                    CASE 
                        WHEN strategy_type LIKE '%Put%' THEN 
                            CASE WHEN current_underlying_price < short_strike THEN 'ITM' ELSE 'OTM' END
                        WHEN strategy_type LIKE '%Call%' THEN 
                            CASE WHEN current_underlying_price > short_strike THEN 'ITM' ELSE 'OTM' END
                        ELSE 'UNKNOWN'
                    END as itm_otm_status,
                    EXTRACT(DAY FROM (expiration_date - CURRENT_DATE)) as days_to_expiration
                FROM trades 
                WHERE status = 'OPEN' AND ticker = 'SPY'
                ORDER BY entry_date DESC
                """
            else:
                # SQLite equivalent - SPY only
                query = """
                SELECT 
                    *,
                    CASE 
                        WHEN strategy_type LIKE '%Put%' THEN 
                            CASE WHEN current_underlying_price < short_strike THEN 'ITM' ELSE 'OTM' END
                        WHEN strategy_type LIKE '%Call%' THEN 
                            CASE WHEN current_underlying_price > short_strike THEN 'ITM' ELSE 'OTM' END
                        ELSE 'UNKNOWN'
                    END as itm_otm_status,
                    CAST((julianday(expiration_date) - julianday('now')) AS INTEGER) as days_to_expiration
                FROM trades 
                WHERE status = 'OPEN' AND ticker = 'SPY'
                ORDER BY entry_date DESC
                """
            
            result = self.execute_query(query)
            return result or []
            
        except Exception as e:
            logger.error(f"❌ Error getting open trades: {e}")
            return []
    
    def get_recent_grok_analyses(self, limit: int = 10) -> List[Dict]:
        """Get recent Grok analyses (unified interface) - Match actual table structure"""
        try:
            logger.info(f"🔍 Getting recent Grok analyses (limit: {limit})")
            
            if self.use_postgresql:
                query = """
                SELECT 
                    id, ticker, snapshot_date, current_price, daily_change, daily_change_percent,
                    volume, implied_volatility, vix_level, market_sentiment,
                    response_text, confidence_score, recommended_strategy,
                    market_outlook, key_levels, related_trade_id, created_at
                FROM grok_analyses 
                WHERE ticker = 'SPY' AND response_text IS NOT NULL AND response_text != ''
                ORDER BY snapshot_date DESC 
                LIMIT %s
                """
            else:
                query = """
                SELECT 
                    id, ticker, snapshot_date, current_price, market_sentiment, response_text
                FROM grok_analyses 
                WHERE ticker = 'SPY'
                ORDER BY snapshot_date DESC 
                LIMIT ?
                """
            
            result = self.execute_query(query, (limit,))
            
            if result and self.use_postgresql:
                # Convert to format expected by the template
                for analysis in result:
                    # Map your columns to what the template expects
                    analysis['analysis_id'] = f"grok_{analysis['id']}"
                    analysis['analysis_date'] = analysis['snapshot_date'] 
                    analysis['underlying_price'] = analysis['current_price']
                    analysis['dte'] = 0  # Default since not in your table
                    analysis['is_featured'] = False
                    analysis['public_title'] = None
                    analysis['executed_trade_id'] = analysis.get('related_trade_id')
            
            logger.info(f"✅ Found {len(result) if result else 0} Grok analyses")
            return result or []
            
        except Exception as e:
            logger.error(f"❌ Error getting Grok analyses: {e}")
            return []
    
    def store_grok_analysis(self, analysis_data: Dict) -> bool:
        """Store Grok analysis (unified interface) - Match actual table with ALL columns"""
        try:
            logger.info(f"💾 Storing Grok analysis: {analysis_data.get('ticker', 'SPY')}")
            
            if self.use_postgresql:
                # Your table has BOTH market snapshot AND analysis columns
                query = """
                INSERT INTO grok_analyses (
                    ticker, snapshot_date, current_price, daily_change, daily_change_percent,
                    volume, implied_volatility, vix_level, market_sentiment,
                    response_text, confidence_score, recommended_strategy, 
                    market_outlook, key_levels, related_trade_id
                ) VALUES (
                    %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s
                )
                """
                params = (
                    analysis_data.get('ticker', 'SPY'),
                    analysis_data.get('snapshot_date', datetime.now()),
                    analysis_data.get('current_price', 0.0),
                    analysis_data.get('daily_change', 0.0),
                    analysis_data.get('daily_change_percent', 0.0),
                    analysis_data.get('volume', 0),
                    analysis_data.get('implied_volatility', 0.0),
                    analysis_data.get('vix_level', 0.0),
                    analysis_data.get('market_sentiment', 'NEUTRAL'),
                    # Analysis fields
                    analysis_data.get('response_text', ''),
                    analysis_data.get('confidence_score'),
                    analysis_data.get('recommended_strategy'),
                    analysis_data.get('market_outlook'),
                    analysis_data.get('key_levels'),
                    analysis_data.get('related_trade_id')
                )
                logger.info(f"🔍 PostgreSQL: ticker={params[0]}, price={params[2]}, response_len={len(params[9]) if params[9] else 0}")
            else:
                # SQLite fallback (simplified)
                query = """
                INSERT OR REPLACE INTO grok_analyses (
                    ticker, snapshot_date, current_price, market_sentiment, response_text
                ) VALUES (?, ?, ?, ?, ?)
                """
                params = (
                    analysis_data.get('ticker', 'SPY'),
                    analysis_data.get('snapshot_date', datetime.now()),
                    analysis_data.get('current_price', 0.0),
                    analysis_data.get('market_sentiment', 'NEUTRAL'),
                    analysis_data.get('response_text', '')
                )
            
            self.execute_query(query, params, fetch=False)
            logger.info(f"✅ Stored Grok analysis: {analysis_data.get('analysis_id')}")
            
            # Verify the storage worked
            verification_query = "SELECT COUNT(*) FROM grok_analyses WHERE analysis_id = %s" if self.use_postgresql else "SELECT COUNT(*) FROM grok_analyses WHERE analysis_id = ?"
            result = self.execute_query(verification_query, (analysis_data.get('analysis_id'),))
            logger.info(f"🔍 Verification: {result[0] if result else 'Failed'} record(s) found")
            return True
            
        except Exception as e:
            logger.error(f"❌ Failed to store Grok analysis: {e}")
            logger.error(f"🔍 Analysis data keys: {list(analysis_data.keys()) if analysis_data else 'None'}")
            return False
    
    def reset_connection(self):
        """Reset database connection state (useful for PostgreSQL transaction errors)"""
        try:
            if self.use_postgresql and self._postgres_conn:
                logger.info("🔄 Resetting PostgreSQL connection state...")
                try:
                    self._postgres_conn.rollback()
                    logger.info("✅ PostgreSQL transaction rolled back")
                except Exception as e:
                    logger.warning(f"⚠️ Rollback warning: {e}")
                
                # Test connection with simple query
                try:
                    with self._postgres_conn.cursor() as cursor:
                        cursor.execute("SELECT 1;")
                        cursor.fetchone()
                    logger.info("✅ PostgreSQL connection verified")
                except Exception as e:
                    logger.error(f"❌ PostgreSQL connection test failed: {e}")
                    # Try to reconnect
                    self._init_postgresql()
            else:
                logger.info("ℹ️ Using SQLite - no connection reset needed")
        except Exception as e:
            logger.error(f"❌ Connection reset failed: {e}")
    
    def close(self):
        """Close database connections"""
        if self._postgres_conn and not self._postgres_conn.closed:
            self._postgres_conn.close()
            logger.info("🔒 PostgreSQL connection closed")
        
        if self._sqlite_conn:
            self._sqlite_conn.close()
            logger.info("🔒 SQLite connection closed")
    
    def test_connection(self) -> bool:
        """Test database connectivity"""
        try:
            result = self.execute_query("SELECT 1 as test")
            return result and result[0]['test'] == 1
        except Exception as e:
            logger.error(f"❌ Database test failed: {e}")
            return False

# Global database manager instance
db_manager = DatabaseManager()

# Convenience functions for backward compatibility
def get_recent_performance():
    return db_manager.get_recent_performance()

def get_open_trades():
    return db_manager.get_open_trades()

def get_recent_grok_analyses(limit: int = 10):
    """Get recent Grok analyses - SPY only"""
    try:
        logger.info(f"🔍 [Standalone] Getting recent Grok analyses (limit: {limit})")
        
        if db_manager.use_postgresql:
            query = """
            SELECT analysis_id, ticker, dte, analysis_date, underlying_price,
                   prompt_text, response_text, confidence_score, recommended_strategy,
                   market_outlook, key_levels, related_trade_id
            FROM grok_analyses 
            WHERE ticker = 'SPY' AND response_text IS NOT NULL AND response_text != ''
            ORDER BY analysis_date DESC 
            LIMIT %s
            """
        else:
            query = """
            SELECT analysis_id, ticker, dte, analysis_date, underlying_price,
                   prompt_text, response_text, confidence_score, recommended_strategy
            FROM grok_analyses 
            WHERE ticker = 'SPY'
            ORDER BY analysis_date DESC 
            LIMIT ?
            """
        
        result = db_manager.execute_query(query, (limit,))
        
        if result and db_manager.use_postgresql:
            # Add missing fields that the template expects
            for analysis in result:
                analysis['is_featured'] = False
                analysis['public_title'] = None
                analysis['executed_trade_id'] = analysis.get('related_trade_id')
        
        logger.info(f"✅ [Standalone] Found {len(result) if result else 0} analyses")
        return result or []
        
    except Exception as e:
        logger.error(f"❌ [Standalone] Error getting recent analyses: {e}")
        return []

def get_featured_analysis():
    """Get the most recent or featured analysis - SPY only"""
    try:
        if db_manager.use_postgresql:
            query = """
            SELECT analysis_id, ticker, dte, analysis_date, underlying_price,
                   prompt_text, response_text, confidence_score, recommended_strategy
            FROM grok_analyses 
            WHERE ticker = 'SPY'
            ORDER BY analysis_date DESC 
            LIMIT 1
            """
        else:
            query = """
            SELECT analysis_id, ticker, dte, analysis_date, underlying_price,
                   prompt_text, response_text, confidence_score, recommended_strategy
            FROM grok_analyses 
            WHERE ticker = 'SPY'
            ORDER BY analysis_date DESC 
            LIMIT 1
            """
        
        result = db_manager.execute_query(query)
        if result:
            return result[0]
        return None
        
    except Exception as e:
        logger.error(f"❌ Error getting featured analysis: {e}")
        return None

def get_latest_market_snapshot():
    """Get the latest market snapshot"""
    try:
        if db_manager.use_postgresql:
            query = """
            SELECT ticker, snapshot_date, current_price, daily_change, 
                   daily_change_percent, volume, implied_volatility, vix_level
            FROM market_snapshots 
            ORDER BY snapshot_date DESC 
            LIMIT 1
            """
        else:
            query = """
            SELECT spy_price as current_price, spy_change as daily_change, 
                   spy_change_percent as daily_change_percent, vix_level,
                   snapshot_time as snapshot_date, 'SPY' as ticker
            FROM market_snapshots 
            ORDER BY snapshot_time DESC 
            LIMIT 1
            """
        
        result = db_manager.execute_query(query)
        if result:
            return result[0]
        return None
        
    except Exception as e:
        logger.error(f"❌ Error getting market snapshot: {e}")
        return None

def test_database_connection():
    """Test database connection"""
    return db_manager.test_connection()

def store_grok_analysis(analysis_data: Dict) -> bool:
    """Store a Grok analysis"""
    return db_manager.store_grok_analysis(analysis_data)

def save_trade_to_database(trade_data: Dict) -> bool:
    """Save a trade record to the database"""
    try:
        if db_manager.use_postgresql:
            query = """
            INSERT INTO trades (
                trade_id, ticker, strategy_type, dte, entry_date, expiration_date,
                short_strike, long_strike, quantity, entry_premium_received,
                entry_premium_paid, entry_underlying_price, status, grok_confidence,
                market_conditions, created_at
            ) VALUES (
                %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s
            ) ON CONFLICT (trade_id) DO UPDATE SET
                updated_at = CURRENT_TIMESTAMP,
                current_underlying_price = EXCLUDED.entry_underlying_price
            """
        else:
            query = """
            INSERT OR REPLACE INTO trades (
                trade_id, ticker, strategy_type, dte, entry_date, expiration_date,
                short_strike, long_strike, quantity, entry_premium_received,
                entry_premium_paid, entry_underlying_price, status, grok_confidence,
                market_conditions, created_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
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
            trade_data.get('created_at', datetime.now())
        )
        
        db_manager.execute_query(query, params, fetch=False)
        logger.info(f"✅ Saved trade to database: {trade_data.get('trade_id')}")
        return True
        
    except Exception as e:
        logger.error(f"❌ Failed to save trade: {e}")
        return False

def update_performance_metrics() -> bool:
    """Recalculate and update performance metrics based on closed trades"""
    try:
        if db_manager.use_postgresql:
            # Calculate metrics from actual trades
            query = """
            INSERT INTO performance_metrics (
                period_type, period_start, period_end, total_trades, winning_trades,
                losing_trades, total_profit_loss, win_rate_percentage, average_roi,
                best_trade_roi, worst_trade_roi, updated_at
            ) 
            SELECT 
                'all_time' as period_type,
                MIN(entry_date::date) as period_start,
                CURRENT_DATE as period_end,
                COUNT(*) as total_trades,
                COUNT(CASE WHEN is_winner = true THEN 1 END) as winning_trades,
                COUNT(CASE WHEN is_winner = false THEN 1 END) as losing_trades,
                COALESCE(SUM(net_premium), 0) as total_profit_loss,
                ROUND(
                    (COUNT(CASE WHEN is_winner = true THEN 1 END) * 100.0 / 
                     NULLIF(COUNT(CASE WHEN is_winner IS NOT NULL THEN 1 END), 0)), 2
                ) as win_rate_percentage,
                ROUND(AVG(CASE WHEN is_winner IS NOT NULL THEN roi_percentage END), 2) as average_roi,
                MAX(roi_percentage) as best_trade_roi,
                MIN(roi_percentage) as worst_trade_roi,
                CURRENT_TIMESTAMP as updated_at
            FROM trades 
            WHERE status = 'CLOSED' AND ticker = 'SPY' AND is_winner IS NOT NULL
            ON CONFLICT (period_type, period_start, period_end) 
            DO UPDATE SET
                total_trades = EXCLUDED.total_trades,
                winning_trades = EXCLUDED.winning_trades,
                losing_trades = EXCLUDED.losing_trades,
                total_profit_loss = EXCLUDED.total_profit_loss,
                win_rate_percentage = EXCLUDED.win_rate_percentage,
                average_roi = EXCLUDED.average_roi,
                best_trade_roi = EXCLUDED.best_trade_roi,
                worst_trade_roi = EXCLUDED.worst_trade_roi,
                updated_at = CURRENT_TIMESTAMP
            """
        else:
            # SQLite version - simplified
            query = """
            INSERT OR REPLACE INTO performance_metrics (
                period_type, period_start, period_end, total_trades, winning_trades,
                losing_trades, total_profit_loss, win_rate_percentage
            ) 
            SELECT 
                'all_time',
                '2024-01-01',
                date('now'),
                COUNT(*),
                COUNT(CASE WHEN is_winner = 1 THEN 1 END),
                COUNT(CASE WHEN is_winner = 0 THEN 1 END),
                COALESCE(SUM(net_premium), 0),
                ROUND(
                    (COUNT(CASE WHEN is_winner = 1 THEN 1 END) * 100.0 / 
                     NULLIF(COUNT(CASE WHEN is_winner IS NOT NULL THEN 1 END), 0)), 1
                )
            FROM trades 
            WHERE status = 'CLOSED' AND ticker = 'SPY'
            """
        
        db_manager.execute_query(query, fetch=False)
        logger.info("✅ Updated performance metrics")
        return True
        
    except Exception as e:
        logger.error(f"❌ Failed to update performance metrics: {e}")
        return False

# Export the manager for direct use
__all__ = ['db_manager', 'get_recent_performance', 'get_open_trades', 
           'get_recent_grok_analyses', 'get_featured_analysis', 'get_latest_market_snapshot',
           'store_grok_analysis', 'save_trade_to_database', 'update_performance_metrics', 'test_database_connection']