import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from sqlalchemy import create_engine
import os

st.set_page_config(page_title="Retail Analytics Dashboard", layout="wide", page_icon="📈")
st.title("📈 Retail Analytics Command Center")
st.markdown("---")

@st.cache_resource
def get_engine():
    db_url = os.getenv("DATABASE_URL", "postgresql://admin:password@db:5432/retail_db")
    return create_engine(db_url)

engine = get_engine()

# ==========================================
# PAGE 1: EXECUTIVE SUMMARY
# ==========================================
def render_executive_summary():
    st.header("Executive Summary")
    
    query = """
    SELECT 
        SUM(f.total_amount) as total_revenue,
        COUNT(f.transaction_id) as total_tx,
        SUM(f.total_amount) / COUNT(f.transaction_id) as aov,
        COUNT(DISTINCT f.customer_id) as unique_cust,
        AVG(f.rating) as avg_rating
    FROM fact_transactions f
    """
    try:
        kpis = pd.read_sql(query, engine).iloc[0]
        c1, c2, c3, c4, c5 = st.columns(5)
        c1.metric("Total Revenue", f"${kpis['total_revenue']:,.2f}")
        c2.metric("Total Transactions", f"{kpis['total_tx']:,}")
        c3.metric("Average Order Value", f"${kpis['aov']:,.2f}")
        c4.metric("Unique Customers", f"{kpis['unique_cust']:,}")
        c5.metric("Avg Customer Rating", f"{kpis['avg_rating']:.2f} / 5.0")
    except Exception as e:
        st.error(f"Waiting for database to initialize... Error: {e}")
        return

    st.markdown("---")
    
    colA, colB = st.columns(2)
    
    # Revenue Trend line chart
    trend_q = """
    SELECT DATE_TRUNC('month', transaction_date) as month, SUM(total_amount) as revenue
    FROM fact_transactions GROUP BY 1 ORDER BY 1
    """
    df_trend = pd.read_sql(trend_q, engine)
    with colA:
        if not df_trend.empty:
            fig = px.line(df_trend, x='month', y='revenue', title="Revenue Trend over Time (Monthly)")
            fig.update_traces(line_color="#1A73E8", line_width=3)
            st.plotly_chart(fig, use_container_width=True)

    # Revenue by Category
    cat_q = """
    SELECT p.product_category as category, SUM(f.total_amount) as revenue
    FROM fact_transactions f JOIN dim_products p ON f.product_id = p.product_id
    GROUP BY p.product_category ORDER BY revenue DESC
    """
    df_cat = pd.read_sql(cat_q, engine)
    with colB:
        if not df_cat.empty:
            fig = px.bar(df_cat, x='revenue', y='category', orientation='h', title="Revenue by Product Category")
            fig.update_traces(marker_color="#1A73E8")
            st.plotly_chart(fig, use_container_width=True)

    colC, colD = st.columns(2)
    
    # Order Status Donut
    status_q = """
    SELECT l.order_status as status, COUNT(f.transaction_id) as orders
    FROM fact_transactions f JOIN dim_logistics l ON f.logistics_id = l.logistics_id
    GROUP BY l.order_status
    """
    df_status = pd.read_sql(status_q, engine)
    with colC:
        if not df_status.empty:
            color_map = {'Delivered':'#34A853', 'Shipped':'#1A73E8', 'Processing':'#FBBC04', 'Cancelled':'#EA4335'}
            fig = px.pie(df_status, values='orders', names='status', title="Order Status Distribution", hole=0.4,
                         color='status', color_discrete_map=color_map)
            st.plotly_chart(fig, use_container_width=True)

    # Top 10 Products
    top_q = """
    SELECT p.product_brand || ' - ' || p.product_type as product_name,
           SUM(f.total_amount) as revenue, SUM(f.quantity) as units_sold, AVG(f.rating) as avg_rating
    FROM fact_transactions f JOIN dim_products p ON f.product_id = p.product_id
    GROUP BY p.product_brand, p.product_type ORDER BY revenue DESC LIMIT 10
    """
    df_top = pd.read_sql(top_q, engine)
    with colD:
        st.subheader("Top 10 Products by Revenue")
        st.dataframe(df_top, use_container_width=True)


# ==========================================
# PAGE 2: CUSTOMER INTELLIGENCE
# ==========================================
def render_customer_intelligence():
    st.header("Customer Intelligence")
    
    kpi_q = """
    SELECT 
        AVG(lifetime_revenue) as avg_ltv,
        COUNT(*) FILTER (WHERE value_segment='Platinum' OR value_segment='VIP') as vip_cust,
        COUNT(*) FILTER (WHERE customer_segment='Premium') * 100.0 / COUNT(*) as premium_pct,
        COUNT(*) FILTER (WHERE lifetime_transactions > 1) * 100.0 / COUNT(*) as repeat_rate
    FROM dim_customers
    """
    df_kpi = pd.read_sql(kpi_q, engine)
    if df_kpi.empty or df_kpi.iloc[0].isnull().all():
        st.warning("Customer dimensions not populated yet.")
        return
        
    k = df_kpi.iloc[0]
    
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Avg Customer LTV", f"${k['avg_ltv']:,.2f}")
    c2.metric("VIP/Platinum Customers", f"{k['vip_cust']:,}")
    c3.metric("Premium Segment %", f"{k['premium_pct']:.1f}%")
    c4.metric("Repeat Purchase Rate", f"{k['repeat_rate']:.1f}%")
    st.markdown("---")

    colA, colB = st.columns(2)
    
    # Customer Value Segmentation
    seg_q = """
    SELECT value_segment, customer_segment, COUNT(customer_id) as cust_count
    FROM dim_customers GROUP BY 1, 2
    """
    df_seg = pd.read_sql(seg_q, engine)
    with colA:
        if not df_seg.empty:
            fig = px.bar(df_seg, x="value_segment", y="cust_count", color="customer_segment",
                         title="Customer Value Segmentation", barmode="stack", color_discrete_sequence=px.colors.qualitative.Pastel)
            st.plotly_chart(fig, use_container_width=True)
            
    # Revenue by Age Group
    age_q = """
    SELECT c.age_group, SUM(c.lifetime_revenue) as revenue, AVG(c.lifetime_revenue) as avg_ltv
    FROM dim_customers c GROUP BY 1 ORDER BY 1
    """
    df_age = pd.read_sql(age_q, engine)
    with colB:
        if not df_age.empty:
            fig = px.bar(df_age, x='age_group', y='revenue', title="Revenue by Demographics (Age Group)")
            fig.update_traces(marker_color='#1A73E8')
            st.plotly_chart(fig, use_container_width=True)

    colC, colD = st.columns(2)
    # Income vs Spend (Scatter Bubble)
    scatter_q = """
    SELECT customer_income_level, lifetime_revenue, lifetime_transactions, customer_segment
    FROM dim_customers WHERE lifetime_revenue > 0 LIMIT 1000
    """
    df_scatter = pd.read_sql(scatter_q, engine)
    with colC:
        if not df_scatter.empty:
            fig = px.scatter(df_scatter, x="customer_income_level", y="lifetime_revenue", size="lifetime_transactions", 
                             color="customer_segment", title="Customer Income vs Spend (Sampled)",
                             color_discrete_sequence=px.colors.qualitative.Vivid)
            st.plotly_chart(fig, use_container_width=True)

    # Gender Split
    gender_q = """
    SELECT c.customer_gender, SUM(f.total_amount) as revenue
    FROM fact_transactions f JOIN dim_customers c ON f.customer_id = c.customer_id GROUP BY 1
    """
    df_gender = pd.read_sql(gender_q, engine)
    with colD:
        if not df_gender.empty:
            fig = px.pie(df_gender, values='revenue', names='customer_gender', title="Gender Revenue Split", hole=0.3)
            st.plotly_chart(fig, use_container_width=True)


# ==========================================
# PAGE 3: OPERATIONS & PRODUCTS
# ==========================================
def render_operations():
    st.header("Product Performance & Logistics Operations")

    kpi_q = """
    SELECT 
        SUM(is_delivered) * 100.0 / NULLIF(COUNT(*),0) as delivery_rate,
        SUM(is_cancelled) * 100.0 / NULLIF(COUNT(*),0) as cancel_rate,
        SUM(is_same_day_shipping) * 100.0 / NULLIF(COUNT(*),0) as same_day_rate
    FROM fact_transactions
    """
    df_kpi = pd.read_sql(kpi_q, engine)
    
    prod_kpi = pd.read_sql("SELECT AVG(avg_rating) as p_rating FROM dim_products", engine)
    
    c1, c2, c3, c4 = st.columns(4)
    if not df_kpi.empty:
        c1.metric("Delivery Rate", f"{df_kpi['delivery_rate'].iloc[0]:.1f}%")
        c2.metric("Cancellation Rate", f"{df_kpi['cancel_rate'].iloc[0]:.1f}%")
        c3.metric("Same-Day Shipping %", f"{df_kpi['same_day_rate'].iloc[0]:.1f}%")
        c4.metric("Avg Product Rating", f"{prod_kpi['p_rating'].iloc[0]:.2f}")
    
    st.markdown("---")

    colA, colB = st.columns(2)
    # Profile Matrix (Bubble)
    matrix_q = """
    SELECT product_category, total_revenue, avg_rating, total_units_sold
    FROM dim_products
    """
    df_matrix = pd.read_sql(matrix_q, engine)
    with colA:
        if not df_matrix.empty:
            df_matrix_agg = df_matrix.groupby("product_category").agg({"total_revenue":"sum", "avg_rating":"mean", "total_units_sold":"sum"}).reset_index()
            fig = px.scatter(df_matrix_agg, x="total_revenue", y="avg_rating", size="total_units_sold", color="product_category",
                             title="Product Category Performance Matrix")
            st.plotly_chart(fig, use_container_width=True)

    # Shipping Method Analysis
    ship_q = """
    SELECT l.order_status, l.shipping_method, COUNT(f.transaction_id) as orders
    FROM fact_transactions f JOIN dim_logistics l ON f.logistics_id = l.logistics_id
    GROUP BY 1, 2
    """
    df_ship = pd.read_sql(ship_q, engine)
    with colB:
        if not df_ship.empty:
            fig = px.bar(df_ship, x="order_status", y="orders", color="shipping_method", barmode='stack', text_auto=True,
                         title="Shipping Method Analysis by Status", color_discrete_sequence=px.colors.qualitative.Prism)
            st.plotly_chart(fig, use_container_width=True)

    colC, colD = st.columns(2)
    # NPS Distribution Stacked Bar
    nps_q = """
    SELECT p.product_category, f.nps_category, COUNT(*) as volume
    FROM fact_transactions f JOIN dim_products p ON f.product_id = p.product_id
    GROUP BY 1, 2
    """
    df_nps = pd.read_sql(nps_q, engine)
    with colC:
        if not df_nps.empty:
            fig = px.bar(df_nps, y="product_category", x="volume", color="nps_category", orientation='h', barmode='stack',
                         title="NPS Distribution by Category", color_discrete_map={"Promoter":"#34A853", "Passive":"#FBBC04", "Detractor":"#EA4335"})
            st.plotly_chart(fig, use_container_width=True)

    # Feedback Sentiment Heatmap
    heatmap_q = """
    SELECT p.product_category, l.feedback_sentiment, COUNT(*) as volume
    FROM fact_transactions f 
    JOIN dim_products p ON f.product_id = p.product_id
    JOIN dim_logistics l ON f.logistics_id = l.logistics_id
    GROUP BY 1, 2
    """
    df_heatmap = pd.read_sql(heatmap_q, engine)
    with colD:
        if not df_heatmap.empty:
            pivot = df_heatmap.pivot_table(index="product_category", columns="feedback_sentiment", values="volume", fill_value=0)
            fig = px.imshow(pivot, text_auto=True, color_continuous_scale="RdBu", title="Feedback Sentiment Heatmap")
            st.plotly_chart(fig, use_container_width=True)


# ==========================================
# RENDER TABS
# ==========================================
tab1, tab2, tab3 = st.tabs(["📊 Executive Summary", "👥 Customer Intelligence", "📦 Operations & Products"])

with tab1:
    render_executive_summary()
with tab2:
    render_customer_intelligence()
with tab3:
    render_operations()

st.markdown("---")
st.caption("Powered by Looker Studio Blueprint Logic & Plotly")