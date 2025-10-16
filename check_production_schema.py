#!/usr/bin/env python3
"""
Production Database Schema Inspector
Connects to Railway PostgreSQL and examines the current requests table structure
"""

import os
import psycopg2
from psycopg2.extras import RealDictCursor
import time

def check_production_schema():
    """Check the production database schema for requests table"""
    
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
            
            # Check if requests table exists
            cursor.execute("""
                SELECT EXISTS (
                    SELECT 1 FROM information_schema.tables 
                    WHERE table_name = 'requests'
                )
            """)
            table_exists = cursor.fetchone()[0]
            
            if not table_exists:
                print("❌ requests table does not exist!")
                return False
            
            print("✅ requests table exists")
            
            # Get table structure
            cursor.execute("""
                SELECT column_name, data_type, is_nullable, column_default 
                FROM information_schema.columns 
                WHERE table_name = 'requests' 
                ORDER BY ordinal_position
            """)
            
            columns = cursor.fetchall()
            print(f"\n📋 Current requests table structure ({len(columns)} columns):")
            print("-" * 60)
            for col in columns:
                nullable = "NULL" if col['is_nullable'] == 'YES' else "NOT NULL"
                default = f" DEFAULT {col['column_default']}" if col['column_default'] else ""
                print(f"  {col['column_name']:<15} {col['data_type']:<20} {nullable}{default}")
            
            # Check specifically for status column
            status_exists = any(col['column_name'] == 'status' for col in columns)
            
            if status_exists:
                print("\n✅ status column EXISTS - schema should be good!")
            else:
                print("\n❌ status column MISSING - this is the problem!")
                print("\n🔧 To fix this, run in Railway PostgreSQL console:")
                print("   ALTER TABLE requests ADD COLUMN status VARCHAR(20) NOT NULL DEFAULT 'PENDING';")
            
            # Show sample data if any exists
            cursor.execute("SELECT COUNT(*) FROM requests")
            count = cursor.fetchone()[0]
            print(f"\n📊 Total requests in table: {count}")
            
            if count > 0:
                cursor.execute("SELECT * FROM requests LIMIT 3")
                samples = cursor.fetchall()
                print("\n📄 Sample requests:")
                for i, req in enumerate(samples, 1):
                    print(f"  {i}: {dict(req)}")
            
            return status_exists
            
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
    print("🚀 Production Database Schema Inspector")
    print("=" * 50)
    
    success = check_production_schema()
    
    if success:
        print("\n🎉 Schema check completed successfully!")
    else:
        print("\n⚠️  Schema issues detected - migration needed")