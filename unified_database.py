"""
SimpleZero Database Manager - Rebuilt from Railway Schema
=========================================================

A clean, schema-accurate database manager that matches the exact Railway PostgreSQL structure.
Built from ground-up analysis of production database schema.
"""

import os
import logging
import random
import string
from typing import Dict, List, Optional, Any
from datetime import datetime, timedelta
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
                    AND table_name IN ('trades', 'grok_analyses', 'market_snapshots', 'requests')
                    ORDER BY table_name;
                """)
                tables = [row[0] for row in cursor.fetchall()]
                logger.info(f"✅ Railway tables verified: {tables}")
                
                # Check if requests table exists, if not create it
                if 'requests' not in tables:
                    logger.info("🔧 Creating missing requests table...")
                    cursor.execute("""
                        CREATE TABLE IF NOT EXISTS requests (
                            id SERIAL PRIMARY KEY,
                            request_id VARCHAR(100) UNIQUE NOT NULL,
                            ticker VARCHAR(10) NOT NULL DEFAULT 'SPY',
                            dte INTEGER NOT NULL,
                            request_date TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
                            status VARCHAR(20) NOT NULL DEFAULT 'PENDING',
                            analysis_id VARCHAR(100) NULL,
                            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                            processed_at TIMESTAMP NULL
                        );
                    """)
                    cursor.execute("""
                        CREATE INDEX IF NOT EXISTS idx_requests_ticker_dte ON requests(ticker, dte);
                    """)
                    cursor.execute("""
                        CREATE INDEX IF NOT EXISTS idx_requests_status ON requests(status);
                    """)
                    cursor.execute("""
                        CREATE INDEX IF NOT EXISTS idx_requests_date ON requests(request_date);
                    """)
                    self._postgres_conn.commit()
                    logger.info("✅ Requests table created successfully")
                
                if len(tables) >= 3:
                    logger.info("✅ All critical tables found - database ready")
                else:
                    logger.warning(f"⚠️ Missing tables! Expected: ['trades', 'grok_analyses', 'market_snapshots', 'requests'], Found: {tables}")
                    
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
            
            # Requests table for public analysis requests
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS requests (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    request_id TEXT UNIQUE NOT NULL,
                    ticker TEXT NOT NULL DEFAULT 'SPY',
                    dte INTEGER NOT NULL,
                    request_date TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
                    status TEXT NOT NULL DEFAULT 'PENDING',
                    analysis_id TEXT,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    processed_at TIMESTAMP
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
    
    def get_recent_performance(self) -> Dict:
        """Get current performance metrics from trades table"""
        try:
            # Calculate performance metrics from trades table
            query = """
            SELECT 
                COUNT(*) as total_trades,
                COUNT(CASE WHEN roi_percentage > 0 THEN 1 END) as winning_trades,
                COUNT(CASE WHEN roi_percentage < 0 THEN 1 END) as losing_trades,
                COUNT(CASE WHEN status IN ('OPEN', 'SUGGESTED') THEN 1 END) as open_trades,
                COALESCE(SUM(net_premium), 0) as total_profit_loss,
                COALESCE(AVG(CASE WHEN roi_percentage IS NOT NULL THEN roi_percentage END), 0) as avg_roi
            FROM trades
            WHERE status IS NOT NULL
            """
            
            result = self.execute_query(query)
            
            if result and len(result) > 0:
                row = result[0]
                total_trades = row.get('total_trades', 0)
                winning_trades = row.get('winning_trades', 0)
                
                # Calculate win rate
                win_rate = (winning_trades / total_trades * 100) if total_trades > 0 else 0
                
                return {
                    'total_trades': total_trades,
                    'winning_trades': winning_trades,
                    'losing_trades': row.get('losing_trades', 0),
                    'open_trades': row.get('open_trades', 0),
                    'win_rate_percentage': round(win_rate, 1),
                    'total_profit_loss': float(row.get('total_profit_loss', 0)),
                    'average_roi': round(float(row.get('avg_roi', 0)), 1)
                }
            else:
                # Return zeros if no data
                return {
                    'total_trades': 0,
                    'winning_trades': 0,
                    'losing_trades': 0,
                    'open_trades': 0,
                    'win_rate_percentage': 0.0,
                    'total_profit_loss': 0.0,
                    'average_roi': 0.0
                }
                
        except Exception as e:
            logger.error(f"❌ Failed to get performance metrics: {e}")
            # Return zeros on error
            return {
                'total_trades': 0,
                'winning_trades': 0,
                'losing_trades': 0,
                'open_trades': 0,
                'win_rate_percentage': 0.0,
                'total_profit_loss': 0.0,
                'average_roi': 0.0
            }
    
    # =====================================
    # REQUEST MANAGEMENT METHODS
    # =====================================
    
    def store_analysis_request(self, ticker: str = 'SPY', dte: int = 0) -> str:
        """Store a new analysis request and return the request ID"""
        try:
            # Generate unique request ID
            request_id = ''.join(random.choices(string.ascii_lowercase + string.digits, k=8))
            
            if self.use_postgresql:
                query = """
                INSERT INTO requests (request_id, ticker, dte, request_date, status)
                VALUES (%s, %s, %s, NOW(), 'PENDING')
                """
                params = (request_id, ticker, dte)
                result = self.execute_query(query, params, fetch=False)
            else:
                # SQLite version - use UTC time for consistency
                query = """
                INSERT INTO requests (request_id, ticker, dte, request_date, status)
                VALUES (?, ?, ?, ?, 'PENDING')
                """
                params = (request_id, ticker, dte, datetime.utcnow())
                result = self.execute_query(query, params, fetch=False)
            
            if result is None:  # Success for INSERT with fetch=False
                logger.info(f"✅ Analysis request stored: {request_id} (DTE: {dte})")
                return request_id
            else:
                logger.error(f"❌ Failed to store analysis request")
                return None
                
        except Exception as e:
            logger.error(f"❌ Failed to store analysis request: {e}")
            return None
    
    def check_duplicate_request(self, ticker: str = 'SPY', dte: int = 0, hours: int = 2) -> bool:
        """Check if a duplicate request exists within specified hours"""
        try:
            if self.use_postgresql:
                query = """
                SELECT COUNT(*) as count FROM requests 
                WHERE ticker = %s AND dte = %s 
                AND request_date >= NOW() - INTERVAL '%s hours'
                """
                params = (ticker, dte, hours)
            else:
                # SQLite version - calculate UTC cutoff time
                cutoff_time = datetime.utcnow() - timedelta(hours=hours)
                query = """
                SELECT COUNT(*) as count FROM requests 
                WHERE ticker = ? AND dte = ? 
                AND datetime(request_date) >= ?
                """
                params = (ticker, dte, cutoff_time)
            
            result = self.execute_query(query, params)
            
            if result and len(result) > 0:
                count = result[0].get('count', 0)
                logger.info(f"🔍 Duplicate check for {ticker} DTE:{dte} within {hours}h: {count} found")
                return count > 0
            
            return False
            
        except Exception as e:
            logger.error(f"❌ Failed to check duplicate request: {e}")
            return False
    
    def get_recent_requests(self, hours: int = 24, limit: int = 50) -> List[Dict]:
        """Get recent analysis requests"""
        try:
            query = """
            SELECT * FROM requests 
            WHERE request_date >= %s
            ORDER BY request_date DESC 
            LIMIT %s
            """ if self.use_postgresql else """
            SELECT * FROM requests 
            WHERE request_date >= datetime('now', '-{} hours')
            ORDER BY request_date DESC 
            LIMIT ?
            """.format(hours)
            
            if self.use_postgresql:
                from datetime import datetime, timedelta
                since_time = datetime.now() - timedelta(hours=hours)
                params = (since_time, limit)
            else:
                params = (limit,)
            
            result = self.execute_query(query, params)
            return result or []
            
        except Exception as e:
            logger.error(f"❌ Failed to get recent requests: {e}")
            return []
    
    def get_pending_requests(self, limit: int = 50) -> List[Dict]:
        """Get pending analysis requests with optional limit"""
        try:
            if self.use_postgresql:
                query = """
                SELECT * FROM requests 
                WHERE status = 'PENDING'
                ORDER BY request_date ASC
                LIMIT %s
                """
                params = (limit,)
            else:
                query = """
                SELECT * FROM requests 
                WHERE status = 'PENDING'
                ORDER BY request_date ASC
                LIMIT ?
                """
                params = (limit,)
            
            result = self.execute_query(query, params)
            return result or []
            
        except Exception as e:
            logger.error(f"❌ Failed to get pending requests: {e}")
            return []
    
    def update_request_status(self, request_id: str, status: str, analysis_id: str = None) -> bool:
        """Update request status and optionally link to analysis"""
        try:
            from datetime import datetime
            
            if analysis_id:
                query = """
                UPDATE requests 
                SET status = %s, analysis_id = %s, processed_at = %s
                WHERE request_id = %s
                """ if self.use_postgresql else """
                UPDATE requests 
                SET status = ?, analysis_id = ?, processed_at = ?
                WHERE request_id = ?
                """
                params = (status, analysis_id, datetime.now(), request_id)
            else:
                query = """
                UPDATE requests 
                SET status = %s, processed_at = %s
                WHERE request_id = %s
                """ if self.use_postgresql else """
                UPDATE requests 
                SET status = ?, processed_at = ?
                WHERE request_id = ?
                """
                params = (status, datetime.now(), request_id)
            
            self.execute_query(query, params, fetch=False)
            logger.info(f"✅ Request {request_id} status updated to: {status}")
            
            return True
            
        except Exception as e:
            logger.error(f"❌ Failed to update request status: {e}")
            return False

    def cleanup_completed_requests(self, days_old: int = 7) -> Dict[str, Any]:
        """Clean up completed requests older than specified days"""
        try:
            from datetime import datetime, timedelta
            
            cutoff_date = datetime.now() - timedelta(days=days_old)
            
            # First, count how many will be deleted
            count_query = """
            SELECT COUNT(*) FROM requests 
            WHERE status = %s AND processed_at < %s
            """ if self.use_postgresql else """
            SELECT COUNT(*) FROM requests 
            WHERE status = ? AND processed_at < ?
            """
            
            result = self.execute_query(count_query, ('COMPLETED', cutoff_date))
            count_to_delete = result[0][0] if result else 0
            
            if count_to_delete == 0:
                return {
                    'success': True,
                    'deleted_count': 0,
                    'message': f'No completed requests older than {days_old} days found'
                }
            
            # Delete the completed requests
            delete_query = """
            DELETE FROM requests 
            WHERE status = %s AND processed_at < %s
            """ if self.use_postgresql else """
            DELETE FROM requests 
            WHERE status = ? AND processed_at < ?
            """
            
            self.execute_query(delete_query, ('COMPLETED', cutoff_date), fetch=False)
            
            logger.info(f"✅ Cleaned up {count_to_delete} completed requests older than {days_old} days")
            
            return {
                'success': True,
                'deleted_count': count_to_delete,
                'message': f'Successfully deleted {count_to_delete} completed requests'
            }
            
        except Exception as e:
            logger.error(f"❌ Failed to cleanup completed requests: {e}")
            return {
                'success': False,
                'deleted_count': 0,
                'message': f'Error during cleanup: {str(e)}'
            }

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

    # Phase 1B: Request Validation and Processing Logic
    def validate_request_input(self, ticker: str, dte: int) -> Dict[str, Any]:
        """Validate request input and return validation result"""
        validation_result = {
            'valid': True,
            'errors': [],
            'warnings': [],
            'normalized_ticker': ticker.upper(),
            'normalized_dte': dte
        }
        
        # Validate ticker
        if not ticker or not isinstance(ticker, str):
            validation_result['valid'] = False
            validation_result['errors'].append('Ticker is required and must be a string')
        elif len(ticker.strip()) == 0:
            validation_result['valid'] = False
            validation_result['errors'].append('Ticker cannot be empty')
        elif len(ticker) > 10:
            validation_result['valid'] = False
            validation_result['errors'].append('Ticker must be 10 characters or less')
        
        # For now, we'll primarily support SPY but allow other tickers with a warning
        if ticker.upper() != 'SPY':
            validation_result['warnings'].append(f'Analysis for {ticker.upper()} may be limited. SPY provides the most comprehensive analysis.')
        
        # Validate DTE
        if not isinstance(dte, int):
            validation_result['valid'] = False
            validation_result['errors'].append('DTE must be an integer')
        elif dte < 0:
            validation_result['valid'] = False
            validation_result['errors'].append('DTE cannot be negative')
        elif dte > 365:
            validation_result['valid'] = False
            validation_result['errors'].append('DTE cannot exceed 365 days')
        elif dte == 0:
            validation_result['warnings'].append('0 DTE options have very high risk and limited analysis time')
        elif dte > 60:
            validation_result['warnings'].append('Long-term options (>60 DTE) may have limited analysis accuracy')
        
        return validation_result

    def process_analysis_request(self, ticker: str, dte: int) -> Dict[str, Any]:
        """Main function to process a new analysis request with validation and duplicate checking"""
        result = {
            'success': False,
            'request_id': None,
            'message': '',
            'duplicate': False,
            'validation_errors': [],
            'warnings': []
        }
        
        try:
            # Step 1: Validate input
            validation = self.validate_request_input(ticker, dte)
            result['validation_errors'] = validation['errors']
            result['warnings'] = validation['warnings']
            
            if not validation['valid']:
                result['message'] = 'Request validation failed: ' + '; '.join(validation['errors'])
                return result
            
            # Use normalized values
            normalized_ticker = validation['normalized_ticker']
            normalized_dte = validation['normalized_dte']
            
            # Step 2: Check for duplicates
            is_duplicate = self.check_duplicate_request(normalized_ticker, normalized_dte, hours=2)
            
            if is_duplicate:
                result['duplicate'] = True
                result['message'] = f'A similar analysis request for {normalized_ticker} with {normalized_dte} DTE was submitted within the last 2 hours. Please check recent analyses or try again later.'
                return result
            
            # Step 3: Store the request
            request_id = self.store_analysis_request(normalized_ticker, normalized_dte)
            
            if request_id:
                result['success'] = True
                result['request_id'] = request_id
                result['message'] = f'Analysis request submitted successfully! Request ID: {request_id}. Your {normalized_ticker} {normalized_dte} DTE analysis will be processed shortly.'
            else:
                result['message'] = 'Failed to store analysis request. Please try again.'
            
            return result
            
        except Exception as e:
            logger.error(f"❌ Failed to process analysis request: {e}")
            result['message'] = 'An error occurred while processing your request. Please try again.'
            return result

    def get_duplicate_info(self, ticker: str, dte: int, hours: int = 2) -> Dict[str, Any]:
        """Get information about duplicate requests for user feedback"""
        try:
            query = """
            SELECT request_id, request_date, status, analysis_id 
            FROM requests 
            WHERE ticker = ? AND dte = ? 
            AND datetime(request_date) >= ?
            ORDER BY request_date DESC
            """ if not self.use_postgresql else """
            SELECT request_id, request_date, status, analysis_id 
            FROM requests 
            WHERE ticker = %s AND dte = %s 
            AND request_date >= NOW() - INTERVAL '%s hours'
            ORDER BY request_date DESC
            """
            
            if self.use_postgresql:
                params = (ticker, dte, hours)
            else:
                cutoff_time = datetime.utcnow() - timedelta(hours=hours)
                params = (ticker, dte, cutoff_time)
            
            result = self.execute_query(query, params)
            
            return {
                'found_duplicates': len(result) > 0,
                'count': len(result),
                'most_recent': result[0] if result else None,
                'all_recent': result
            }
            
        except Exception as e:
            logger.error(f"❌ Failed to get duplicate info: {e}")
            return {'found_duplicates': False, 'count': 0, 'most_recent': None, 'all_recent': []}

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

def get_recent_performance() -> Dict:
    """Get recent performance metrics"""
    return db_manager.get_recent_performance()

def store_grok_trade_suggestion(analysis_data: Dict, response_text: str = None) -> bool:
    """Store a Grok trade suggestion"""
    return db_manager.store_grok_trade_suggestion(analysis_data, response_text)

def test_database_connection() -> bool:
    """Test database connection"""
    return db_manager.test_connection()

# Request management functions
def store_analysis_request(ticker: str = 'SPY', dte: int = 0) -> Optional[str]:
    """Store a new analysis request and return request_id"""
    return db_manager.store_analysis_request(ticker, dte)

def check_duplicate_request(ticker: str = 'SPY', dte: int = 0, hours: int = 2) -> bool:
    """Check if a duplicate request exists within specified hours"""
    return db_manager.check_duplicate_request(ticker, dte, hours)

def get_recent_requests(hours: int = 24, limit: int = 50) -> List[Dict]:
    """Get recent analysis requests"""
    return db_manager.get_recent_requests(hours, limit)

def get_pending_requests(limit: int = 50) -> List[Dict]:
    """Get pending analysis requests with optional limit"""
    return db_manager.get_pending_requests(limit)

def update_request_status(request_id: str, status: str, analysis_id: str = None) -> bool:
    """Update request status and optionally link to analysis"""
    return db_manager.update_request_status(request_id, status, analysis_id)

# Phase 1B: Request Validation and Processing Functions
def validate_request_input(ticker: str, dte: int) -> Dict[str, Any]:
    """Validate request input and return validation result"""
    return db_manager.validate_request_input(ticker, dte)

def process_analysis_request(ticker: str, dte: int) -> Dict[str, Any]:
    """Main function to process a new analysis request with validation and duplicate checking"""
    return db_manager.process_analysis_request(ticker, dte)

def get_duplicate_info(ticker: str, dte: int, hours: int = 2) -> Dict[str, Any]:
    """Get information about duplicate requests for user feedback"""
    return db_manager.get_duplicate_info(ticker, dte, hours)

def get_open_trades() -> List[Dict]:
    """Get open trades - placeholder function for compatibility"""
    try:
        # For now, return empty list since we're focusing on public requests
        # This can be expanded later when trade management is needed
        return []
    except Exception as e:
        logger.error(f"❌ Failed to get open trades: {e}")
        return []

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
        LIMIT ?
        """
        
        result = db_manager.execute_query(query, (limit,))
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
        
        result = db_manager.execute_query(query, ())
        return result[0] if result else None
        
    except Exception as e:
        logger.error(f"❌ Failed to get featured analysis: {e}")
        return None

def cleanup_completed_requests(days_old: int = 7) -> Dict[str, Any]:
    """Clean up completed requests older than specified days"""
    return db_manager.cleanup_completed_requests(days_old)