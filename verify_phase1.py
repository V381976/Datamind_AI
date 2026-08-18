#!/usr/bin/env python3
"""Phase 1 verification script for PostgreSQL connection and tools."""

import os
import sys

# Add project root to path
sys.path.insert(0, str(os.path.dirname(os.path.abspath(__file__))))

from database.connector import DatabaseConnector
from database.schema import SchemaInspector
from database.tools import DatabaseToolRegistry


def test_connection():
    """Test PostgreSQL connection."""
    print("Testing PostgreSQL connection...")
    try:
        connector = DatabaseConnector()
        connector.validate_url()
        connection = connector.connect()
        
        # Verify connection with a read-only query
        with connection.cursor() as cursor:
            cursor.execute("SELECT current_database(), current_user, version()")
            result = cursor.fetchone()
            print(f"  Connected to: {result[0]}")
            print(f"  User: {result[1]}")
            print(f"  PostgreSQL version: {result[2].split()[1]}")
        
        connector.close()
        return True, "PASS"
    except Exception as e:
        return False, f"FAIL: {str(e)}"


def test_schema_discovery():
    """Test schema discovery."""
    print("\nTesting schema discovery...")
    try:
        connector = DatabaseConnector()
        connection = connector.connect()
        
        inspector = SchemaInspector(connection)
        schema_summary = inspector.get_safe_schema_summary()
        
        print(f"  Database: {schema_summary['database']}")
        print(f"  Schemas found: {len(schema_summary['schemas'])}")
        
        for schema in schema_summary['schemas']:
            print(f"    Schema: {schema['name']}")
            print(f"    Tables: {len(schema['tables'])}")
            for table in schema['tables']:
                print(f"      - {table['name']} ({len(table['columns'])} columns)")
        
        connector.close()
        return True, "PASS"
    except Exception as e:
        return False, f"FAIL: {str(e)}"


def test_count_records():
    """Test count_records tool."""
    print("\nTesting count_records...")
    try:
        connector = DatabaseConnector()
        connection = connector.connect()
        
        # Get first available table from public schema
        inspector = SchemaInspector(connection)
        schema_summary = inspector.get_safe_schema_summary()
        
        # Find public schema with tables
        public_schema = None
        for schema in schema_summary['schemas']:
            if schema['name'] == 'public' and schema['tables']:
                public_schema = schema
                break
        
        if not public_schema:
            return False, "FAIL: No tables found in public schema"
        
        table_name = public_schema['tables'][0]['name']
        print(f"  Testing table: {table_name}")
        
        tools = DatabaseToolRegistry(connection, allowed_tables={table_name})
        count = tools.count_records(table_name)
        
        print(f"  Record count: {count}")
        
        connector.close()
        return True, "PASS"
    except Exception as e:
        return False, f"FAIL: {str(e)}"


def test_find_records():
    """Test find_records tool."""
    print("\nTesting find_records...")
    try:
        connector = DatabaseConnector()
        connection = connector.connect()
        
        # Get first available table from public schema
        inspector = SchemaInspector(connection)
        schema_summary = inspector.get_safe_schema_summary()
        
        # Find public schema with tables
        public_schema = None
        for schema in schema_summary['schemas']:
            if schema['name'] == 'public' and schema['tables']:
                public_schema = schema
                break
        
        if not public_schema:
            return False, "FAIL: No tables found in public schema"
        
        table_name = public_schema['tables'][0]['name']
        print(f"  Testing table: {table_name}")
        
        tools = DatabaseToolRegistry(connection, allowed_tables={table_name})
        records = tools.find_records(table_name, limit=5)
        
        print(f"  Records found: {len(records)}")
        if records:
            print(f"  Sample record keys: {list(records[0].keys())}")
        
        connector.close()
        return True, "PASS"
    except Exception as e:
        return False, f"FAIL: {str(e)}"


def test_aggregate_data():
    """Test aggregate_data tool."""
    print("\nTesting aggregate_data...")
    try:
        connector = DatabaseConnector()
        connection = connector.connect()
        
        # Get first available table from public schema
        inspector = SchemaInspector(connection)
        schema_summary = inspector.get_safe_schema_summary()
        
        # Find public schema with tables
        public_schema = None
        for schema in schema_summary['schemas']:
            if schema['name'] == 'public' and schema['tables']:
                public_schema = schema
                break
        
        if not public_schema:
            return False, "FAIL: No tables found in public schema"
        
        table_name = public_schema['tables'][0]['name']
        print(f"  Testing table: {table_name}")
        
        tools = DatabaseToolRegistry(connection, allowed_tables={table_name})
        
        # Test COUNT operation
        result = tools.aggregate_data(table_name, operation="count")
        print(f"  COUNT result: {result}")
        
        connector.close()
        return True, "PASS"
    except Exception as e:
        return False, f"FAIL: {str(e)}"


def test_security():
    """Test security - no password exposure."""
    print("\nTesting security...")
    try:
        # Check that POSTGRES_DATABASE_URL is set
        db_url = os.getenv("POSTGRES_DATABASE_URL")
        if not db_url:
            return False, "FAIL: POSTGRES_DATABASE_URL not set"
        
        # Check that it's a PostgreSQL URL
        if not db_url.startswith(("postgresql://", "postgres://")):
            return False, "FAIL: Not a PostgreSQL URL"
        
        # Check that password is not exposed in logs (by checking the connector's safe logging)
        connector = DatabaseConnector()
        safe_url = connector._safe_url_for_logging(db_url)
        
        if "*****" not in safe_url:
            return False, "FAIL: Password not redacted in safe URL"
        
        if ":" in safe_url.split("@")[0] and "*****" not in safe_url.split("@")[0]:
            return False, "FAIL: Password may be exposed"
        
        print(f"  Safe URL format: {safe_url}")
        print("  Password is redacted in logs")
        
        return True, "PASS"
    except Exception as e:
        return False, f"FAIL: {str(e)}"


def main():
    """Run all tests and report results."""
    print("=" * 60)
    print("Phase 1 Verification - PostgreSQL Connection")
    print("=" * 60)
    
    results = {
        "PostgreSQL connection": test_connection(),
        "Schema discovery": test_schema_discovery(),
        "count_records": test_count_records(),
        "find_records": test_find_records(),
        "aggregate_data": test_aggregate_data(),
        "Security": test_security(),
    }
    
    print("\n" + "=" * 60)
    print("RESULTS")
    print("=" * 60)
    
    for test_name, (success, message) in results.items():
        print(f"{test_name}: {message}")
    
    # Return exit code based on results
    all_passed = all(success for success, _ in results.values())
    if not all_passed:
        sys.exit(1)


if __name__ == "__main__":
    main()
