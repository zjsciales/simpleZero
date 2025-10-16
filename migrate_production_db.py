#!/usr/bin/env python3
"""
Production Database Migration Tool
Safely adds missing status column to requests table in Railway PostgreSQL
"""

import os
import psycopg2
from psycopg2.extras import RealDictCursor
import time

def migrate_production_database():
    """Add missing status column to production requests table"""
    
    # Get Railway DATABASE_URL from environment
    database_url = os.getenv('DATABASE_URL')
    if not database_url:
        print("❌ DATABASE_URL environment variable not set")
        print("Set it with: export DATABASE_URL='your_railway_postgres_url'")
        return False
    
    try:
        print("🔍 Connecting to Railway PostgreSQL...")
        
        # Connect with timeout
        conn = psycopg2.connect(
            database_url,
            connect_timeout=10,
            cursor_factory=RealDictCursor
        )
        conn.autocommit = True
        
        with conn.cursor() as cursor:
            # Set statement timeout
            cursor.execute("SET statement_timeout = '30s'")
            
            print("✅ Connected successfully!")
            
            # Check current table structure
            cursor.execute("""
                SELECT column_name 
                FROM information_schema.columns 
                WHERE table_name = 'requests' 
                ORDER BY ordinal_position
            """)
            
            current_columns = [row['column_name'] for row in cursor.fetchall()]
            print(f"📋 Current columns: {', '.join(current_columns)}")
            
            # Check if status column already exists
            if 'status' in current_columns:
                print("✅ status column already exists - no migration needed!")
                return True
            
            print("🔧 status column missing - adding it now...")
            
            # Add the missing status column
            cursor.execute("""
                ALTER TABLE requests 
                ADD COLUMN status VARCHAR(20) NOT NULL DEFAULT 'PENDING'
            """)
            
            print("✅ status column added successfully!")
            
            # Verify the column was added
            cursor.execute("""
                SELECT column_name, data_type, is_nullable, column_default 
                FROM information_schema.columns 
                WHERE table_name = 'requests' 
                ORDER BY ordinal_position
            """)
            
            updated_columns = cursor.fetchall()
            print(f"\n📋 Updated requests table structure ({len(updated_columns)} columns):")
            print("-" * 60)
            for col in updated_columns:
                nullable = "NULL" if col['is_nullable'] == 'YES' else "NOT NULL"
                default = f" DEFAULT {col['column_default']}" if col['column_default'] else ""
                print(f"  {col['column_name']:<15} {col['data_type']:<20} {nullable}{default}")
            
            # Test that we can now insert a request with status
            test_request_id = f"test_migration_{int(time.time())}"
            cursor.execute("""
                INSERT INTO requests (request_id, ticker, dte, status) 
                VALUES (%s, %s, %s, %s)
            """, (test_request_id, 'SPY', 1, 'PENDING'))
            
            print(f"\n✅ Test insert successful with request_id: {test_request_id}")
            
            # Clean up test record
            cursor.execute("DELETE FROM requests WHERE request_id = %s", (test_request_id,))
            print("✅ Test record cleaned up")
            
            return True
            
    except psycopg2.Error as e:
        print(f"❌ Database error: {e}")
        return False
    except Exception as e:
        print(f"❌ Unexpected error: {e}")
        return False
    finally:
        if 'conn' in locals():
            conn.close()
            print("\n🔌 Database connection closed")

if __name__ == "__main__":
    print("🚀 Production Database Migration Tool")
    print("=" * 50)
    
    success = migrate_production_database()
    
    if success:
        print("\n🎉 Migration completed successfully!")
        print("The requests table now has the status column and can accept new requests.")
    else:
        print("\n⚠️  Migration failed - please check the errors above")