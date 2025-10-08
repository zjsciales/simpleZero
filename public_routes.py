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
    """Get current live trades for public display"""
    try:
        if not DATABASE_AVAILABLE:
            # Return mock data if database not available
            mock_trades = [
                {
                    'trade_id': 'SPY_2025_10_17_001',
                    'ticker': 'SPY',
                    'strategy_type': 'Bull Put Spread',
                    'short_strike': 565.00,
                    'long_strike': 560.00,
                    'expiration_date': '2025-10-17',
                    'current_itm_status': 'OTM',
                    'entry_premium_received': 1.20,
                    'grok_confidence': 85,
                    'days_to_expiration': 10
                },
                {
                    'trade_id': 'QQQ_2025_10_24_001',
                    'ticker': 'QQQ',
                    'strategy_type': 'Bear Call Spread',
                    'short_strike': 485.00,
                    'long_strike': 480.00,
                    'expiration_date': '2025-10-24',
                    'current_itm_status': 'OTM',
                    'entry_premium_received': 0.95,
                    'grok_confidence': 78,
                    'days_to_expiration': 17
                },
                {
                    'trade_id': 'IWM_2025_10_31_001',
                    'ticker': 'IWM',
                    'strategy_type': 'Bull Put Spread',
                    'short_strike': 200.00,
                    'long_strike': 195.00,
                    'expiration_date': '2025-10-31',
                    'current_itm_status': 'ITM',
                    'entry_premium_received': 1.50,
                    'grok_confidence': 62,
                    'days_to_expiration': 24
                },
                {
                    'trade_id': 'SPY_2025_11_07_001',
                    'ticker': 'SPY',
                    'strategy_type': 'Iron Condor',
                    'short_strike': 567.00,
                    'long_strike': 564.00,
                    'expiration_date': '2025-11-07',
                    'current_itm_status': 'OTM',
                    'entry_premium_received': 2.10,
                    'grok_confidence': 88,
                    'days_to_expiration': 31
                },
                {
                    'trade_id': 'DIA_2025_10_17_001',
                    'ticker': 'DIA',
                    'strategy_type': 'Bull Put Spread',
                    'short_strike': 425.00,
                    'long_strike': 420.00,
                    'expiration_date': '2025-10-17',
                    'current_itm_status': 'OTM',
                    'entry_premium_received': 0.85,
                    'grok_confidence': 81,
                    'days_to_expiration': 10
                }
            ]
            
            return jsonify({
                'success': True,
                'trades': mock_trades,
                'count': len(mock_trades),
                'source': 'mock',
                'last_updated': datetime.now().isoformat()
            })
        
        # Get live trades from database
        trades = get_open_trades()
        
        if trades:
            # Convert Decimal objects to float for JSON serialization
            for trade in trades:
                for key, value in trade.items():
                    if isinstance(value, Decimal):
                        trade[key] = float(value)
            
            return jsonify({
                'success': True,
                'trades': trades,
                'count': len(trades),
                'source': 'database',
                'last_updated': datetime.now().isoformat()
            })
        else:
            return jsonify({
                'success': True,
                'trades': [],
                'count': 0,
                'message': 'No live trades available'
            })
            
    except Exception as e:
        logger.error(f"❌ Error getting live trades: {e}")
        return jsonify({
            'success': False,
            'error': 'Internal server error'
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
        analysis = get_featured_analysis()
        
        if not analysis:
            # Fallback to most recent analysis
            recent_analyses = get_recent_grok_analyses(limit=1)
            if recent_analyses:
                analysis = recent_analyses[0]
        
        if analysis:
            # Convert Decimal objects to float for JSON serialization
            for key, value in analysis.items():
                if isinstance(value, Decimal):
                    analysis[key] = float(value)
            
            return jsonify({
                'success': True,
                'analysis': analysis,
                'source': 'database'
            })
        else:
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
        
        if not DATABASE_AVAILABLE:
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
        # Note: This would need to be implemented in the database module
        analyses = get_recent_grok_analyses(limit=per_page)
        
        if analyses:
            # Convert Decimal objects to float for JSON serialization
            for analysis in analyses:
                for key, value in analysis.items():
                    if isinstance(value, Decimal):
                        analysis[key] = float(value)
            
            return jsonify({
                'success': True,
                'analyses': analyses,
                'total': len(analyses),
                'page': page,
                'per_page': per_page,
                'source': 'database'
            })
        else:
            return jsonify({
                'success': True,
                'analyses': [],
                'total': 0,
                'page': page,
                'per_page': per_page
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