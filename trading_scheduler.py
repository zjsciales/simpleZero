"""
Automated Trading Scheduler for 32DTE SPY Options
================================================

This module implements a comprehensive automated trading system that:
1. Runs every Monday to generate 32DTE SPY options trade recommendations
2. Integrates with the existing Grok AI analysis system
3. Prepares trades for user execution via the web interface
4. Maintains authentication and market data persistence
5. Provides detailed logging and error handling

The system automates everything up to trade execution, requiring manual user approval.
"""

import schedule
import time
import threading
import logging
from datetime import datetime, timedelta, timezone
from typing import Dict, Any, Optional
import json
import traceback

# Import existing modules
from grok import (
    GrokAnalyzer, 
    get_comprehensive_market_data,
    format_market_analysis_prompt_v7_comprehensive,
    GrokTradeParser,
    run_dte_aware_analysis
)
from dte_manager import DTEManager
from token_manager import get_tokens, validate_token
from market_data import get_available_dtes
import config
import db_storage

class AutomatedTradingScheduler:
    """
    Automated trading scheduler for 32DTE SPY options
    """
    
    def __init__(self, paper_trading=True, use_simple_grok=False):
        """
        Initialize the automated trading scheduler
        
        Parameters:
        paper_trading: Whether to use paper trading mode
        use_simple_grok: Whether to use simplified Grok analysis (for testing)
        """
        self.paper_trading = paper_trading
        self.use_simple_grok = use_simple_grok
        self.is_running = False
        self.scheduler_thread = None
        self.last_trade_date = None
        self.logger = self._setup_logging()
        
        # Initialize components
        self.grok_analyzer = GrokAnalyzer()
        self.dte_manager = DTEManager()
        self.trade_parser = GrokTradeParser(ticker="SPY")
        
        # Execution tracking
        self.current_execution_status = {
            'is_active': False,
            'current_phase': 'idle',
            'prompt_type': None,
            'request_start_time': None,
            'elapsed_time': 0,
            'last_completed': None,
            'error_message': None,
            'success': False,
            'trades_executed': 0
        }
        
        # Initialize database
        db_storage.init_db()
        
    def _setup_logging(self):
        """Set up logging for the automated trading scheduler"""
        logger = logging.getLogger(f"{__name__}.AutomatedTradingScheduler")
        if not logger.handlers:
            handler = logging.StreamHandler()
            formatter = logging.Formatter(
                '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
            )
            handler.setFormatter(formatter)
            logger.addHandler(handler)
            logger.setLevel(logging.INFO)
        return logger
    
    def find_optimal_dte(self, ticker: str = "SPY", target_dte: int = 32, tolerance: int = 5) -> Optional[int]:
        """
        Find the optimal DTE within our target range by checking available expiration dates
        
        Parameters:
        ticker: Stock ticker to check (default SPY)
        target_dte: Target days to expiration (default 32)
        tolerance: How many days +/- from target to accept (default 5, so 27-37 range)
        
        Returns:
        Optimal DTE if found, None if no suitable expiration available
        """
        try:
            self.logger.info(f"🎯 Finding optimal DTE for {ticker} (target: {target_dte}±{tolerance} days)")
            
            # Get all available DTEs from the market
            available_dtes = get_available_dtes(ticker)
            
            if not available_dtes:
                self.logger.error(f"❌ No available DTEs found for {ticker}")
                return None
            
            # Define our acceptable range
            min_dte = target_dte - tolerance  # 27 days minimum
            max_dte = target_dte + tolerance  # 37 days maximum
            
            # Filter DTEs within our range
            candidate_dtes = []
            for dte_info in available_dtes:
                dte = dte_info['dte']
                if min_dte <= dte <= max_dte:
                    candidate_dtes.append({
                        'dte': dte,
                        'expiration_date': dte_info['expiration_date'],
                        'option_count': dte_info.get('count', 0),
                        'distance_from_target': abs(dte - target_dte)
                    })
            
            if not candidate_dtes:
                self.logger.warning(f"⚠️ No DTEs found in range {min_dte}-{max_dte} days for {ticker}")
                # Log what's available for debugging
                available_range = [d['dte'] for d in available_dtes[:10]]
                self.logger.info(f"📅 Available DTEs: {available_range}")
                return None
            
            # Sort by preference:
            # 1. Closest to target DTE
            # 2. Higher option count (more liquidity)
            candidate_dtes.sort(key=lambda x: (x['distance_from_target'], -x['option_count']))
            
            optimal = candidate_dtes[0]
            
            self.logger.info(f"✅ Optimal DTE found: {optimal['dte']} days ({optimal['expiration_date']})")
            self.logger.info(f"   📊 Options available: {optimal['option_count']}")
            self.logger.info(f"   🎯 Distance from target: {optimal['distance_from_target']} days")
            
            # Log alternatives for transparency
            if len(candidate_dtes) > 1:
                alternatives = [f"{d['dte']}DTE" for d in candidate_dtes[1:4]]
                self.logger.info(f"   🔄 Alternatives: {', '.join(alternatives)}")
            
            return optimal['dte']
            
        except Exception as e:
            self.logger.error(f"❌ Error finding optimal DTE: {e}")
            # Fallback to target DTE if discovery fails
            self.logger.info(f"🔄 Falling back to target DTE: {target_dte}")
            return target_dte
    
    def start_scheduler(self) -> Optional[threading.Thread]:
        """
        Start the automated trading scheduler
        
        Returns:
        Threading object if successful, None if failed
        """
        try:
            if self.is_running:
                self.logger.info("📅 Scheduler already running")
                return self.scheduler_thread
            
            # Schedule Monday trades at 10:00 AM ET (after market opens and settles)
            schedule.every().monday.at("10:00").do(self._execute_weekly_trade_analysis)
            
            # Optional: Schedule a test run every day at 9:45 AM for development
            if not config.IS_PRODUCTION:
                schedule.every().day.at("09:45").do(self._execute_test_analysis)
            
            # Start the scheduler in a separate thread
            self.is_running = True
            self.scheduler_thread = threading.Thread(target=self._run_scheduler, daemon=True)
            self.scheduler_thread.start()
            
            self.logger.info("🚀 Automated trading scheduler started successfully")
            self.logger.info("📅 Weekly 32DTE trades scheduled for Mondays at 10:00 AM ET")
            
            if not config.IS_PRODUCTION:
                self.logger.info("🧪 Test analysis scheduled daily at 9:45 AM (development mode)")
            
            return self.scheduler_thread
            
        except Exception as e:
            self.logger.error(f"❌ Failed to start scheduler: {e}")
            return None
    
    def _run_scheduler(self):
        """Run the scheduler loop (runs in separate thread)"""
        while self.is_running:
            try:
                schedule.run_pending()
                time.sleep(60)  # Check every minute
            except Exception as e:
                self.logger.error(f"❌ Scheduler loop error: {e}")
                time.sleep(60)
    
    def stop_scheduler(self):
        """Stop the automated trading scheduler"""
        self.is_running = False
        schedule.clear()
        self.logger.info("🛑 Automated trading scheduler stopped")
    
    def _execute_weekly_trade_analysis(self):
        """Execute the weekly 32DTE trade analysis (Monday routine)"""
        self.logger.info("📊 Starting weekly 32DTE trade analysis...")
        self._update_execution_status('active', 'weekly_analysis', 'Starting weekly 32DTE analysis')
        
        try:
            # Find optimal DTE in the 28-35 day range (tighter for weekly consistency)
            optimal_dte = self.find_optimal_dte(ticker="SPY", target_dte=32, tolerance=3)
            
            if optimal_dte is None:
                error_msg = "No suitable expiration date found in 29-35 day range"
                self._update_execution_status('error', 'weekly_analysis', error_msg)
                self.logger.error(f"❌ {error_msg}")
                return
            
            # Execute comprehensive analysis with the optimal DTE
            result = self._execute_comprehensive_analysis(
                dte=optimal_dte, 
                ticker="SPY",
                analysis_type="weekly_32dte"
            )
            
            if result['success']:
                self.last_trade_date = datetime.now()
                success_msg = f"Weekly analysis completed successfully ({optimal_dte}DTE)"
                self._update_execution_status('completed', 'weekly_analysis', success_msg)
                self.logger.info(f"✅ {success_msg}")
            else:
                self._update_execution_status('error', 'weekly_analysis', f"Weekly analysis failed: {result.get('error', 'Unknown error')}")
                self.logger.error(f"❌ Weekly analysis failed: {result.get('error', 'Unknown error')}")
                
        except Exception as e:
            self._update_execution_status('error', 'weekly_analysis', f"Exception in weekly analysis: {e}")
            self.logger.error(f"❌ Exception in weekly analysis: {e}")
            traceback.print_exc()
    
    def _execute_test_analysis(self):
        """Execute test analysis (development mode only)"""
        if config.IS_PRODUCTION:
            return
            
        self.logger.info("🧪 Starting test analysis...")
        self._update_execution_status('active', 'test_analysis', 'Starting test analysis')
        
        try:
            # For testing, use a wider tolerance to find any suitable expiration
            optimal_dte = self.find_optimal_dte(ticker="SPY", target_dte=32, tolerance=10)
            
            if optimal_dte is None:
                # Fallback to shorter DTE for testing if no 32DTE available
                self.logger.warning("⚠️ No 32DTE available for testing, trying shorter DTE...")
                optimal_dte = self.find_optimal_dte(ticker="SPY", target_dte=7, tolerance=3)
                
            if optimal_dte is None:
                error_msg = "No suitable expiration date found for testing"
                self._update_execution_status('error', 'test_analysis', error_msg)
                self.logger.error(f"❌ {error_msg}")
                return
            
            result = self._execute_comprehensive_analysis(
                dte=optimal_dte,
                ticker="SPY", 
                analysis_type="test"
            )
            
            if result['success']:
                success_msg = f"Test analysis completed successfully ({optimal_dte}DTE)"
                self._update_execution_status('completed', 'test_analysis', success_msg)
                self.logger.info(f"✅ {success_msg}")
            else:
                self._update_execution_status('error', 'test_analysis', f"Test analysis failed: {result.get('error', 'Unknown error')}")
                self.logger.error(f"❌ Test analysis failed: {result.get('error', 'Unknown error')}")
                
        except Exception as e:
            self._update_execution_status('error', 'test_analysis', f"Exception in test analysis: {e}")
            self.logger.error(f"❌ Exception in test analysis: {e}")
    
    def _execute_comprehensive_analysis(self, dte: int, ticker: str = "SPY", analysis_type: str = "automated") -> Dict[str, Any]:
        """
        Execute comprehensive market analysis and trade recommendation generation
        
        Parameters:
        dte: Days to expiration target
        ticker: Stock ticker (default SPY)
        analysis_type: Type of analysis (weekly_32dte, test, manual)
        
        Returns:
        Dictionary with analysis results and trade recommendations
        """
        try:
            self.logger.info(f"🔍 Starting comprehensive analysis for {ticker} {dte}DTE")
            
            # Verify authentication
            if not self._verify_authentication():
                return {'success': False, 'error': 'Authentication failed'}
            
            # Phase 1: Market Data Collection
            self._update_execution_status('active', 'market_data', f'Collecting market data for {dte}DTE')
            self.logger.info(f"📊 Collecting comprehensive market data for {ticker} {dte}DTE...")
            
            market_data = get_comprehensive_market_data(
                ticker=ticker,
                dte=dte,
                include_full_options_chain=True  # Full chain for 32DTE analysis
            )
            
            if not market_data:
                return {'success': False, 'error': 'Failed to collect market data'}
            
            # Phase 2: Grok AI Analysis
            self._update_execution_status('active', 'grok_analysis', f'Running Grok AI analysis for {dte}DTE')
            self.logger.info(f"🤖 Generating Grok AI analysis for {ticker} {dte}DTE...")
            
            # Generate comprehensive prompt for 32DTE analysis
            analysis_prompt = format_market_analysis_prompt_v7_comprehensive(
                market_data=market_data,
                include_sentiment=True
            )
            
            # Send to Grok AI
            grok_response = self.grok_analyzer.send_to_grok(
                prompt=analysis_prompt,
                max_tokens=4000
            )
            
            if not grok_response:
                return {'success': False, 'error': 'Failed to get Grok AI response'}
            
            # Phase 3: Trade Parsing and Preparation
            self._update_execution_status('active', 'trade_parsing', f'Parsing trade recommendations for {dte}DTE')
            self.logger.info("🔧 Parsing trade recommendations...")
            
            # Parse trade recommendations
            parsed_trades = self.trade_parser.parse_grok_response(grok_response)
            
            # Phase 4: Data Storage
            self._update_execution_status('active', 'data_storage', 'Storing analysis results')
            self.logger.info("💾 Storing analysis results...")
            
            # Store comprehensive results
            storage_result = self._store_analysis_results(
                analysis_type=analysis_type,
                dte=dte,
                ticker=ticker,
                market_data=market_data,
                grok_response=grok_response,
                analysis_prompt=analysis_prompt,
                parsed_trades=parsed_trades
            )
            
            # Final result compilation
            result = {
                'success': True,
                'analysis_type': analysis_type,
                'dte': dte,
                'ticker': ticker,
                'timestamp': datetime.now().isoformat(),
                'market_data': market_data,
                'grok_response': grok_response,
                'analysis_prompt': analysis_prompt,
                'parsed_trades': parsed_trades,
                'storage_result': storage_result
            }
            
            self.logger.info(f"✅ Comprehensive analysis completed for {ticker} {dte}DTE")
            return result
            
        except Exception as e:
            self.logger.error(f"❌ Comprehensive analysis failed: {e}")
            traceback.print_exc()
            return {'success': False, 'error': f'Analysis failed: {e}'}
    
    def _verify_authentication(self) -> bool:
        """Verify TastyTrade authentication is valid"""
        try:
            # Check if we have a valid access token
            access_token, refresh_token = get_tokens()
            if not access_token:
                self.logger.error("❌ No access token available")
                return False
            
            # Validate the token
            is_valid = validate_token(access_token)
            if is_valid:
                self.logger.info("✅ Access token validation successful")
            else:
                self.logger.warning("⚠️ Access token validation failed - may need refresh")
                # Continue anyway as token might still work for some operations
            
            return True
            
        except Exception as e:
            self.logger.error(f"❌ Authentication verification failed: {e}")
            return False
    
    def _store_analysis_results(self, analysis_type: str, dte: int, ticker: str,
                              market_data: dict, grok_response: str, analysis_prompt: str,
                              parsed_trades: dict) -> dict:
        """Store comprehensive analysis results in database"""
        try:
            # Create session ID for this automated analysis
            session_id = f"auto_{analysis_type}_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
            
            # Store market data
            db_storage.store_data(
                data_type='market_data',
                data=market_data,
                session_id=session_id,
                ticker=ticker,
                dte=dte
            )
            
            # Store Grok response
            db_storage.store_data(
                data_type='grok_response',
                data={
                    'response': grok_response,
                    'prompt': analysis_prompt,
                    'analysis_type': analysis_type
                },
                session_id=session_id,
                ticker=ticker,
                dte=dte
            )
            
            # Store parsed trades
            db_storage.store_data(
                data_type='parsed_trades',
                data=parsed_trades,
                session_id=session_id,
                ticker=ticker,
                dte=dte
            )
            
            # Store automation metadata
            db_storage.store_data(
                data_type='automation_metadata',
                data={
                    'analysis_type': analysis_type,
                    'automation_timestamp': datetime.now().isoformat(),
                    'scheduler_version': '1.0',
                    'paper_trading': self.paper_trading,
                    'status': 'ready_for_execution'
                },
                session_id=session_id,
                ticker=ticker,
                dte=dte
            )
            
            self.logger.info(f"💾 Analysis results stored with session ID: {session_id}")
            self.logger.info(f"✅ Results available to dashboard via latest data lookup")
            
            return {
                'success': True,
                'session_id': session_id,
                'storage_timestamp': datetime.now().isoformat()
            }
            
        except Exception as e:
            self.logger.error(f"❌ Failed to store analysis results: {e}")
            return {'success': False, 'error': f'Storage failed: {e}'}
    
    def _update_execution_status(self, status: str, phase: str, message: str):
        """Update the current execution status"""
        self.current_execution_status.update({
            'is_active': status == 'active',
            'current_phase': phase,
            'last_update': datetime.now().isoformat(),
            'message': message,
            'success': status == 'completed',
            'error_message': message if status == 'error' else None
        })
        
        if status == 'active' and self.current_execution_status['request_start_time'] is None:
            self.current_execution_status['request_start_time'] = datetime.now().isoformat()
        
        if status in ['completed', 'error']:
            self.current_execution_status['last_completed'] = datetime.now().isoformat()
            if self.current_execution_status['request_start_time']:
                start_time = datetime.fromisoformat(self.current_execution_status['request_start_time'])
                elapsed = (datetime.now() - start_time).total_seconds()
                self.current_execution_status['elapsed_time'] = elapsed
    
    def get_status(self) -> dict:
        """Get the current status of the automated trading scheduler"""
        return {
            'is_running': self.is_running,
            'last_trade_date': self.last_trade_date.isoformat() if self.last_trade_date else None,
            'paper_trading': self.paper_trading,
            'execution_status': self.current_execution_status.copy(),
            'next_scheduled_run': self._get_next_scheduled_run(),
            'scheduler_info': {
                'thread_alive': self.scheduler_thread.is_alive() if self.scheduler_thread else False,
                'use_simple_grok': self.use_simple_grok
            }
        }
    
    def _get_next_scheduled_run(self) -> Optional[str]:
        """Get the next scheduled run time"""
        try:
            jobs = schedule.jobs
            if jobs:
                next_job = min(jobs, key=lambda job: job.next_run)
                return next_job.next_run.isoformat()
            return None
        except Exception:
            return None
    
    def force_execute_trade(self) -> dict:
        """Force execute a trade analysis (for testing purposes)"""
        self.logger.info("🔧 Force executing trade analysis...")
        
        try:
            # Find optimal DTE for force execution (wider tolerance for flexibility)
            optimal_dte = self.find_optimal_dte(ticker="SPY", target_dte=32, tolerance=8)
            
            if optimal_dte is None:
                error_msg = "No suitable expiration date found (24-40 day range)"
                self.logger.error(f"❌ {error_msg}")
                return {'success': False, 'error': error_msg}
            
            result = self._execute_comprehensive_analysis(
                dte=optimal_dte,
                ticker="SPY",
                analysis_type="manual_force"
            )
            
            if result['success']:
                result['optimal_dte'] = optimal_dte
                result['dte_discovery'] = f"Selected {optimal_dte}DTE as optimal expiration"
            
            return result
            
        except Exception as e:
            self.logger.error(f"❌ Force execution failed: {e}")
            return {'success': False, 'error': f'Force execution failed: {e}'}
    
    def get_latest_trade_recommendation(self) -> Optional[dict]:
        """Get the latest automated trade recommendation"""
        try:
            # Query database for latest automation results
            latest_data = db_storage.get_latest_data('parsed_trades')
            
            if latest_data:
                return {
                    'success': True,
                    'trade_data': latest_data,
                    'timestamp': latest_data.get('created_at'),
                    'ready_for_execution': True
                }
            else:
                return {
                    'success': False,
                    'message': 'No automated trade recommendations available'
                }
                
        except Exception as e:
            self.logger.error(f"❌ Failed to get latest trade recommendation: {e}")
            return {
                'success': False,
                'error': f'Failed to retrieve trade recommendation: {e}'
            }

# Singleton instance for module-level access
_scheduler_instance = None

def get_scheduler_instance() -> AutomatedTradingScheduler:
    """Get the global scheduler instance"""
    global _scheduler_instance
    if _scheduler_instance is None:
        _scheduler_instance = AutomatedTradingScheduler()
    return _scheduler_instance