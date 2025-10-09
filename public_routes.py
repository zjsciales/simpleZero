"""
Public API Routes for SimpleZero Trading Scoreboard
==================================================

This module provides public-facing API endpoints for the trading scoreboard,
live trades display, and Grok analysis library. These endpoints don't require
authentication and serve cached data for public consumption.
"""

from flask import Blueprint, jsonify, render_template, request
from datetime import datetime, timedelta
import logging
from typing import Dict, List, Optional
from decimal import Decimal

# Import database functions (with fallback if not available)
try:
    from unified_database import (
        get_recent_performance, get_open_trades, get_recent_grok_analyses,
        get_featured_analysis, get_latest_market_snapshot, test_database_connection
    )
    DATABASE_AVAILABLE = True
    print("✅ Using unified database")
except ImportError as e:
    print(f"⚠️ Unified database not available: {e}")
    # Try legacy database
    try:
        from public_database import (
            get_recent_performance, get_open_trades, get_recent_grok_analyses,
            get_featured_analysis, get_latest_market_snapshot, test_database_connection
        )
        DATABASE_AVAILABLE = True
        print("✅ Using legacy database")
    except ImportError:
        print(f"⚠️ No database available, using mock data")
        DATABASE_AVAILABLE = False

# Set up logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Create blueprint for public routes
public_routes = Blueprint('public', __name__)

# =============================================================================
# PUBLIC SCOREBOARD PAGE
# =============================================================================

@public_routes.route('/scoreboard')
def scoreboard():
    """Public trading scoreboard page"""
    return render_template('scoreboard.html')

@public_routes.route('/library')
def analysis_library():
    """Public Grok analysis library page"""
    return render_template('library.html')

# =============================================================================
# PUBLIC API ENDPOINTS
# =============================================================================

@public_routes.route('/api/public/performance')
def api_public_performance():
    """Get trading performance metrics for public display"""
    try:
        if not DATABASE_AVAILABLE:
            # Return mock data if database not available
            return jsonify({
                'success': True,
                'performance': {
                    'total_trades': 247,
                    'winning_trades': 189,
                    'losing_trades': 58,
                    'win_rate_percentage': 76.5,
                    'total_profit_loss': 12450.75,
                    'open_trades': 5
                },
                'source': 'mock'
            })
        
        # Get performance data from database
        performance = get_recent_performance()
        
        if performance:
            return jsonify({
                'success': True,
                'performance': performance,
                'source': 'database',
                'last_updated': datetime.now().isoformat()
            })
        else:
            return jsonify({
                'success': False,
                'error': 'No performance data available'
            }), 404
            
    except Exception as e:
        logger.error(f"❌ Error getting performance data: {e}")
        return jsonify({
            'success': False,
            'error': 'Internal server error'
        }), 500

@public_routes.route('/api/public/live-trades')
def api_public_live_trades():
    """Get current live trades directly from TastyTrade API"""
    try:
        # Import TastyTrade functions
        from tt import get_account_positions
        
        # Get live positions from TastyTrade
        positions = get_account_positions()
        
        if not positions:
            return jsonify({
                'success': True,
                'trades': [],
                'count': 0,
                'source': 'tastytrade_live',
                'last_updated': datetime.now().isoformat(),
                'message': 'No active positions found'
            })
        
        # Convert TastyTrade positions to trade format
        live_trades = []
        for position in positions:
            # Only include SPY for public display
            underlying = position.get('underlying_symbol') or position.get('ticker')
            if underlying != 'SPY':
                continue
            
            try:
                # Handle spreads vs individual positions
                if position.get('is_spread'):
                    # This is a detected spread
                    trade = {
                        'trade_id': position.get('trade_id', f"SPREAD_{underlying}_{position.get('expiration_date', '')}"),
                        'ticker': underlying,
                        'strategy_type': position.get('strategy_type', 'Spread'),
                        'short_strike': position.get('short_strike', 0),
                        'long_strike': position.get('long_strike', 0),
                        'expiration_date': position.get('expiration_date', ''),
                        'current_itm_status': position.get('current_itm_status', 'UNKNOWN'),
                        'entry_premium_received': position.get('entry_premium_received', 0),
                        'entry_premium_paid': position.get('entry_premium_paid', 0),
                        'expected_credit': position.get('net_premium', 0),
                        'grok_confidence': position.get('grok_confidence'),
                        'days_to_expiration': position.get('days_to_expiration', 0),
                        'quantity': len(position.get('positions', [])),  # Number of legs
                        'open_date': position.get('created_at', 'Unknown'),
                        'unrealized_pnl': sum(pos.get('unrealized_day_gain_loss', 0) for pos in position.get('positions', [])),
                        'is_spread': True
                    }
                else:
                    # Skip if not an option
                    if position.get('instrument_type') != 'Equity Option':
                        continue
                        
                    # Calculate strategy type based on position
                    if position['quantity'] > 0:
                        strategy_type = f"Long {position['option_type']}"
                    else:
                        strategy_type = f"Short {position['option_type']}"
                    
                    # Calculate days to expiration
                    exp_date = datetime.strptime(position['expiration_date'], '%Y-%m-%d')
                    days_to_exp = (exp_date - datetime.now()).days
                    
                    # Format trade for display
                    trade = {
                        'trade_id': f"TT_{position['underlying_symbol']}_{position['expiration_date']}_{position['strike_price']:.0f}{position['option_type'][0]}",
                        'ticker': position['underlying_symbol'],
                        'strategy_type': strategy_type,
                        'short_strike': position['strike_price'],
                        'long_strike': position['strike_price'],  # For single options
                        'expiration_date': position['expiration_date'],
                        'current_itm_status': 'UNKNOWN',  # Would need current market data
                        'entry_premium_received': abs(position['average_open_price'] * position['quantity'] * 100) if position['quantity'] < 0 else 0,
                        'entry_premium_paid': abs(position['average_open_price'] * position['quantity'] * 100) if position['quantity'] > 0 else 0,
                        'expected_credit': abs(position['average_open_price'] * position['quantity'] * 100),
                        'grok_confidence': None,  # No confidence for real trades
                        'days_to_expiration': days_to_exp,
                        'quantity': abs(position['quantity']),
                        'open_date': position.get('created_at', 'Unknown'),
                        'unrealized_pnl': position.get('unrealized_day_gain_loss', 0),
                        'is_spread': False
                    }
                
                live_trades.append(trade)
                
            except Exception as e:
                logger.warning(f"Error processing position {position.get('symbol', 'unknown')}: {e}")
                continue
        
        return jsonify({
            'success': True,
            'trades': live_trades,
            'count': len(live_trades),
            'source': 'tastytrade_live',
            'last_updated': datetime.now().isoformat()
        })
        
    except Exception as e:
        logger.error(f"Error getting live trades from TastyTrade: {e}")
        
        # Fallback to database if TastyTrade fails
        try:
            if DATABASE_AVAILABLE:
                from unified_database import get_open_trades
                db_trades = get_open_trades()
                
                return jsonify({
                    'success': True,
                    'trades': db_trades[:5],  # Limit to 5 most recent
                    'count': len(db_trades[:5]),
                    'source': 'database_fallback',
                    'last_updated': datetime.now().isoformat(),
                    'note': 'TastyTrade API unavailable, showing database trades'
                })
        except Exception as db_error:
            logger.error(f"Database fallback failed: {db_error}")
        
        return jsonify({
            'success': False,
            'error': 'Unable to retrieve live trades',
            'source': 'error'
        }), 500

@public_routes.route('/api/public/latest-analysis')
def api_public_latest_analysis():
    """Get latest Grok analysis for public display"""
    try:
        if not DATABASE_AVAILABLE:
            # Return mock data if database not available
            mock_analysis = {
                'analysis_id': 'grok_2025_10_07_001',
                'ticker': 'SPY',
                'dte': 0,
                'analysis_date': '2025-10-07T14:30:00',
                'response_text': """🎯 SPY 0DTE Analysis - October 7, 2025

MARKET SNAPSHOT:
• SPY: $571.80 (+0.41%, +$2.35)
• VIX: 16.8 (Low volatility environment)
• Market State: Bullish continuation pattern

TECHNICAL ANALYSIS:
• RSI: 58.2 (Neutral momentum)
• Bollinger Bands: Price near upper band
• Support: $568.50 | Resistance: $574.00

TRADE RECOMMENDATION:
Strategy: Bull Put Spread
• Sell $565 Put / Buy $560 Put
• Premium: ~$1.20 credit
• Max Profit: $120 (if SPY stays above $565)
• Max Risk: $380
• Probability: 85%

RATIONALE:
Strong technical setup with low volatility providing good premium collection opportunity. Market showing resilience above key support levels.""",
                'recommended_strategy': 'Bull Put Spread',
                'confidence_score': 85,
                'underlying_price': 571.80
            }
            
            return jsonify({
                'success': True,
                'analysis': mock_analysis,
                'source': 'mock'
            })
        
        # Get latest analysis from database
        print("🔍 Attempting to get featured analysis from database...")
        analysis = get_featured_analysis()
        print(f"📊 Featured analysis result: {analysis}")
        
        if not analysis:
            # Fallback to most recent analysis
            print("🔍 Featured analysis not found, trying recent analyses...")
            recent_analyses = get_recent_grok_analyses(limit=1)
            print(f"📊 Recent analyses result: {recent_analyses}")
            if recent_analyses:
                analysis = recent_analyses[0]
        
        if analysis:
            # Convert Decimal objects to float for JSON serialization
            for key, value in analysis.items():
                if isinstance(value, Decimal):
                    analysis[key] = float(value)
            
            print(f"✅ Returning analysis: {analysis.get('analysis_id', 'unknown')} from {analysis.get('analysis_date', 'unknown')}")
            return jsonify({
                'success': True,
                'analysis': analysis,
                'source': 'database'
            })
        else:
            print("❌ No analysis found in database")
            return jsonify({
                'success': False,
                'error': 'No analysis available'
            }), 404
            
    except Exception as e:
        logger.error(f"❌ Error getting latest analysis: {e}")
        return jsonify({
            'success': False,
            'error': 'Internal server error'
        }), 500

@public_routes.route('/api/public/analysis-library')
def api_public_analysis_library():
    """Get Grok analysis library for public browsing"""
    try:
        # Get pagination parameters
        page = request.args.get('page', 1, type=int)
        per_page = request.args.get('per_page', 20, type=int)
        ticker = request.args.get('ticker', None)
        
        logger.info(f"📚 Library request - DATABASE_AVAILABLE: {DATABASE_AVAILABLE}")
        
        if not DATABASE_AVAILABLE:
            logger.warning("⚠️ Database not available - returning mock data")
            # Return mock data if database not available
            mock_analyses = [
                {
                    'analysis_id': f'grok_2025_10_0{i}_001',
                    'ticker': 'SPY',
                    'dte': i % 3,
                    'analysis_date': f'2025-10-0{i}T14:30:00',
                    'public_title': f'SPY {i%3}DTE Analysis - Market Update',
                    'recommended_strategy': 'Bull Put Spread' if i % 2 == 0 else 'Bear Call Spread',
                    'confidence_score': 80 + (i % 10),
                    'underlying_price': 570 + i,
                    'is_featured': i == 1
                }
                for i in range(1, 8)
            ]
            
            return jsonify({
                'success': True,
                'analyses': mock_analyses,
                'total': len(mock_analyses),
                'page': page,
                'per_page': per_page,
                'source': 'mock'
            })
        
        # Get analyses from database with pagination
        logger.info(f"🔍 Fetching analyses from database (limit: {per_page})")
        analyses = get_recent_grok_analyses(limit=per_page)
        logger.info(f"📊 Database returned {len(analyses) if analyses else 0} analyses")
        
        if analyses:
            logger.info(f"🔍 First analysis sample: {analyses[0] if analyses else 'None'}")
            # Convert Decimal objects to float for JSON serialization
            for analysis in analyses:
                for key, value in analysis.items():
                    if isinstance(value, Decimal):
                        analysis[key] = float(value)
            
            logger.info(f"✅ Returning {len(analyses)} analyses from database")
            return jsonify({
                'success': True,
                'analyses': analyses,
                'total': len(analyses),
                'page': page,
                'per_page': per_page,
                'source': 'database'
            })
        else:
            logger.warning("⚠️ No analyses found in database - returning empty result")
            return jsonify({
                'success': True,
                'analyses': [],
                'total': 0,
                'page': page,
                'per_page': per_page,
                'source': 'database_empty'
            })
            
    except Exception as e:
        logger.error(f"❌ Error getting analysis library: {e}")
        return jsonify({
            'success': False,
            'error': 'Internal server error'
        }), 500

@public_routes.route('/api/public/market-snapshot')
def api_public_market_snapshot():
    """Get current market snapshot for public display"""
    try:
        if not DATABASE_AVAILABLE:
            # Return mock data if database not available
            mock_snapshot = {
                'spy_price': 571.80,
                'spy_change': 2.35,
                'spy_change_percent': 0.41,
                'spx_price': 5738.50,
                'qqq_price': 479.15,
                'vix_level': 16.8,
                'is_market_open': True,
                'snapshot_time': datetime.now().isoformat()
            }
            
            return jsonify({
                'success': True,
                'snapshot': mock_snapshot,
                'source': 'mock'
            })
        
        # Get market snapshot from database
        snapshot = get_latest_market_snapshot()
        
        if snapshot:
            # Convert Decimal objects to float for JSON serialization
            for key, value in snapshot.items():
                if isinstance(value, Decimal):
                    snapshot[key] = float(value)
            
            return jsonify({
                'success': True,
                'snapshot': snapshot,
                'source': 'database'
            })
        else:
            return jsonify({
                'success': False,
                'error': 'No market snapshot available'
            }), 404
            
    except Exception as e:
        logger.error(f"❌ Error getting market snapshot: {e}")
        return jsonify({
            'success': False,
            'error': 'Internal server error'
        }), 500

# =============================================================================
# UTILITY ENDPOINTS
# =============================================================================

@public_routes.route('/api/public/health')
def api_public_health():
    """Health check endpoint for public API"""
    try:
        health_status = {
            'status': 'healthy',
            'timestamp': datetime.now().isoformat(),
            'database': 'available' if DATABASE_AVAILABLE else 'unavailable',
            'version': '1.0.0'
        }
        
        if DATABASE_AVAILABLE:
            try:
                # Test database connection
                db_test = test_database_connection()
                health_status['database_test'] = 'passed' if db_test else 'failed'
            except Exception as e:
                health_status['database_test'] = f'error: {str(e)}'
        
        return jsonify(health_status)
        
    except Exception as e:
        return jsonify({
            'status': 'error',
            'error': str(e),
            'timestamp': datetime.now().isoformat()
        }), 500

# =============================================================================
# ERROR HANDLERS
# =============================================================================

@public_routes.errorhandler(404)
def not_found_error(error):
    return jsonify({
        'success': False,
        'error': 'Resource not found'
    }), 404

@public_routes.errorhandler(500)
def internal_error(error):
    return jsonify({
        'success': False,
        'error': 'Internal server error'
    }), 500