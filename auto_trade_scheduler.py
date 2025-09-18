"""
Integration script to add automated trading to the existing web application
Updated to use clean trading_scheduler.py instead of redundant automated_trader.py
"""

from trading_scheduler import AutomatedTradingScheduler
import threading
import logging

# Global scheduler instance
auto_trader_scheduler = None
scheduler_thread = None

def start_automated_trading(use_simple_grok=False):
    """
    Start the automated trading system
    Call this from your main app initialization
    
    Parameters:
    use_simple_grok: Whether to use the new simple Grok-4 analysis system (default False for stability)
    """
    global auto_trader_scheduler, scheduler_thread
    
    try:
        if auto_trader_scheduler is None:
            # Initialize scheduler with optional simple Grok system
            auto_trader_scheduler = AutomatedTradingScheduler(paper_trading=True, use_simple_grok=use_simple_grok)
            
            # Start the scheduler
            scheduler_thread = auto_trader_scheduler.start_scheduler()
            
            if scheduler_thread:
                grok_type = "simple Grok-4" if use_simple_grok else "comprehensive Grok"
                logging.info(f"🚀 Automated trading system integrated successfully using {grok_type}")
                return True
            else:
                logging.error("❌ Failed to start automated trading scheduler")
                return False
        else:
            logging.info("ℹ️ Automated trading system already running")
            return True
            
    except Exception as e:
        logging.error(f"❌ Error starting automated trading: {e}")
        return False

def stop_automated_trading():
    """
    Stop the automated trading system
    """
    global auto_trader_scheduler, scheduler_thread
    
    try:
        if auto_trader_scheduler:
            auto_trader_scheduler.stop_scheduler()
            auto_trader_scheduler = None
            scheduler_thread = None
            logging.info("🛑 Automated trading system stopped")
            return True
        else:
            logging.info("ℹ️ Automated trading system not running")
            return True
            
    except Exception as e:
        logging.error(f"❌ Error stopping automated trading: {e}")
        return False

def get_auto_trader_status():
    """
    Get the status of the automated trading system including detailed execution status
    """
    global auto_trader_scheduler
    
    if auto_trader_scheduler and auto_trader_scheduler.is_running:
        # Get detailed status from scheduler
        detailed_status = auto_trader_scheduler.get_status()
        
        return {
            'status': 'running',
            'last_trade_date': auto_trader_scheduler.last_trade_date.isoformat() if auto_trader_scheduler.last_trade_date else None,
            'paper_trading': auto_trader_scheduler.paper_trading,
            'detailed_status': detailed_status
        }
    else:
        return {
            'status': 'stopped',
            'last_trade_date': None,
            'paper_trading': None,
            'detailed_status': {
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
        }

def force_execute_trade():
    """
    Force execute a trade (for testing purposes)
    """
    global auto_trader_scheduler
    
    if auto_trader_scheduler:
        try:
            result = auto_trader_scheduler.force_execute_trade()
            return result
        except Exception as e:
            return {'success': False, 'message': f'Error: {e}'}
    else:
        return {'success': False, 'message': 'Automated trading scheduler not initialized'}

# For backward compatibility with existing Flask app
auto_trader = auto_trader_scheduler  # Alias for the Flask app that expects this variable
