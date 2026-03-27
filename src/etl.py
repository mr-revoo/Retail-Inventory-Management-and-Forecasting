import os
import sys
import logging
import pandas as pd
import numpy as np
from sqlalchemy import create_engine, text

# ---- LOGGING ----
logging.basicConfig(
    level=logging.INFO,
    format="[%(levelname)s] %(asctime)s — %(message)s",
    datefmt="%H:%M:%S",
    stream=sys.stdout,
)
log = logging.getLogger("etl")

# ===========================================================================
# 1. EXTRACT
# ===========================================================================
def extract(path: str) -> pd.DataFrame:
    log.info("EXTRACT — Reading %s", path)
    df = pd.read_csv(path)
    log.info("EXTRACT — Read %d rows × %d columns", *df.shape)
    return df

# ===========================================================================
# 2. CLEAN / TRANSFORM
# ===========================================================================
def clean(df: pd.DataFrame) -> pd.DataFrame:
    log.info("CLEAN — Starting data cleaning (%d rows)", len(df))
    initial = len(df)

    df = df.drop_duplicates()
    df = df.dropna(subset=["Transaction_ID", "Customer_ID"])
    
    brand_fixes = {"Whirepool": "Whirlpool", "Mitsubhisi": "Mitsubishi"}
    if "Product_Brand" in df.columns:
        df["Product_Brand"] = df["Product_Brand"].replace(brand_fixes)

    # Convert Date explicitly
    df["Date_Key"] = pd.to_datetime(df["Date"], errors="coerce")
    valid_dates = df.dropna(subset=["Date_Key"])
    median_date = valid_dates["Date_Key"].median()
    df["Date_Key"] = df["Date_Key"].fillna(median_date)
    df["Date"] = df["Date_Key"]

    numeric_fill_cols = ["Age", "Amount", "Total_Amount", "Total_Purchases", "Zipcode", "Ratings"]
    for col in numeric_fill_cols:
        if col in df.columns and df[col].isnull().any():
            median_val = df[col].median()
            df[col] = df[col].fillna(median_val)
            
    cat_cols = df.select_dtypes(include=["object"]).columns.tolist()
    for col in cat_cols:
        if df[col].isnull().any() and col != 'Date':
            mode_val = df[col].mode().iloc[0] if not df[col].mode().empty else "Unknown"
            df[col] = df[col].fillna(mode_val)

    # Outlier capping / handling
    if "Age" in df.columns:
        df["Age"] = df["Age"].clip(18, 100) # Ensure age is within reasonable limits
    if "Total_Amount" in df.columns:
        df["Total_Amount"] = df["Total_Amount"].clip(lower=0)
    if "Amount" in df.columns:
        df["Amount"] = df["Amount"].clip(lower=0)
    
    # Types
    df["Transaction_ID"] = df["Transaction_ID"].astype(int)
    df["Customer_ID"] = df["Customer_ID"].astype(int)
    df["Zipcode"] = df["Zipcode"].astype(float).astype(int).astype(str)
    df["Ratings"] = df["Ratings"].astype(int)

    log.info("CLEAN — Cleaning complete. Final shape: %d × %d", *df.shape)
    return df

# ===========================================================================
# 3. BUILD STAR SCHEMA AND CALCULATED FIELDS (LOOKER BLUEPRINT)
# ===========================================================================
def build_star_schema(df: pd.DataFrame):
    log.info("SCHEMA — Building Star Schema dimensions and fact table...")

    # Fact Base Processing
    df["is_delivered"] = (df["Order_Status"] == "Delivered").astype(int)
    df["is_cancelled"] = (df["Order_Status"] == "Cancelled").astype(int)
    df["is_same_day_shipping"] = (df["Shipping_Method"] == "Same-Day").astype(int)
    
    df["day_of_week"] = df["Date_Key"].dt.day_name()
    df["quarter"] = df["Date_Key"].dt.quarter
    
    # Unit Price Calculation
    # Assuming Total_Purchases means Quantity here based on the schema mapping requests
    df["quantity"] = df["Total_Purchases"]
    df["unit_price"] = np.where(df["quantity"] > 0, df["Total_Amount"] / df["quantity"], df["Total_Amount"])
    
    # NPS Category
    def get_nps(rating):
        if rating >= 4: return "Promoter"
        elif rating <= 2: return "Detractor"
        return "Passive"
    df["nps_category"] = df["Ratings"].apply(get_nps)
    
    # Order Size Bucket
    def get_order_bucket(qty):
        if qty == 1: return "Single Item"
        elif qty <= 3: return "Small Cart"
        elif qty <= 10: return "Medium Cart"
        return "Large Cart"
    df["order_size_bucket"] = df["quantity"].apply(get_order_bucket)

    # Feedback sentiment mapping explicitly
    df["feedback_sentiment"] = df["Feedback"]

    # ---------- Dim_Geography ----------
    geo_cols = ["City", "State", "Country", "Zipcode"]
    dim_geography = df[geo_cols].drop_duplicates().reset_index(drop=True)
    dim_geography.insert(0, "location_id", range(1, len(dim_geography) + 1))
    df = df.merge(dim_geography, on=geo_cols, how="left")

    # ---------- Dim_Logistics ----------
    log_cols = ["Shipping_Method", "Payment_Method", "Order_Status", "feedback_sentiment"]
    dim_logistics = df[log_cols].drop_duplicates().reset_index(drop=True)
    dim_logistics.insert(0, "logistics_id", range(1, len(dim_logistics) + 1))
    dim_logistics.columns = [
        "logistics_id", "shipping_method", "payment_method",
        "order_status", "feedback_sentiment"
    ]
    log_map = dim_logistics.copy()
    log_map.columns = ["logistics_id", "Shipping_Method", "Payment_Method", "Order_Status", "feedback_sentiment"]
    df = df.merge(log_map, on=log_cols, how="left")

    # ---------- Dim_Products ----------
    prod_cols = ["Product_Category", "Product_Brand", "Product_Type"]
    dim_products_base = df[prod_cols].drop_duplicates().reset_index(drop=True)
    dim_products_base.insert(0, "product_id", range(1, len(dim_products_base) + 1))
    
    # Map product ID to df so we can group on it
    prod_map_temp = dim_products_base.copy()
    df = df.merge(prod_map_temp, on=prod_cols, how="left")

    # Aggregate Product Metrics
    prod_agg = df.groupby("product_id").agg(
        avg_unit_price=("unit_price", "mean"),
        total_units_sold=("quantity", "sum"),
        product_avg_rating=("Ratings", "mean"),
        total_revenue=("Total_Amount", "sum")
    ).reset_index()
    
    dim_products = dim_products_base.merge(prod_agg, on="product_id", how="left")
    
    def get_rating_tier(r):
        if r >= 4.5: return "Excellent"
        if r >= 4.0: return "Good"
        if r >= 3.0: return "Average"
        return "Poor"
    dim_products["rating_tier"] = dim_products["product_avg_rating"].apply(get_rating_tier)
    
    dim_products["revenue_rank_in_category"] = dim_products.groupby("Product_Category")["total_revenue"].rank("dense", ascending=False)
    
    dim_products.columns = [
        "product_id", "product_category", "product_brand", "product_type", 
        "avg_unit_price", "total_units_sold", "avg_rating", "total_revenue", "rating_tier", "revenue_rank_in_category"
    ]
    # 'price_tier' logic based on avg price within category
    dim_products["price_tier"] = pd.qcut(dim_products["avg_unit_price"].rank(method='first'), q=4, labels=["Budget", "Mid-Range", "Premium", "Luxury"])

    # ---------- Dim_Customers ----------
    cust_cols = ["Customer_ID", "Name", "Email", "Age", "Gender", "Income", "Customer_Segment"]
    dim_customers_base = df[cust_cols].drop_duplicates(subset=["Customer_ID"]).reset_index(drop=True)

    # Customer Aggregates
    cust_agg = df.groupby("Customer_ID").agg(
        lifetime_revenue=("Total_Amount", "sum"),
        lifetime_transactions=("Transaction_ID", "count"),
        first_purchase_date=("Date_Key", "min"),
        last_purchase_date=("Date_Key", "max")
    ).reset_index()
    
    dim_customers = dim_customers_base.merge(cust_agg, on="Customer_ID", how="left")
    dim_customers["avg_order_value"] = np.where(dim_customers["lifetime_transactions"]>0, dim_customers["lifetime_revenue"] / dim_customers["lifetime_transactions"], 0)
    
    def get_value_segment(ltv):
        if ltv >= 5000: return "Platinum"
        if ltv >= 2000: return "Gold"
        if ltv >= 500: return "Silver"
        return "Bronze"
    dim_customers["value_segment"] = dim_customers["lifetime_revenue"].apply(get_value_segment)
    
    dim_customers["age_group"] = pd.cut(dim_customers["Age"], bins=[-1, 24, 34, 49, 64, 100], labels=["<25", "25-34", "35-49", "50-64", "65+"])
    
    dim_customers.columns = [
        "customer_id", "customer_name", "email", "age", "customer_gender", "customer_income_level", "customer_segment",
        "lifetime_revenue", "lifetime_transactions", "first_purchase_date", "last_purchase_date",
        "avg_order_value", "value_segment", "age_group"
    ]

    # ---------- Fact_Transactions ----------
    fact_transactions = df[[
        "Transaction_ID", "Date_Key", "Customer_ID", "product_id", "location_id", "logistics_id", 
        "quantity", "unit_price", "Total_Amount", "Ratings", "nps_category", 
        "order_size_bucket", "is_delivered", "is_cancelled", "is_same_day_shipping", "day_of_week", "quarter"
    ]].copy()
    
    fact_transactions.columns = [
        "transaction_id", "transaction_date", "customer_id", "product_id", "location_id", "logistics_id",
        "quantity", "unit_price", "total_amount", "rating", "nps_category",
        "order_size_bucket", "is_delivered", "is_cancelled", "is_same_day_shipping", "day_of_week", "quarter"
    ]

    return dim_customers, dim_products, dim_geography, dim_logistics, fact_transactions

# ===========================================================================
# 4. LOAD (Idempotent — truncate + reload)
# ===========================================================================
def load(engine, dim_customers, dim_products, dim_geography, dim_logistics, fact_transactions):
    log.info("LOAD — Starting idempotent load into PostgreSQL...")

    tables = [
        ("dim_customers", dim_customers),
        ("dim_products", dim_products),
        ("dim_geography", dim_geography),
        ("dim_logistics", dim_logistics),
        ("fact_transactions", fact_transactions),
    ]

    with engine.begin() as conn:
        for tbl_name, _ in reversed(tables):
            conn.execute(text(f'DROP TABLE IF EXISTS "{tbl_name}" CASCADE'))
            log.info("LOAD — Dropped table %s (if existed)", tbl_name)

    for tbl_name, tbl_df in tables:
        log.info("LOAD — Writing %s (%d rows)...", tbl_name, len(tbl_df))
        tbl_df.to_sql(tbl_name, engine, if_exists="replace", index=False, method="multi", chunksize=10000)
        log.info("LOAD — ✓ %s loaded", tbl_name)

    log.info("LOAD — All tables loaded successfully!")

def main():
    db_url = os.getenv("DATABASE_URL", "postgresql://admin:password@localhost:5433/retail_db")
    engine = create_engine(db_url)

    file_path = "data/retail_data.csv"
    if not os.path.exists(file_path):
        file_path = "../data/retail_data.csv"
    if not os.path.exists(file_path):
        log.error("CSV file not found")
        sys.exit(1)

    df = extract(file_path)
    df = clean(df)
    dim_cust, dim_prod, dim_geo, dim_log, fact = build_star_schema(df)
    load(engine, dim_cust, dim_prod, dim_geo, dim_log, fact)

    log.info("=" * 50)
    log.info("ETL PIPELINE COMPLETED SUCCESSFULLY")
    log.info("=" * 50)

if __name__ == "__main__":
    main()
