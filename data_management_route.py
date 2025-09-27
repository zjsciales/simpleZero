@app.route('/data-management')
def data_management():
    """Data management dashboard to view persistent storage"""
    try:
        # Get session ID
        session_id = get_user_session_id()
        
        # Get user ID from database based on session ID
        user_id = db_storage.get_or_create_user_id(session_id=session_id)
        
        # Get all data for this user
        conn = db_storage.get_db_connection()
        cursor = conn.cursor()
        
        # Get user info
        cursor.execute("SELECT * FROM users WHERE id = ?", (user_id,))
        user_info = cursor.fetchone()
        
        # Get all data types for this user
        cursor.execute(
            "SELECT DISTINCT data_type FROM trade_data WHERE user_id = ? ORDER BY updated_at DESC", 
            (user_id,)
        )
        data_types = [row['data_type'] for row in cursor.fetchall()]
        
        # Get latest data for each type
        stored_data = {}
        for data_type in data_types:
            data = db_storage.get_latest_data(data_type, user_id=user_id)
            if data:
                stored_data[data_type] = data
        
        return render_template(
            'data_management.html',
            session_id=session_id,
            user_id=user_id,
            last_active=user_info['last_active'] if user_info else 'Unknown',
            stored_data=stored_data
        )
        
    except Exception as e:
        print(f"💥 Exception in data management: {e}")
        import traceback
        traceback.print_exc()
        return f"Error: {str(e)}", 500