"""
TastyTrade Account Streamer for Order Management and Real-time Updates
====================================================================

This module provides websocket streaming capabilities for TastyTrade sandbox accounts.
It handles authentication, heartbeats, and real-time order/fill notifications.

Key Features:
- Websocket connection to TastyTrade sandbox streamer
- Authentication using OAuth tokens
- Automated heartbeat management
- Order status and fill monitoring
- Account balance and position updates
- Error handling and reconnection logic

Usage:
    from account_streamer import TastyTradeStreamer
    
    streamer = TastyTradeStreamer(access_token="your_token", account_numbers=["5WT00000"])
    streamer.connect()
    streamer.start_monitoring()
"""

import json
import time
import threading
import logging
from datetime import datetime, timedelta
from typing import List, Dict, Optional, Callable, Any
import config

# Import websocket library
try:
    import websocket
    WEBSOCKET_AVAILABLE = True
except ImportError:
    print("⚠️ websocket-client not installed. Run: pip install websocket-client")
    WEBSOCKET_AVAILABLE = False

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class TastyTradeStreamer:
    """
    TastyTrade Account Streamer for real-time order and account updates
    
    Handles websocket connections to TastyTrade sandbox/production streamers
    with proper authentication, heartbeats, and message handling.
    """
    
    def __init__(self, access_token: str, account_numbers: List[str], 
                 use_sandbox: bool = True, heartbeat_interval: int = 30):
        """
        Initialize the TastyTrade streamer
        
        Args:
            access_token: OAuth access token for authentication
            account_numbers: List of account numbers to monitor
            use_sandbox: Whether to use sandbox (True) or production (False)
            heartbeat_interval: Seconds between heartbeat messages (2-60)
        """
        if not WEBSOCKET_AVAILABLE:
            raise ImportError("websocket-client library is required. Install with: pip install websocket-client")
        
        self.access_token = access_token
        self.account_numbers = account_numbers
        self.use_sandbox = use_sandbox
        self.heartbeat_interval = max(2, min(60, heartbeat_interval))  # Clamp to 2-60 seconds
        
        # Websocket configuration
        self.host = "wss://streamer.cert.tastyworks.com" if use_sandbox else "wss://streamer.tastyworks.com"
        self.ws = None
        self.session_id = None
        self.is_connected = False
        self.is_authenticated = False
        
        # Threading and heartbeat management
        self.heartbeat_thread = None
        self.stop_heartbeat = threading.Event()
        self.last_heartbeat_response = None
        
        # Message handlers
        self.order_handler = None
        self.fill_handler = None
        self.balance_handler = None
        self.position_handler = None
        self.error_handler = None
        
        # Message storage for recent activity
        self.recent_messages = []
        self.max_messages = 50  # Keep last 50 messages
        self.message_lock = threading.Lock()
        
        # Request tracking
        self.request_counter = 0
        self.pending_requests = {}
        
        print(f"🔌 TastyTrade Streamer initialized")
        print(f"   📡 Host: {self.host}")
        print(f"   🏦 Accounts: {account_numbers}")
        print(f"   💓 Heartbeat: {heartbeat_interval}s")
        print(f"   🧪 Environment: {'SANDBOX' if use_sandbox else 'PRODUCTION'}")
    
    def connect(self) -> bool:
        """
        Establish websocket connection to TastyTrade streamer
        
        Returns:
            bool: True if connection successful, False otherwise
        """
        if not self.access_token:
            logger.error("❌ No access token provided")
            return False
        
        try:
            print("🔌 Connecting to TastyTrade streamer...")
            
            # Create websocket connection with proper callbacks
            websocket.enableTrace(False)  # Disable verbose debugging
            self.ws = websocket.WebSocketApp(
                self.host,
                on_open=self._on_open,
                on_message=self._on_message,
                on_error=self._on_error,
                on_close=self._on_close
            )
            
            # Start connection in a separate thread
            self.connection_thread = threading.Thread(
                target=self.ws.run_forever,
                daemon=True
            )
            self.connection_thread.start()
            
            # Wait for connection to establish (with timeout)
            timeout = 10  # 10 second timeout
            start_time = time.time()
            while not self.is_connected and (time.time() - start_time) < timeout:
                time.sleep(0.1)
            
            if self.is_connected:
                print("✅ Websocket connection established")
                return True
            else:
                logger.error("❌ Connection timeout")
                return False
                
        except Exception as e:
            logger.error(f"❌ Connection failed: {e}")
            return False
    
    def _on_open(self, ws):
        """Handle websocket connection opened"""
        print("🔗 Websocket connection opened")
        self.is_connected = True
        
        # Subscribe to account notifications
        self._subscribe_to_accounts()
    
    def _on_message(self, ws, message):
        """Handle incoming websocket messages"""
        try:
            data = json.loads(message)
            self._handle_message(data)
        except json.JSONDecodeError as e:
            logger.error(f"❌ Failed to parse message: {message[:200]}... Error: {e}")
        except Exception as e:
            logger.error(f"❌ Error handling message: {e}")
    
    def _on_error(self, ws, error):
        """Handle websocket errors"""
        logger.error(f"🚨 Websocket error: {error}")
        if self.error_handler:
            self.error_handler(error)
    
    def _on_close(self, ws, close_status_code, close_msg):
        """Handle websocket connection closed"""
        print(f"🔌 Websocket connection closed: {close_status_code} - {close_msg}")
        self.is_connected = False
        self.is_authenticated = False
        self._stop_heartbeat_thread()
    
    def _subscribe_to_accounts(self):
        """Subscribe to account notifications"""
        request_id = self._get_next_request_id()
        
        connect_message = {
            "action": "connect",
            "value": self.account_numbers,
            "auth-token": self.access_token,
            "request-id": request_id
        }
        
        print(f"📡 Subscribing to accounts: {self.account_numbers}")
        print(f"🔑 Using token: {self.access_token[:20]}..." if self.access_token else "❌ No token")
        print(f"🆔 Request ID: {request_id}")
        self._send_message(connect_message)
        self.pending_requests[request_id] = "connect"
    
    def _handle_message(self, data: Dict[str, Any]):
        """Process incoming messages from the streamer"""
        message_type = data.get('type')
        action = data.get('action')
        status = data.get('status')
        request_id = data.get('request-id')
        
        # Handle response messages
        if action and status:
            self._handle_response_message(data)
        # Handle notification messages
        elif message_type:
            self._handle_notification_message(data)
        else:
            logger.warning(f"🤷 Unknown message format: {data}")
    
    def _handle_response_message(self, data: Dict[str, Any]):
        """Handle response messages (connect, heartbeat confirmations)"""
        action = data.get('action')
        status = data.get('status')
        request_id = data.get('request-id')
        
        print(f"📨 Response: {action} - {status}")
        
        if action == "connect" and status == "ok":
            self.is_authenticated = True
            self.session_id = data.get('web-socket-session-id')
            accounts = data.get('value', [])
            print(f"✅ Connected to accounts: {accounts}")
            print(f"🆔 Session ID: {self.session_id}")
            
            # Start heartbeat after successful connection
            self._start_heartbeat_thread()
            
        elif action == "heartbeat" and status == "ok":
            self.last_heartbeat_response = datetime.now()
            print(f"💓 Heartbeat acknowledged at {self.last_heartbeat_response.strftime('%H:%M:%S')}")
            
        elif status != "ok":
            logger.error(f"❌ {action} failed: {data}")
            if self.error_handler:
                self.error_handler(data)
        
        # Clean up pending request
        if request_id and request_id in self.pending_requests:
            del self.pending_requests[request_id]
    
    def _handle_notification_message(self, data: Dict[str, Any]):
        """Handle notification messages (orders, fills, balances, positions)"""
        message_type = data.get('type')
        message_data = data.get('data', {})
        timestamp = data.get('timestamp')
        
        print(f"🔔 Notification: {message_type} at {timestamp}")
        
        if message_type == "Order":
            self._handle_order_notification(message_data, timestamp)
        elif message_type == "Fill":
            self._handle_fill_notification(message_data, timestamp)
        elif message_type == "AccountBalance":
            self._handle_balance_notification(message_data, timestamp)
        elif message_type == "Position":
            self._handle_position_notification(message_data, timestamp)
        else:
            print(f"📋 Other notification ({message_type}): {message_data}")
    
    def _handle_order_notification(self, order_data: Dict[str, Any], timestamp: int):
        """Handle order status updates"""
        order_id = order_data.get('id')
        status = order_data.get('status')
        account = order_data.get('account-number')
        symbol = order_data.get('underlying-symbol')
        
        # Store order message for UI display
        status_icon = "🟡" if status == "Received" else "🟢" if status == "Filled" else "🔵" if status == "Live" else "🔴"
        
        self._store_message({
            'type': 'Order',
            'category': 'info' if status in ['Received', 'Live'] else 'success' if status == 'Filled' else 'warning',
            'message': f"{status_icon} ORDER {status}: {symbol} (ID: {order_id})",
            'timestamp': timestamp,
            'data': order_data
        })
        
        print(f"📝 Order Update:")
        print(f"   🆔 ID: {order_id}")
        print(f"   📊 Status: {status}")
        print(f"   🏦 Account: {account}")
        print(f"   📈 Symbol: {symbol}")
        
        # Call custom order handler if provided
        if self.order_handler:
            self.order_handler(order_data, timestamp)
    
    def _handle_fill_notification(self, fill_data: Dict[str, Any], timestamp: int):
        """Handle order fill notifications"""
        # Store fill message for UI display
        fill_symbol = fill_data.get('underlying-symbol', 'Unknown')
        fill_quantity = fill_data.get('quantity', 0)
        fill_price = fill_data.get('price', 0)
        fill_id = fill_data.get('id', 'Unknown')
        
        self._store_message({
            'type': 'Fill',
            'category': 'success',
            'message': f"🟢 FILL: {fill_quantity} {fill_symbol} @ ${fill_price} (ID: {fill_id})",
            'timestamp': timestamp,
            'data': fill_data
        })
        
        print(f"✅ Fill Notification: {fill_data}")
        
        # Call custom fill handler if provided
        if self.fill_handler:
            self.fill_handler(fill_data, timestamp)
    
    def _store_message(self, message_data: Dict[str, Any]):
        """Store message for recent activity display"""
        with self.message_lock:
            # Add timestamp if not present
            if 'timestamp' not in message_data:
                message_data['timestamp'] = int(time.time() * 1000)
            
            # Add to beginning of list (most recent first)
            self.recent_messages.insert(0, message_data)
            
            # Keep only max_messages
            if len(self.recent_messages) > self.max_messages:
                self.recent_messages = self.recent_messages[:self.max_messages]
    
    def _handle_balance_notification(self, balance_data: Dict[str, Any], timestamp: int):
        """Handle account balance updates"""
        account = balance_data.get('account-number')
        print(f"💰 Balance Update for {account}: {balance_data}")
        
        # Call custom balance handler if provided
        if self.balance_handler:
            self.balance_handler(balance_data, timestamp)
    
    def _handle_position_notification(self, position_data: Dict[str, Any], timestamp: int):
        """Handle position updates"""
        symbol = position_data.get('underlying-symbol')
        quantity = position_data.get('quantity')
        print(f"📊 Position Update: {symbol} - {quantity} shares/contracts")
        
        # Call custom position handler if provided
        if self.position_handler:
            self.position_handler(position_data, timestamp)
    
    def _start_heartbeat_thread(self):
        """Start the heartbeat thread"""
        if self.heartbeat_thread and self.heartbeat_thread.is_alive():
            return
        
        print(f"💓 Starting heartbeat thread (every {self.heartbeat_interval}s)")
        self.stop_heartbeat.clear()
        self.heartbeat_thread = threading.Thread(target=self._heartbeat_loop, daemon=True)
        self.heartbeat_thread.start()
    
    def _stop_heartbeat_thread(self):
        """Stop the heartbeat thread"""
        if self.heartbeat_thread:
            print("💓 Stopping heartbeat thread")
            self.stop_heartbeat.set()
            self.heartbeat_thread = None
    
    def _heartbeat_loop(self):
        """Heartbeat loop to keep connection alive"""
        while not self.stop_heartbeat.is_set():
            if self.is_connected and self.is_authenticated:
                self._send_heartbeat()
            
            # Wait for interval or until stop signal
            self.stop_heartbeat.wait(self.heartbeat_interval)
    
    def _send_heartbeat(self):
        """Send heartbeat message to server"""
        request_id = self._get_next_request_id()
        
        heartbeat_message = {
            "action": "heartbeat",
            "auth-token": self.access_token,
            "request-id": request_id
        }
        
        self._send_message(heartbeat_message)
        self.pending_requests[request_id] = "heartbeat"
    
    def _send_message(self, message: Dict[str, Any]):
        """Send message to websocket server"""
        if not self.ws or not self.is_connected:
            logger.error("❌ Cannot send message: not connected")
            return False
        
        try:
            message_json = json.dumps(message)
            print(f"📤 Sending websocket message: {message_json}")
            self.ws.send(message_json)
            return True
        except Exception as e:
            logger.error(f"❌ Failed to send message: {e}")
            return False
    
    def _get_next_request_id(self) -> int:
        """Get next request ID for message tracking"""
        self.request_counter += 1
        return self.request_counter
    
    def set_order_handler(self, handler: Callable[[Dict[str, Any], int], None]):
        """Set custom order notification handler"""
        self.order_handler = handler
        print("📝 Custom order handler set")
    
    def set_fill_handler(self, handler: Callable[[Dict[str, Any], int], None]):
        """Set custom fill notification handler"""
        self.fill_handler = handler
        print("✅ Custom fill handler set")
    
    def set_balance_handler(self, handler: Callable[[Dict[str, Any], int], None]):
        """Set custom balance notification handler"""
        self.balance_handler = handler
        print("💰 Custom balance handler set")
    
    def set_position_handler(self, handler: Callable[[Dict[str, Any], int], None]):
        """Set custom position notification handler"""
        self.position_handler = handler
        print("📊 Custom position handler set")
    
    def set_error_handler(self, handler: Callable[[Any], None]):
        """Set custom error handler"""
        self.error_handler = handler
        print("🚨 Custom error handler set")
    
    def disconnect(self):
        """Disconnect from the streamer"""
        print("🔌 Disconnecting from streamer...")
        
        self._stop_heartbeat_thread()
        
        if self.ws:
            self.ws.close()
        
        self.is_connected = False
        self.is_authenticated = False
        print("✅ Disconnected from streamer")
    
    def is_healthy(self) -> bool:
        """Check if the streamer connection is healthy"""
        if not self.is_connected or not self.is_authenticated:
            return False
        
        # Check if we've received a recent heartbeat response
        if self.last_heartbeat_response:
            time_since_heartbeat = datetime.now() - self.last_heartbeat_response
            if time_since_heartbeat > timedelta(seconds=self.heartbeat_interval * 3):
                logger.warning("⚠️ No recent heartbeat response")
                return False
        
        return True
    
    def get_status(self) -> Dict[str, Any]:
        """Get current streamer status"""
        return {
            'connected': self.is_connected,
            'authenticated': self.is_authenticated,
            'session_id': self.session_id,
            'accounts': self.account_numbers,
            'host': self.host,
            'heartbeat_interval': self.heartbeat_interval,
            'last_heartbeat': self.last_heartbeat_response.isoformat() if self.last_heartbeat_response else None,
            'pending_requests': len(self.pending_requests),
            'healthy': self.is_healthy(),
            'recent_messages': self.get_recent_messages()
        }
    
    def get_recent_messages(self, limit: int = 20) -> List[Dict[str, Any]]:
        """Get recent order/fill messages for UI display"""
        with self.message_lock:
            return self.recent_messages[:limit]


def create_sandbox_streamer(access_token: str, account_numbers: List[str]) -> TastyTradeStreamer:
    """
    Convenience function to create a sandbox streamer instance
    
    Args:
        access_token: OAuth access token
        account_numbers: List of sandbox account numbers
    
    Returns:
        TastyTradeStreamer: Configured for sandbox environment
    """
    return TastyTradeStreamer(
        access_token=access_token,
        account_numbers=account_numbers,
        use_sandbox=True,
        heartbeat_interval=30
    )


def create_production_streamer(access_token: str, account_numbers: List[str]) -> TastyTradeStreamer:
    """
    Convenience function to create a production streamer instance
    
    Args:
        access_token: OAuth access token
        account_numbers: List of production account numbers
    
    Returns:
        TastyTradeStreamer: Configured for production environment
    """
    return TastyTradeStreamer(
        access_token=access_token,
        account_numbers=account_numbers,
        use_sandbox=False,
        heartbeat_interval=30
    )


# Global streamer instance for web app integration
_global_streamer = None
_streamer_lock = threading.Lock()


def get_streamer_status() -> Dict[str, Any]:
    """
    Get current status of the global streamer instance
    
    Returns:
        Dict containing streamer status information
    """
    with _streamer_lock:
        if _global_streamer is None:
            return {
                'active': False,
                'connected': False,
                'session_id': None,
                'accounts': [],
                'uptime': 0,
                'messages_received': 0,
                'recent_messages': []
            }
        
        return _global_streamer.get_status()


def start_global_streamer(access_token: str, account_numbers: List[str] = None) -> Dict[str, Any]:
    """
    Start the global streamer instance for web app integration
    
    Args:
        access_token: OAuth access token
        account_numbers: Optional list of account numbers
    
    Returns:
        Dict with success status and message
    """
    global _global_streamer
    
    with _streamer_lock:
        # Stop existing streamer if running
        if _global_streamer is not None:
            print("🔄 Stopping existing streamer...")
            _global_streamer.disconnect()
            _global_streamer = None
        
        try:
            # Create new streamer instance
            print("🚀 Starting new account streamer...")
            
            # Use sandbox by default (can be configured)
            use_sandbox = not config.IS_PRODUCTION
            
            _global_streamer = TastyTradeStreamer(
                access_token=access_token,
                account_numbers=account_numbers,
                use_sandbox=use_sandbox,
                heartbeat_interval=30
            )
            
            # Add default handlers for logging
            def default_order_handler(order_data, timestamp):
                symbol = order_data.get('underlying-symbol', 'Unknown')
                status = order_data.get('status', 'Unknown')
                print(f"📋 Order Update: {symbol} - {status}")
            
            def default_fill_handler(fill_data, timestamp):
                symbol = fill_data.get('underlying-symbol', 'Unknown')
                quantity = fill_data.get('quantity', 0)
                price = fill_data.get('price', 0)
                print(f"💰 Fill: {quantity} {symbol} @ ${price}")
            
            _global_streamer.set_order_handler(default_order_handler)
            _global_streamer.set_fill_handler(default_fill_handler)
            
            # Connect
            if _global_streamer.connect():
                return {
                    'success': True,
                    'message': 'Account streamer started successfully',
                    'status': _global_streamer.get_status()
                }
            else:
                _global_streamer = None
                return {
                    'success': False,
                    'message': 'Failed to connect to account streamer'
                }
                
        except Exception as e:
            _global_streamer = None
            return {
                'success': False,
                'message': f'Error starting streamer: {str(e)}'
            }


def stop_global_streamer() -> Dict[str, Any]:
    """
    Stop the global streamer instance
    
    Returns:
        Dict with success status and message
    """
    global _global_streamer
    
    with _streamer_lock:
        if _global_streamer is None:
            return {
                'success': True,
                'message': 'No streamer was running'
            }
        
        try:
            print("🛑 Stopping account streamer...")
            _global_streamer.disconnect()
            _global_streamer = None
            
            return {
                'success': True,
                'message': 'Account streamer stopped successfully'
            }
            
        except Exception as e:
            return {
                'success': False,
                'message': f'Error stopping streamer: {str(e)}'
            }


# Example usage and testing functions
if __name__ == "__main__":
    """
    Example usage of the TastyTrade Account Streamer
    """
    print("🧪 TastyTrade Account Streamer - Test Mode")
    
    # Example token and account (replace with real values for testing)
    test_token = "your_sandbox_access_token_here"
    test_accounts = ["5WT00000"]  # Replace with real sandbox account numbers
    
    def example_order_handler(order_data, timestamp):
        """Example order handler"""
        print(f"🎯 Custom Order Handler: Order {order_data.get('id')} is {order_data.get('status')}")
    
    def example_fill_handler(fill_data, timestamp):
        """Example fill handler"""
        print(f"🎯 Custom Fill Handler: Fill received - {fill_data}")
    
    # Create and configure streamer
    streamer = create_sandbox_streamer(test_token, test_accounts)
    streamer.set_order_handler(example_order_handler)
    streamer.set_fill_handler(example_fill_handler)
    
    # Connect and monitor
    if streamer.connect():
        print("🚀 Streamer connected successfully!")
        print("📊 Status:", streamer.get_status())
        
        # Keep running for demonstration (in practice, this would run indefinitely)
        try:
            print("🔄 Monitoring for 60 seconds... (Press Ctrl+C to stop)")
            time.sleep(60)
        except KeyboardInterrupt:
            print("\n👋 Stopping streamer...")
        finally:
            streamer.disconnect()
    else:
        print("❌ Failed to connect streamer")


def add_test_order_message() -> Dict[str, Any]:
    """Add a test order message for UI testing"""
    global _global_streamer
    
    with _streamer_lock:
        if _global_streamer is None:
            return {'success': False, 'message': 'No active streamer'}
        
        # Create test order message
        test_order = {
            'type': 'Order',
            'category': 'info',
            'message': '🟡 ORDER Received: SPY (ID: TEST123)',
            'timestamp': int(time.time() * 1000),
            'data': {
                'id': 'TEST123',
                'status': 'Received',
                'underlying-symbol': 'SPY',
                'account-number': '5WT00000'
            }
        }
        
        _global_streamer._store_message(test_order)
        return {'success': True, 'message': 'Test order message added'}


def add_test_fill_message() -> Dict[str, Any]:
    """Add a test fill message for UI testing"""
    global _global_streamer
    
    with _streamer_lock:
        if _global_streamer is None:
            return {'success': False, 'message': 'No active streamer'}
        
        # Create test fill message
        test_fill = {
            'type': 'Fill',
            'category': 'success',
            'message': '🟢 FILL: 1 SPY @ $575.50 (ID: FILL456)',
            'timestamp': int(time.time() * 1000),
            'data': {
                'id': 'FILL456',
                'quantity': 1,
                'price': 575.50,
                'underlying-symbol': 'SPY'
            }
        }
        
        _global_streamer._store_message(test_fill)
        return {'success': True, 'message': 'Test fill message added'}


def add_manual_order_message(order_data: Dict[str, Any]):
    """Add a manual order message when websocket isn't working"""
    global _global_streamer
    
    with _streamer_lock:
        if _global_streamer is None:
            print("⚠️ No active streamer to add manual order message")
            return {'success': False, 'message': 'No active streamer'}
        
        # Create manual order message
        order_id = order_data.get('id', 'Unknown')
        status = order_data.get('status', 'Submitted')
        symbol = order_data.get('underlying-symbol', 'Unknown')
        strategy = order_data.get('strategy_type', 'Unknown')
        
        status_icon = "🟡" if status in ["Received", "Routed"] else "🟢" if status == "Filled" else "🔵" if status == "Live" else "🔴"
        
        manual_order = {
            'type': 'Order',
            'category': 'info' if status in ['Received', 'Routed', 'Live'] else 'success' if status == 'Filled' else 'warning',
            'message': f"{status_icon} ORDER {status}: {symbol} {strategy} (ID: {order_id})",
            'timestamp': int(time.time() * 1000),
            'data': order_data
        }
        
        _global_streamer._store_message(manual_order)
        print(f"📝 Manual order message added: {symbol} {strategy} - {status}")
        return {'success': True}
