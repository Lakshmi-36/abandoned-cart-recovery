# Abandoned Cart Recovery & Conversion Attribution

A data-driven analytics dashboard built using **Python, Streamlit, MySQL, Pandas, and Plotly** to monitor abandoned shopping carts, campaign activity, messaging operations, customer consent, revenue attribution, and data quality.

## Project Overview

In e-commerce, customers often add products to their shopping carts but leave without completing their purchases. Businesses use abandoned-cart recovery strategies to encourage customers to return and complete their orders.

This project provides a centralized dashboard for monitoring cart activity, campaign operations, customer consent, order revenue, conversion attribution, and business-rule compliance.

The application connects to a MySQL database and presents data through interactive visualizations, searchable tables, and SQL-based validation reports.

**Application:** Recovery Control Center
**Database:** MySQL 8.4
**Connection mode:** Read-only monitoring

---

## Dashboard Sections

The application contains six main sections.

### 1. Control Center

Provides an overview of the project's key operational metrics.

Features:
- Total shopping carts
- Abandoned and active carts
- Messages sent and suppressed
- Paid orders and revenue metrics
- Cart status visualizations
- Messaging channel activity

**Purpose:** Help users understand the current state of cart activity, messaging operations, and revenue at a glance.

### 2. Cart Lifecycle

Provides tools to explore shopping carts and their associated information.

Features:
- Filter carts by status
- Search using cart and customer identifiers
- Inspect individual carts
- View associated cart-line items
- Review cart lifecycle information
- Examine abandonment-related rules

**Purpose:** Help users investigate cart records and understand their lifecycle.

### 3. Campaign Workspace

Provides an overview of campaign and messaging activity.

Features:
- Explore campaign records
- Review campaign performance data
- Examine messaging activity
- Analyze channel-related information
- View message event summaries

**Purpose:** Support analysis of campaign operations and messaging activity.

### 4. Consent Audit

Supports monitoring of customer consent and messaging compliance.

Features:
- Review consent-related information
- Examine message suppression
- Check consent validity at send time
- Investigate messaging frequency limits
- Identify potential compliance violations

**Purpose:** Help verify whether messaging operations follow the project's consent and frequency rules.

### 5. Business Rules & Data Quality

Runs SQL-based validation checks against the MySQL database.

Features:
- Validate customer, cart, campaign, send, and order ID formats
- Check relationships between database tables
- Validate cart lifecycle timestamps
- Check the 24-hour abandonment rule
- Validate consent at send time
- Check rolling seven-day messaging limits
- Identify duplicate conversion attribution
- Reconcile cart and order totals
- Check campaign-template channel consistency
- Validate message-event chronology
- Review attribution timing and credited revenue
- Export validation results to CSV

#### Validation Statuses

| Status | Meaning |
|---|---|
| PASS | The validation query returned zero matching records. |
| FAIL | The validation query found one or more matching records that require review. |
| ERROR | The validation query could not be executed. |

**Purpose:** Help identify data inconsistencies and monitor whether selected business rules are satisfied.

A passing check confirms only the specific condition tested by that query. It does not guarantee that the entire application or database is error-free.

### 6. Table Explorer

Provides a convenient interface for inspecting the project's database tables.

Features:
- Browse available database tables
- Inspect table schemas
- Preview records
- Choose a preview row limit
- Export selected data to CSV

**Purpose:** Make database exploration easier without requiring users to write SQL queries manually.

---

## Technology Stack

| Technology | Purpose |
|---|---|
| Python | Application logic and data processing |
| Streamlit | Interactive dashboard interface |
| MySQL 8.4 | Relational database |
| MySQL Connector/Python | Python-to-MySQL connectivity |
| Pandas | Data manipulation and tabular reporting |
| Plotly | Interactive data visualizations |
| SQL | Data retrieval, reconciliation, and validation |

---

## Database Overview

The project uses relational tables covering customers, shopping carts, cart items, sessions, consent events, campaigns, messaging, orders, and conversion attribution.

The database includes the following 16 tables:

1. `customers`
2. `consent_events`
3. `sessions`
4. `carts`
5. `cart_lines`
6. `cart_events`
7. `campaigns`
8. `message_templates`
9. `campaign_templates`
10. `campaign_carts`
11. `send_attempts`
12. `message_events`
13. `orders`
14. `order_lines`
15. `order_events`
16. `attributions`

These tables support operational reporting, relational integrity checks, financial reconciliation, and attribution analysis.

---

## Project Structure

```text
abandoned-cart-recovery/
│
├── app_recovery_control_center.py
├── sql/
│   ├── 08_validate_anomalies.sql
│   └── 10_validate_business_rules.sql
├── .env
├── .gitignore
└── README.md
```

This is an illustrative structure showing the main application and validation files. Your repository may contain additional SQL scripts and supporting files.

---

## Installation and Setup

### Prerequisites

Before running the application, install:

- Python 3.10 or a compatible version supported by your dependencies
- MySQL Server 8.4
- Git (optional, for version control)

### 1. Clone the repository

```bash
git clone <your-github-repository-url>
cd abandoned-cart-recovery
```

Replace the placeholder with your actual GitHub repository URL.

### 2. Create a virtual environment

For Windows PowerShell:

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
```

### 3. Install dependencies

```powershell
python -m pip install streamlit mysql-connector-python pandas plotly
```

### 4. Configure environment variables

Create a local `.env` file in the project root:

```env
DB_HOST=localhost
DB_PORT=3306
DB_USER=root
DB_PASSWORD=your_local_mysql_password
DB_NAME=abandoned_cart_full_db
```

Replace `your_local_mysql_password` with your local MySQL password.

The application must load these environment variables before attempting to connect to MySQL.

**Security reminder:** Never upload your `.env` file or database credentials to GitHub.

### 5. Configure the database

Create or import the project database using the SQL setup scripts supplied with your repository.

Ensure that the database contains all tables expected by the dashboard before starting the application.

**Important:** Do not rerun database-generation or initialization scripts against an existing database unless you have reviewed their effects.

### 6. Run the application

```powershell
streamlit run app_recovery_control_center.py
```

Open the local address displayed by Streamlit in your browser.

---

## Read-Only Database Monitoring

The dashboard is designed to retrieve and analyse information without modifying database records.

The application uses SQL queries to retrieve information for dashboard metrics, charts, tables, and validation results.

For additional protection, configure a dedicated MySQL account with only the permissions required to read the dashboard data.

The validation checks identify records matching defined conditions. Any data corrections should be reviewed and performed separately through an authorized process.

---

## Data Quality and Business Rules

The project includes validation checks for several important business rules, including:

- A 24-hour cart abandonment threshold
- A 168-hour attribution window
- A maximum of three sent messages per customer and channel in a rolling seven-day window
- Valid customer consent at send time
- Prevention of duplicate conversion attribution
- Consistent cart and order totals
- Valid relationships between database records
- Consistent campaign and template channels

Some checks depend on the availability and meaning of linked timestamps and identifiers. Results should be interpreted according to the validation query and the project's data model.

---

## Security Considerations

- Keep database credentials in a local `.env` file.
- Add `.env` and `.venv/` to `.gitignore`.
- Never publish passwords, API keys, or other secrets.
- Use read-only database permissions where possible.
- Avoid publishing personal or sensitive customer information.
- Review validation findings before attempting any data corrections.

---

## Future Enhancements

Potential improvements include:

- Time-series analysis of cart abandonment and campaign performance
- Recovery conversion-rate analysis using verified cart-to-order relationships
- More detailed campaign effectiveness comparisons
- Automated scheduled data-quality reports
- Attribution analysis using verified click and conversion timestamps
- Role-based access control
- Deployment to a hosted environment

---

## Conclusion

The **Abandoned Cart Recovery & Conversion Attribution** project combines relational database management, SQL validation, data analysis, and interactive visualization in one application.

It demonstrates how Python, MySQL, and Streamlit can be used to monitor e-commerce operations, investigate data-quality issues, and present business metrics through a centralized dashboard.

### Technologies

**Python · Streamlit · MySQL · SQL · Pandas · Plotly**