# Retail Analytics Data Warehouse & BI Dashboard

![Revenue Trend](docs/revenue_trend.png)

## Business Case & Overview
The Retail Analytics end-to-end framework aims to process raw transactional data covering products, customers, operations, and orders, to unlock intelligent Insights for the C-Suite and regional managers. Instead of relying on manual reporting tools which cannot scale with our $300M+ revenue growth trajectory, this robust infrastructure achieves continuous data normalization, pipeline reproducibility, and powerful interactive dashboarding.

### Goal
To build a modern Start-Schema Data Warehouse on **PostgreSQL**, processing hundreds of thousands of retail transactions robustly through a containerized Python ETL pipeline and surfacing high-value Business Intelligence via a native **Streamlit/Plotly Dashboard** aligned with a Looker Studio blueprint. 

---

## 📊 Dashboard Metrics Deep-Dive

The analytical workspace is broken down into three distinct areas, meticulously tracking both P&L growth and Operational efficiencies:

![Revenue by Category](docs/revenue_category.png)

### 1. Executive Summary
- **KPI Scorecards:** Total Revenue, Total Transactions (Volume), Average Order Value (AOV), Unique Customer footprints, and overall Sentiment.
- **Reporting Visulas:** 
   - **Monthly Growth Curve:** Monitoring seasonal influx.
   - **Category Distribution (Bar Chart):** Identifying our most profitable product vertices.
   - **Order Dispatch Health (Donut):** Status mix of Delivered vs. Processing orders.

### 2. Customer Intelligence
Focuses exclusively on long-term behavioral profiles and predictive segmentations.
- **Customer Lifetime Value (LTV) & VIP Status:** Tiering customers into VIP/Platinum, Gold, Silver bands based on longitudinal spend.
- **Repeat Purchase Cohorts:** Analyzing loyalty mechanics and tracking demographic age group correlations mapping Income vs. Spend.

![Customer Segmentation](docs/customer_segments.png)

### 3. Operations & Logistics
- Evaluates the "cost to serve" and real-world supply chain metrics.
- Computes metrics on **Delivery Rate**, **Cancellations**, and **Same-Day volume**.
- Includes dense Heatmaps to pinpoint operational bottlenecks per specific Shipping methods vs. internal Order Status transitions.

---

## 🏗 System Architecture (ETL & Docker)

We follow a unified **Extract → Transform → Load** (ETL) strategy enforcing Idempotency:

- **Extract:** Raw CSV reading `retail_data.csv`.
- **Clean/Validate:** Robust null inference via modes/medians, type-casting, typo fixes (e.g., standardizing brands), and Date extraction (Day of Week, Quarters).
- **Transform (Star Schema Modeling):** 
   - **Fact Table (`fact_transactions`):** Transactional mapping, pricing boundaries, status boolean flags.
   - **Dimension Tables:** `dim_customers`, `dim_products`, `dim_geography`, `dim_logistics`. LTV and NPS metrics are computed securely.
- **Load:** Streamed idempotently into **PostgreSQL** (Drops gracefully if run multiple times).

---

## 🚀 Guide to Run the Project

This project leverages Docker Compose to achieve zero-config deployments. Everything will initialize automatically. Ensure Docker is installed on your OS.

### 1. Build and Run the Stack
From your terminal root simply run:
```bash
docker-compose up --build -d
```
*What happens under the hood?*
1. Docker provisions a bare-metal PostgreSQL 15 database. 
2. The `app` container constructs the Python 3.11 environment.
3. Our bash `entrypoint.sh` blocks startup until postgres is receptive.
4. Python runs the robust `src/etl.py` Data Pipeline.
5. Streamlit binds to port 8501 and begins executing `src/app.py`.

### 2. Monitor Initial Setup
The ETL pipeline processes ~300,000 rows. You can track this process robustly via unified logs:
```bash
docker-compose logs -f
```

### 3. Access the BI Dashboard
Once the Streamlit service acknowledges a successful boot, open your favorite web browser and navigate to:
**http://localhost:8501/ **

### 4. Cleanup
To stop the application cleanly and free your terminal:
```bash
docker-compose down
```
*(Volumes persist automatically via the configured `postgres_data` volume)*
