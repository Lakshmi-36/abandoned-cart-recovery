# AI Prompt History
## Project: Abandoned Cart Recovery & Conversion Attribution

### 1. Overview

AI tools were used during development to clarify requirements, explore implementation approaches, troubleshoot issues, and improve parts of the project. The main use was to get suggestions and explanations while working on the database, synthetic data, dashboard, and validation queries.

The prompts below are representative summaries of the types of questions asked during development, rather than a complete transcript of the original conversations.

### 2. Understanding the Project Requirements

**Purpose:** Clarify the main features and decide what the project should cover.

**Example prompts:**
- What are the main components of an abandoned cart recovery system?
- What business rules should be considered when designing this project?
- How can conversion attribution be tracked after a recovery message is sent?

### 3. Database Design and SQL

**Purpose:** Get suggestions for structuring the database and improving SQL implementation.

**Example prompts:**
- How should I organize the MySQL tables for customers, carts, campaigns, messages, and orders?
- Are the primary keys and foreign keys correctly connected?
- What constraints can help maintain data consistency?
- How can I check whether the tables and relationships are working as expected?

### 4. Generating Test Data

**Purpose:** Create sample data to test different scenarios without relying on real customer information.

**Example prompts:**
- How can I generate realistic synthetic data for this project?
- How do I make sure the generated data remains consistent across related tables?
- How can I use a fixed random seed so the results are reproducible?
- What checks can I run to verify the generated records?

### 5. Implementing Business Rules

**Purpose:** Clarify the logic behind cart abandonment, recovery messages, and conversion tracking.

**Example prompts:**
- How should the 24-hour cart abandonment rule work?
- How can I check customer consent before sending recovery messages?
- How can I validate the limit of three successful messages per customer per channel within seven days?
- How should the LAST_CLICK attribution model work within a 168-hour window?

### 6. Dashboard Improvements

**Purpose:** Get guidance on presenting project data in a simple and understandable way.

**Example prompts:**
- How can I connect my Streamlit dashboard to MySQL?
- What information would be useful to display for abandoned carts and recovery campaigns?
- How can I add a table explorer to view database records?
- How can I keep dashboard queries read-only?

### 7. SQL Validation and Debugging

**Purpose:** Investigate potential data inconsistencies and verify whether the business rules are being followed.

**Example prompts:**
- How can I identify recovery messages sent after a customer opts out?
- How can I check for carts marked as abandoned after a purchase?
- How can I find duplicate conversion attribution records?
- How can I identify cases where cart totals do not match their line-item quantities?
- How can I validate these issues using SELECT queries without modifying the data?

### 8. Schema and Code Consistency

**Purpose:** Resolve inconsistencies between project files and avoid unnecessary changes to existing data.

**Example prompts:**
- How can I compare the database schema with the SQL creation scripts?
- What is the best way to check whether the data dictionary matches the actual tables?
- How can I fix a specific inconsistency without changing unrelated parts of the project?
- What checks should I perform before making changes to the database?

### 9. Documentation and Project Setup

**Purpose:** Make the project easier to understand, run, and review.

**Example prompts:**
- What should be included in the README for this project?
- How should I document the database tables and their purpose?
- How can I provide clear instructions for setting up MySQL and running the dashboard?
- How can I record validation results and file checksums for reproducibility?

### 10. Final Checks Before Submission

**Purpose:** Review the project for common issues before pushing it to GitHub.

**Example prompts:**
- What should I check before submitting this project?
- How can I verify foreign-key relationships and row counts?
- How can I confirm that the business-rule validation queries are working?
- What should I check to make sure credentials and other sensitive configuration details are not committed to Git?
- How can I review the final changes before committing them?

### 11. Use of AI and Verification

AI was used as a supporting tool for understanding concepts, exploring possible solutions, debugging, and improving documentation. Suggestions were reviewed against the project's requirements and implementation before being used.

The final code, SQL queries, database structure, and validation results should be checked against the actual project files to ensure that the submitted implementation is accurate.