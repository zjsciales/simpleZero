"""
Database storage module for SimpleZero application.

This module provides persistent storage for trade data, market sentiment analysis,
Grok responses, and parsed trades using SQLite.

The data is stored in a SQLite database file and persists across application restarts
and user sessions.
"""

import sqlite3
import json
import os
import time
from datetime import datetime
import logging
from typing import Dict, Any, Optional, List, Tuple
import uuid

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Database configuration
DB_FILE = 'simple_zero_data.db'

def get_db_connection():
    """Get a connection to the SQLite database"""
    conn = sqlite3.connect(DB_FILE)
    conn.row_factory = sqlite3.Row  # Return rows as dictionaries
    return conn

def init_db():
    """Initialize the database schema if it doesn't exist"""
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        
        # Create users table for persistent user identification
        cursor.execute('''
        CREATE TABLE IF NOT EXISTS users (
            id TEXT PRIMARY KEY,
            email TEXT UNIQUE,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            last_active TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
        ''')
        
        # Create trade_data table for storing all JSON blobs
        cursor.execute('''
        CREATE TABLE IF NOT EXISTS trade_data (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id TEXT,
            data_type TEXT,
            ticker TEXT,
            dte INTEGER,
            data_json TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (user_id) REFERENCES users (id),
            UNIQUE (user_id, data_type, ticker, dte)
        )
        ''')
        
        # Create tokens table for persistent OAuth token storage
        # This enables automation to work across deployments on Railway
        cursor.execute('''
        CREATE TABLE IF NOT EXISTS tokens (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            environment TEXT NOT NULL,
            access_token TEXT,
            refresh_token TEXT,
            token_scopes TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            expires_at TIMESTAMP,
            UNIQUE (environment)
        )
        ''')
        
        conn.commit()
        logger.info(f"✅ Database initialized successfully: {DB_FILE}")
    except Exception as e:
        logger.error(f"❌ Database initialization error: {e}")
    finally:
        conn.close()

def get_or_create_user_id(email=None, session_id=None):
    """
    Get an existing user ID or create a new one
    
    Args:
        email (str, optional): User's email for persistent identification
        session_id (str, optional): Session ID as fallback
        
    Returns:
        str: User ID
    """
    conn = None
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        
        user_id = None
        
        # If email is provided, try to find user by email
        if email:
            cursor.execute("SELECT id FROM users WHERE email = ?", (email,))
            result = cursor.fetchone()
            if result:
                user_id = result['id']
                # Update last active timestamp
                cursor.execute("UPDATE users SET last_active = CURRENT_TIMESTAMP WHERE id = ?", (user_id,))
            else:
                # Create new user with email
                user_id = str(uuid.uuid4())
                cursor.execute(
                    "INSERT INTO users (id, email) VALUES (?, ?)",
                    (user_id, email)
                )
        elif session_id:
            # Use session ID to generate a stable user ID
            # This creates a persistent ID derived from the session
            # but still allows for anonymous usage
            user_id = f"anon_{session_id}"
            
            # Check if this user exists
            cursor.execute("SELECT id FROM users WHERE id = ?", (user_id,))
            if not cursor.fetchone():
                # Create new anonymous user
                cursor.execute(
                    "INSERT INTO users (id) VALUES (?)",
                    (user_id,)
                )
            else:
                # Update last active timestamp
                cursor.execute("UPDATE users SET last_active = CURRENT_TIMESTAMP WHERE id = ?", (user_id,))
        else:
            # Create totally anonymous user with random ID
            user_id = f"anon_{str(uuid.uuid4())}"
            cursor.execute(
                "INSERT INTO users (id) VALUES (?)",
                (user_id,)
            )
        
        conn.commit()
        return user_id
    except Exception as e:
        logger.error(f"❌ Error getting/creating user ID: {e}")
        # Fallback to a random ID
        return f"temp_{str(uuid.uuid4())}"
    finally:
        if conn:
            conn.close()

def store_data(data_type, data, user_id=None, session_id=None, ticker=None, dte=None):
    """
    Store data in the database
    
    Args:
        data_type (str): Type of data (e.g., 'parsed_trade', 'market_sentiment')
        data (dict): JSON-serializable data to store
        user_id (str, optional): User ID to associate with this data
        session_id (str, optional): Session ID as fallback if user_id not provided
        ticker (str, optional): Stock ticker symbol
        dte (int, optional): Days to expiration
        
    Returns:
        bool: Success status
    """
    try:
        # Get user ID
        if not user_id:
            user_id = get_or_create_user_id(session_id=session_id)
        
        # Extract ticker and DTE from data if not provided
        if not ticker and isinstance(data, dict):
            ticker = data.get('ticker') or data.get('underlying') or data.get('symbol')
        
        if dte is None and isinstance(data, dict):
            dte = data.get('dte')
            
            # Try to parse DTE from expiration date if available
            if dte is None and 'expiration_date' in data:
                try:
                    exp_date = datetime.strptime(data['expiration_date'], '%Y-%m-%d')
                    today = datetime.now()
                    dte = (exp_date - today).days
                except (ValueError, TypeError):
                    pass
        
        conn = get_db_connection()
        cursor = conn.cursor()
        
        # Convert data to JSON string
        data_json = json.dumps(data)
        
        # Use UPSERT to either insert new data or update existing
        cursor.execute('''
        INSERT INTO trade_data (user_id, data_type, ticker, dte, data_json, updated_at)
        VALUES (?, ?, ?, ?, ?, CURRENT_TIMESTAMP)
        ON CONFLICT (user_id, data_type, ticker, dte)
        DO UPDATE SET 
            data_json = excluded.data_json,
            updated_at = CURRENT_TIMESTAMP
        ''', (user_id, data_type, ticker, dte, data_json))
        
        conn.commit()
        logger.info(f"✅ Stored {data_type} data for user {user_id[:8]}... ({ticker or 'unknown'}, DTE: {dte or 'N/A'})")
        return True
    except Exception as e:
        logger.error(f"❌ Error storing data: {e}")
        return False
    finally:
        conn.close()

def get_data(data_type, user_id=None, session_id=None, ticker=None, dte=None):
    """
    Retrieve data from the database
    
    Args:
        data_type (str): Type of data to retrieve
        user_id (str, optional): User ID to retrieve data for
        session_id (str, optional): Session ID as fallback
        ticker (str, optional): Filter by ticker symbol
        dte (int, optional): Filter by days to expiration
        
    Returns:
        dict or None: Retrieved data or None if not found
    """
    conn = None
    try:
        # Get user ID if not provided
        if not user_id and session_id:
            user_id = get_or_create_user_id(session_id=session_id)
        
        if not user_id:
            logger.warning("⚠️ No user_id or session_id provided for data retrieval")
            return None
        
        conn = get_db_connection()
        cursor = conn.cursor()
        
        query = "SELECT data_json, created_at, updated_at FROM trade_data WHERE user_id = ? AND data_type = ?"
        params = [user_id, data_type]
        
        # Add filters if provided
        if ticker:
            query += " AND ticker = ?"
            params.append(ticker)
            
        if dte is not None:
            query += " AND dte = ?"
            params.append(dte)
            
        # Order by most recently updated
        query += " ORDER BY updated_at DESC LIMIT 1"
        
        cursor.execute(query, params)
        result = cursor.fetchone()
        
        if result:
            data = json.loads(result['data_json'])
            # Add metadata
            data['_metadata'] = {
                'created_at': result['created_at'],
                'updated_at': result['updated_at']
            }
            return data
        else:
            return None
    except Exception as e:
        logger.error(f"❌ Error retrieving data: {e}")
        return None
    finally:
        if conn:
            conn.close()

def get_latest_data(data_type, user_id=None, session_id=None):
    """
    Get the latest data of a particular type regardless of ticker or DTE
    Includes both user data and automation data for dashboard access
    
    Args:
        data_type (str): Type of data to retrieve
        user_id (str, optional): User ID
        session_id (str, optional): Session ID as fallback
        
    Returns:
        dict or None: Latest data or None if not found
    """
    conn = None
    try:
        # Get user ID if not provided
        if not user_id and session_id:
            user_id = get_or_create_user_id(session_id=session_id)
        
        conn = get_db_connection()
        cursor = conn.cursor()
        
        # First try to get user-specific data
        if user_id:
            cursor.execute(
                "SELECT data_json FROM trade_data WHERE user_id = ? AND data_type = ? ORDER BY updated_at DESC LIMIT 1",
                (user_id, data_type)
            )
            result = cursor.fetchone()
            if result:
                return json.loads(result['data_json'])
        
        # Fall back to latest automation data (for dashboard access to automated results)
        cursor.execute(
            "SELECT data_json FROM trade_data WHERE data_type = ? AND user_id LIKE 'automation@%' ORDER BY updated_at DESC LIMIT 1",
            (data_type,)
        )
        result = cursor.fetchone()
        if result:
            return json.loads(result['data_json'])
            
        # Final fallback: any data of this type
        cursor.execute(
            "SELECT data_json FROM trade_data WHERE data_type = ? ORDER BY updated_at DESC LIMIT 1",
            (data_type,)
        )
        result = cursor.fetchone()
        if result:
            return json.loads(result['data_json'])
            
        return None
        
    except Exception as e:
        logger.error(f"❌ Error retrieving latest data: {e}")
        return None
    finally:
        if conn:
            conn.close()

def clean_old_data(days_threshold=30):
    """
    Clean up old data from the database
    
    Args:
        days_threshold (int): Number of days after which data is considered old
        
    Returns:
        int: Number of records deleted
    """
    conn = None
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        
        # Delete data older than the threshold
        cursor.execute(
            "DELETE FROM trade_data WHERE updated_at < datetime('now', ?)",
            (f'-{days_threshold} days',)
        )
        
        deleted_count = cursor.rowcount
        conn.commit()
        
        logger.info(f"✅ Cleaned up {deleted_count} old records from the database")
        return deleted_count
    except Exception as e:
        logger.error(f"❌ Error cleaning old data: {e}")
        return 0
    finally:
        if conn:
            conn.close()

# Initialize the database when the module is imported
init_db()

# =====================================
# Token Storage Functions for Railway Persistence
# =====================================

def store_tokens(environment: str, access_token: str, refresh_token: str = None, 
                token_scopes: str = None, expires_at: datetime = None) -> bool:
    """
    Store OAuth tokens persistently in database for Railway deployment compatibility
    
    Args:
        environment (str): Environment name (DEVELOPMENT/PRODUCTION)
        access_token (str): OAuth access token
        refresh_token (str, optional): OAuth refresh token  
        token_scopes (str, optional): Space-separated token scopes
        expires_at (datetime, optional): Token expiration time
        
    Returns:
        bool: Success status
    """
    conn = None
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        
        # Use REPLACE to handle both insert and update
        cursor.execute('''
            REPLACE INTO tokens (environment, access_token, refresh_token, token_scopes, expires_at, updated_at)
            VALUES (?, ?, ?, ?, ?, CURRENT_TIMESTAMP)
        ''', (environment, access_token, refresh_token, token_scopes, expires_at))
        
        conn.commit()
        logger.info(f"✅ Tokens stored successfully for {environment}")
        return True
        
    except Exception as e:
        logger.error(f"❌ Error storing tokens for {environment}: {e}")
        return False
    finally:
        if conn:
            conn.close()

def get_stored_tokens(environment: str) -> Tuple[Optional[str], Optional[str]]:
    """
    Retrieve stored OAuth tokens from database
    
    Args:
        environment (str): Environment name (DEVELOPMENT/PRODUCTION)
        
    Returns:
        tuple: (access_token, refresh_token) - either may be None
    """
    conn = None
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        
        cursor.execute(
            "SELECT access_token, refresh_token FROM tokens WHERE environment = ? ORDER BY updated_at DESC LIMIT 1",
            (environment,)
        )
        
        row = cursor.fetchone()
        if row:
            return row['access_token'], row['refresh_token']
        else:
            return None, None
            
    except Exception as e:
        logger.error(f"❌ Error retrieving tokens for {environment}: {e}")
        return None, None
    finally:
        if conn:
            conn.close()

def get_token_info(environment: str) -> Optional[Dict[str, Any]]:
    """
    Get comprehensive token information including scopes and expiration
    
    Args:
        environment (str): Environment name
        
    Returns:
        dict: Token information or None if not found
    """
    conn = None
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        
        cursor.execute(
            "SELECT * FROM tokens WHERE environment = ? ORDER BY updated_at DESC LIMIT 1",
            (environment,)
        )
        
        row = cursor.fetchone()
        if row:
            return dict(row)
        else:
            return None
            
    except Exception as e:
        logger.error(f"❌ Error retrieving token info for {environment}: {e}")
        return None
    finally:
        if conn:
            conn.close()

def delete_tokens(environment: str) -> bool:
    """
    Delete stored tokens for an environment
    
    Args:
        environment (str): Environment name
        
    Returns:
        bool: Success status
    """
    conn = None
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        
        cursor.execute("DELETE FROM tokens WHERE environment = ?", (environment,))
        conn.commit()
        
        deleted_count = cursor.rowcount
        logger.info(f"🗑️ Deleted {deleted_count} token records for {environment}")
        return deleted_count > 0
        
    except Exception as e:
        logger.error(f"❌ Error deleting tokens for {environment}: {e}")
        return False
    finally:
        if conn:
            conn.close()

# Run cleanup periodically (you can call this from a scheduled task)
# clean_old_data(30)  # Remove data older than 30 days