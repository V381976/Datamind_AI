"""Script to add multiple fields to database tables."""
import os
import sys
from pathlib import Path

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from database.connector import DatabaseConnector

def add_fields_to_tables():
    """Add multiple fields to users and orders tables."""
    connector = DatabaseConnector()
    connection = connector.connect()
    
    try:
        with connection.cursor() as cursor:
            # Add fields to users table
            print("Adding fields to users table...")
            user_fields = [
                ("phone", "VARCHAR(20)"),
                ("address", "TEXT"),
                ("date_of_birth", "DATE"),
                ("is_active", "BOOLEAN DEFAULT TRUE"),
                ("last_login", "TIMESTAMP"),
                ("profile_image", "TEXT"),
                ("bio", "TEXT")
            ]
            
            for field_name, field_type in user_fields:
                try:
                    cursor.execute(f"""
                        ALTER TABLE users 
                        ADD COLUMN IF NOT EXISTS {field_name} {field_type}
                    """)
                    print(f"  ✓ Added {field_name} to users table")
                except Exception as e:
                    print(f"  ✗ Failed to add {field_name}: {e}")
            
            # Add fields to orders table
            print("\nAdding fields to orders table...")
            order_fields = [
                ("shipping_address", "TEXT"),
                ("payment_method", "VARCHAR(50)"),
                ("discount_amount", "NUMERIC(10,2) DEFAULT 0"),
                ("tax_amount", "NUMERIC(10,2) DEFAULT 0"),
                ("notes", "TEXT"),
                ("updated_at", "TIMESTAMP"),
                ("order_number", "VARCHAR(50) UNIQUE")
            ]
            
            for field_name, field_type in order_fields:
                try:
                    cursor.execute(f"""
                        ALTER TABLE orders 
                        ADD COLUMN IF NOT EXISTS {field_name} {field_type}
                    """)
                    print(f"  ✓ Added {field_name} to orders table")
                except Exception as e:
                    print(f"  ✗ Failed to add {field_name}: {e}")
            
            connection.commit()
            print("\n✓ Database fields added successfully!")
            
    except Exception as e:
        connection.rollback()
        print(f"\n✗ Error: {e}")
        raise
    finally:
        connector.close()

if __name__ == "__main__":
    add_fields_to_tables()
