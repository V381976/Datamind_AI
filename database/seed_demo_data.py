import os
from pathlib import Path
import psycopg
from dotenv import load_dotenv

root = Path(__file__).resolve().parent.parent
os.chdir(root)
load_dotenv(root / ".env")

conn_str = os.getenv("POSTGRES_DATABASE_URL") or os.getenv("DATABASE_URL")
if not conn_str:
    raise SystemExit("No PostgreSQL connection string found")

with psycopg.connect(conn_str) as conn:
    with conn.cursor() as cur:
        cur.execute("DROP TABLE IF EXISTS orders CASCADE")
        cur.execute("DROP TABLE IF EXISTS revenues CASCADE")
        cur.execute("DROP TABLE IF EXISTS expenses CASCADE")
        cur.execute("DROP TABLE IF EXISTS invoices CASCADE")
        cur.execute("DROP TABLE IF EXISTS projects CASCADE")
        cur.execute("DROP TABLE IF EXISTS customers CASCADE")
        cur.execute("DROP TABLE IF EXISTS products CASCADE")
        cur.execute("DROP TABLE IF EXISTS employees CASCADE")
        cur.execute("DROP TABLE IF EXISTS departments CASCADE")
        cur.execute("DROP TABLE IF EXISTS companies CASCADE")

        cur.execute("""
        CREATE TABLE companies (
            company_id SERIAL PRIMARY KEY,
            company_name VARCHAR(200) NOT NULL,
            industry VARCHAR(100) NOT NULL,
            founded_date DATE NOT NULL,
            headquarters_city VARCHAR(100) NOT NULL,
            headquarters_country VARCHAR(100) NOT NULL,
            website VARCHAR(255),
            email VARCHAR(255),
            phone VARCHAR(50),
            description TEXT
        )""")

        cur.execute("""
        CREATE TABLE departments (
            department_id SERIAL PRIMARY KEY,
            company_id INTEGER NOT NULL REFERENCES companies(company_id),
            department_name VARCHAR(100) NOT NULL,
            budget NUMERIC(12,2) NOT NULL DEFAULT 0,
            headcount INTEGER NOT NULL DEFAULT 0
        )""")

        cur.execute("""
        CREATE TABLE employees (
            employee_id SERIAL PRIMARY KEY,
            company_id INTEGER NOT NULL REFERENCES companies(company_id),
            department_id INTEGER NOT NULL REFERENCES departments(department_id),
            first_name VARCHAR(100) NOT NULL,
            last_name VARCHAR(100) NOT NULL,
            email VARCHAR(255) NOT NULL,
            role VARCHAR(100) NOT NULL,
            salary NUMERIC(12,2) NOT NULL,
            status VARCHAR(50) NOT NULL,
            hire_date DATE NOT NULL
        )""")

        cur.execute("""
        CREATE TABLE products (
            product_id SERIAL PRIMARY KEY,
            company_id INTEGER NOT NULL REFERENCES companies(company_id),
            product_name VARCHAR(200) NOT NULL,
            category VARCHAR(100) NOT NULL,
            unit_price NUMERIC(10,2) NOT NULL,
            stock_quantity INTEGER NOT NULL,
            release_date DATE NOT NULL,
            status VARCHAR(50) NOT NULL
        )""")

        cur.execute("""
        CREATE TABLE customers (
            customer_id SERIAL PRIMARY KEY,
            company_id INTEGER NOT NULL REFERENCES companies(company_id),
            customer_name VARCHAR(200) NOT NULL,
            segment VARCHAR(100) NOT NULL,
            contact_name VARCHAR(200) NOT NULL,
            email VARCHAR(255) NOT NULL,
            phone VARCHAR(50),
            city VARCHAR(100) NOT NULL,
            country VARCHAR(100) NOT NULL,
            status VARCHAR(50) NOT NULL
        )""")

        cur.execute("""
        CREATE TABLE projects (
            project_id SERIAL PRIMARY KEY,
            company_id INTEGER NOT NULL REFERENCES companies(company_id),
            department_id INTEGER NOT NULL REFERENCES departments(department_id),
            project_manager_id INTEGER NOT NULL REFERENCES employees(employee_id),
            project_name VARCHAR(200) NOT NULL,
            budget NUMERIC(12,2) NOT NULL,
            start_date DATE NOT NULL,
            end_date DATE,
            status VARCHAR(50) NOT NULL
        )""")

        cur.execute("""
        CREATE TABLE invoices (
            invoice_id SERIAL PRIMARY KEY,
            company_id INTEGER NOT NULL REFERENCES companies(company_id),
            customer_id INTEGER NOT NULL REFERENCES customers(customer_id),
            invoice_number VARCHAR(50) NOT NULL UNIQUE,
            invoice_date DATE NOT NULL,
            due_date DATE NOT NULL,
            total_amount NUMERIC(12,2) NOT NULL,
            status VARCHAR(50) NOT NULL
        )""")

        cur.execute("""
        CREATE TABLE expenses (
            expense_id SERIAL PRIMARY KEY,
            company_id INTEGER NOT NULL REFERENCES companies(company_id),
            department_id INTEGER NOT NULL REFERENCES departments(department_id),
            project_id INTEGER REFERENCES projects(project_id),
            expense_date DATE NOT NULL,
            category VARCHAR(100) NOT NULL,
            description TEXT NOT NULL,
            amount NUMERIC(10,2) NOT NULL,
            status VARCHAR(50) NOT NULL
        )""")

        cur.execute("""
        CREATE TABLE revenues (
            revenue_id SERIAL PRIMARY KEY,
            company_id INTEGER NOT NULL REFERENCES companies(company_id),
            invoice_id INTEGER NOT NULL REFERENCES invoices(invoice_id),
            revenue_date DATE NOT NULL,
            amount NUMERIC(12,2) NOT NULL,
            source_type VARCHAR(100) NOT NULL
        )""")

        cur.execute("""
        CREATE TABLE orders (
            order_id SERIAL PRIMARY KEY,
            company_id INTEGER NOT NULL REFERENCES companies(company_id),
            customer_id INTEGER NOT NULL REFERENCES customers(customer_id),
            sales_rep_id INTEGER NOT NULL REFERENCES employees(employee_id),
            order_date DATE NOT NULL,
            expected_delivery_date DATE NOT NULL,
            status VARCHAR(50) NOT NULL,
            total_amount NUMERIC(12,2) NOT NULL
        )""")

        cur.execute(
            """INSERT INTO companies (company_name, industry, founded_date, headquarters_city, headquarters_country, website, email, phone, description)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s) RETURNING company_id""",
            (
                "Northstar Analytics",
                "Software & Data Services",
                "2015-03-14",
                "Seattle",
                "USA",
                "https://northstaranalytics.example",
                "hello@northstaranalytics.example",
                "+1-206-555-0142",
                "Fictional company focused on AI-powered analytics and operations software.",
            ),
        )
        company_id = cur.fetchone()[0]

        cur.executemany(
            "INSERT INTO departments (company_id, department_name, budget, headcount) VALUES (%s, %s, %s, %s)",
            [
                (company_id, "Engineering", 1200000.00, 18),
                (company_id, "Sales", 450000.00, 9),
                (company_id, "Finance", 280000.00, 6),
                (company_id, "Operations", 520000.00, 10),
            ],
        )

        employee_rows = [
            ("Maya", "Chen", "maya.chen@northstaranalytics.example", "Chief Technology Officer", 240000.00, "Active", "2015-03-16", 1),
            ("Daniel", "Rossi", "daniel.rossi@northstaranalytics.example", "VP of Engineering", 185000.00, "Active", "2017-06-01", 1),
            ("Aisha", "Patel", "aisha.patel@northstaranalytics.example", "Principal Engineer", 155000.00, "Active", "2018-08-20", 1),
            ("Lucas", "Nguyen", "lucas.nguyen@northstaranalytics.example", "Sales Director", 132000.00, "Active", "2016-11-02", 2),
            ("Olivia", "Martinez", "olivia.martinez@northstaranalytics.example", "Account Executive", 96000.00, "Active", "2019-02-14", 2),
            ("Noah", "Kim", "noah.kim@northstaranalytics.example", "Account Executive", 94000.00, "Active", "2020-07-09", 2),
            ("Sofia", "Ibrahim", "sofia.ibrahim@northstaranalytics.example", "Finance Director", 128000.00, "Active", "2017-01-19", 3),
            ("Ethan", "Brooks", "ethan.brooks@northstaranalytics.example", "Senior Accountant", 91000.00, "Active", "2018-10-03", 3),
            ("Priya", "Singh", "priya.singh@northstaranalytics.example", "Operations Manager", 118000.00, "Active", "2016-09-11", 4),
            ("Jordan", "Lee", "jordan.lee@northstaranalytics.example", "Operations Analyst", 84000.00, "Active", "2021-04-05", 4),
            ("Mina", "Osei", "mina.osei@northstaranalytics.example", "Customer Success Lead", 103000.00, "Active", "2019-12-16", 2),
            ("Nadia", "Garcia", "nadia.garcia@northstaranalytics.example", "Product Manager", 126000.00, "Active", "2018-05-24", 1),
        ]
        cur.executemany(
            "INSERT INTO employees (company_id, department_id, first_name, last_name, email, role, salary, status, hire_date) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)",
            [
                (company_id, dept_id, first, last, email, role, salary, status, hire_date)
                for first, last, email, role, salary, status, hire_date, dept_id in employee_rows
            ],
        )

        cur.executemany(
            "INSERT INTO products (company_id, product_name, category, unit_price, stock_quantity, release_date, status) VALUES (%s, %s, %s, %s, %s, %s, %s)",
            [
                (company_id, "Northstar Pulse", "Analytics", 249.99, 82, "2018-02-01", "Active"),
                (company_id, "Signal Board", "Operations", 189.99, 54, "2019-04-15", "Active"),
                (company_id, "Forecast AI", "Planning", 329.99, 38, "2020-06-10", "Active"),
                (company_id, "Atlas CRM", "Sales", 159.99, 67, "2017-09-22", "Active"),
                (company_id, "Ledger Sync", "Finance", 129.99, 47, "2021-01-15", "Active"),
                (company_id, "Insight Studio", "Analytics", 279.99, 22, "2022-03-08", "Active"),
            ],
        )

        cur.executemany(
            "INSERT INTO customers (company_id, customer_name, segment, contact_name, email, phone, city, country, status) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)",
            [
                (company_id, "BluePeak Retail", "Enterprise", "Rina Alvarez", "rina@bluepeak.example", "+1-415-555-0101", "San Francisco", "USA", "Active"),
                (company_id, "Harbor & Co", "Mid-Market", "Theo Brooks", "theo@harbor.example", "+1-617-555-0144", "Boston", "USA", "Active"),
                (company_id, "Aster Labs", "Startup", "Claire Hu", "claire@aster.example", "+1-206-555-0187", "Seattle", "USA", "Active"),
                (company_id, "Cedar Health", "Healthcare", "Marek Novak", "marek@cedar.example", "+1-312-555-0111", "Chicago", "USA", "Active"),
                (company_id, "Lumen Grid", "Enterprise", "Jules Martin", "jules@lumen.example", "+1-512-555-0133", "Austin", "USA", "Active"),
                (company_id, "Pineway Foods", "Retail", "Sana Khan", "sana@pineway.example", "+1-503-555-0178", "Portland", "USA", "Active"),
            ],
        )

        cur.execute("SELECT employee_id FROM employees WHERE company_id = %s ORDER BY employee_id", (company_id,))
        employee_ids = [row[0] for row in cur.fetchall()]
        cur.execute("SELECT department_id FROM departments WHERE company_id = %s ORDER BY department_id", (company_id,))
        department_ids = [row[0] for row in cur.fetchall()]
        project_rows = [
            ("Enterprise Analytics Rollout", department_ids[0], employee_ids[1], 250000.00, "2024-01-10", "2024-12-15", "Active"),
            ("Revenue Forecasting Upgrade", department_ids[0], employee_ids[2], 180000.00, "2024-02-15", "2024-10-31", "Active"),
            ("Sales Enablement Portal", department_ids[1], employee_ids[3], 140000.00, "2024-03-01", "2024-09-30", "Active"),
            ("Finance Automation Initiative", department_ids[2], employee_ids[6], 110000.00, "2024-04-20", "2024-08-31", "Active"),
        ]
        cur.executemany(
            "INSERT INTO projects (company_id, department_id, project_manager_id, project_name, budget, start_date, end_date, status) VALUES (%s, %s, %s, %s, %s, %s, %s, %s)",
            [(company_id, dept, pm, name, budget, start, end, status) for name, dept, pm, budget, start, end, status in project_rows],
        )

        cur.execute("SELECT customer_id FROM customers WHERE company_id = %s ORDER BY customer_id", (company_id,))
        customer_ids = [row[0] for row in cur.fetchall()]
        cur.execute("SELECT project_id FROM projects WHERE company_id = %s ORDER BY project_id", (company_id,))
        project_ids = [row[0] for row in cur.fetchall()]
        invoice_rows = [
            ("INV-1001", "2024-01-15", "2024-02-15", 12580.00, "Paid", customer_ids[0]),
            ("INV-1002", "2024-01-21", "2024-02-20", 8420.00, "Paid", customer_ids[1]),
            ("INV-1003", "2024-02-04", "2024-03-05", 15480.00, "Open", customer_ids[2]),
            ("INV-1004", "2024-02-14", "2024-03-15", 9900.00, "Paid", customer_ids[3]),
        ]
        cur.executemany(
            "INSERT INTO invoices (company_id, customer_id, invoice_number, invoice_date, due_date, total_amount, status) VALUES (%s, %s, %s, %s, %s, %s, %s)",
            [(company_id, cust_id, number, date, due, total, status) for number, date, due, total, status, cust_id in invoice_rows],
        )

        expense_rows = [
            (department_ids[0], project_ids[0], "2024-01-08", "Cloud hosting", "Azure costs", 6380.00, "Approved"),
            (department_ids[1], None, "2024-02-05", "Travel", "Regional sales meetup", 1820.00, "Approved"),
            (department_ids[2], None, "2024-02-16", "Accounting tools", "Audit support", 960.00, "Approved"),
            (department_ids[3], project_ids[3], "2024-03-01", "Operations tools", "Warehouse tools", 1475.00, "Approved"),
        ]
        cur.executemany(
            "INSERT INTO expenses (company_id, department_id, project_id, expense_date, category, description, amount, status) VALUES (%s, %s, %s, %s, %s, %s, %s, %s)",
            [(company_id, dept, proj, date, category, description, amount, status) for dept, proj, date, category, description, amount, status in expense_rows],
        )

        cur.execute("SELECT invoice_id, total_amount FROM invoices WHERE company_id = %s ORDER BY invoice_id", (company_id,))
        invoice_rows = cur.fetchall()
        cur.executemany(
            "INSERT INTO revenues (company_id, invoice_id, revenue_date, amount, source_type) VALUES (%s, %s, %s, %s, %s)",
            [(company_id, invoice_id, "2024-02-01", amount, "Invoice") for invoice_id, amount in invoice_rows],
        )

        cur.execute("SELECT customer_id FROM customers WHERE company_id = %s ORDER BY customer_id", (company_id,))
        customer_ids = [row[0] for row in cur.fetchall()]
        cur.execute("SELECT employee_id FROM employees WHERE company_id = %s ORDER BY employee_id", (company_id,))
        employee_ids = [row[0] for row in cur.fetchall()]
        order_rows = [
            (customer_ids[0], employee_ids[4], "2024-01-17", "2024-01-24", "Completed", 1240.00),
            (customer_ids[1], employee_ids[5], "2024-01-23", "2024-01-31", "Completed", 940.00),
            (customer_ids[2], employee_ids[4], "2024-02-07", "2024-02-14", "Shipped", 3180.00),
            (customer_ids[3], employee_ids[5], "2024-02-18", "2024-02-26", "Completed", 1590.00),
        ]
        cur.executemany(
            "INSERT INTO orders (company_id, customer_id, sales_rep_id, order_date, expected_delivery_date, status, total_amount) VALUES (%s, %s, %s, %s, %s, %s, %s)",
            [(company_id, cust_id, rep_id, order_date, delivery_date, status, amount) for cust_id, rep_id, order_date, delivery_date, status, amount in order_rows],
        )

        conn.commit()
        print("DEMO_DATA_LOADED")
