#### Write you dashboard here

from typing import List, Tuple
import pandas as pd
import streamlit as st
import sqlite3
import plotly.express as px

DB_PATH = "legal_documents_ecommerce.db"

def set_page_config() -> None:
    st.set_page_config(
        page_title="Legal Desk Analytics Dashboard",
        page_icon="📑",
        layout="wide",
        initial_sidebar_state="expanded",
    )
    st.markdown("""
        <style>
            footer {visibility: hidden;}
        </style>
    """, unsafe_allow_html=True)

@st.cache_data(show_spinner="Loading data…")
def load_data() -> pd.DataFrame:
    conn = sqlite3.connect(DB_PATH)
    query = """
        SELECT
            C.customer_id,
            C.first_name,
            C.last_name,
            C.registration_date,
            O.order_id,
            O.order_date,
            O.total_amount,
            P.product_name,
            P.category,
            P.price,
            OI.quantity,
            OI.unit_price,
            OI.quantity * OI.unit_price     AS item_revenue
        FROM   Customers     AS C
        JOIN   Orders        AS O  ON O.customer_id  = C.customer_id
        JOIN   Order_items   AS OI ON OI.order_id    = O.order_id
        JOIN   Products      AS P  ON P.product_id   = OI.product_id;
    """

    df = pd.read_sql_query(query, conn)
    conn.close()

    # datetime conversions
    df["order_date"] = pd.to_datetime(df["order_date"])
    df["registration_date"] = pd.to_datetime(df["registration_date"])

    # time buckets
    df["week_start"] = df["order_date"] - pd.to_timedelta(df["order_date"].dt.dayofweek, unit="d")
    df["month_start"] = df["order_date"].dt.to_period("M").dt.to_timestamp()

    return df

def calculate_kpis(df: pd.DataFrame) -> List[str]:
    total_customers      = f"{df['customer_id'].nunique():,}"
    total_orders         = f"{df['order_id'].nunique():,}"
    total_revenue        = f"${df['item_revenue'].sum():,.0f}"
    avg_order_value      = f"${df.groupby('order_id')['item_revenue'].sum().mean():.0f}"
    orders_per_customer  = f"{df['order_id'].nunique() / df['customer_id'].nunique():.2f}"
    avg_items_per_order  = f"{df.groupby('order_id').size().mean():.2f}"

    return [
        total_customers,
        total_orders,
        total_revenue,
        avg_order_value,
        orders_per_customer,
        avg_items_per_order,
    ]

def display_kpi_metrics(kpi_values: List[str], kpi_names: List[str]) -> None:
    def metric_row(vals: List[str], names: List[str], n_cols: int) -> None:
        cols = st.columns(n_cols)
        for col, name, val in zip(cols, names, vals):
            with col:
                st.metric(label=name, value=val)
    
    metric_row(kpi_values[:4], kpi_names[:4], n_cols=4)
    metric_row(kpi_values[4:],  kpi_names[4:], n_cols=2)


def overview_page(df: pd.DataFrame) -> None:
    st.header("Business/data Overview")

    # KPI 
    kpi_names = [
        "Total Customers",
        "Total Orders",
        "Total Revenue",
        "Avg Order Value",
        "Orders per Customer",
        "Avg Items per Order",
    ]
    kpi_vals = calculate_kpis(df)
    display_kpi_metrics(kpi_vals, kpi_names)

    # Dataset info 
    st.subheader("Dataset Information")
    st.write(f"**Date Range:** {df['order_date'].min().date()} ➜ {df['order_date'].max().date()}")
    st.write(f"**Total Records:** {len(df):,}")

    with st.expander("▶ Sample data (first 5 rows)"):
        st.dataframe(df.head())

def analysis_page(df: pd.DataFrame) -> None:
    st.header("Required Task Analysis")
    st.subheader("1. Orders Development Over Time")
    
    # Weekly analysis
    weekly = (df.groupby("week_start")["order_id"].nunique().reset_index(name="orders"))
    
    fig_week = px.line(weekly, x="week_start", y="orders", markers=True, 
                       title="Weekly Order Volume")
    fig_week.update_traces(fill='tozeroy')
    fig_week.update_layout(xaxis_title="Week (Mon–Sun)", yaxis_title="Number of Orders")
    st.plotly_chart(fig_week, use_container_width=True)

    st.info(
        f"**Observation:** Weekly orders are quite unpredictable ranging from "
        f"{weekly['orders'].min()} to {weekly['orders'].max()} orders per week "
        f"with peaks in september and november 2024. This pattern could indicate "
        "the benefit of marketing campaigns during these lower periodes (Youtube "
        "campaigns etc.). "
        f"avg {weekly['orders'].mean():.1f} per week."
    )

    # Monthly analysis - changed to line chart
    monthly = (df.groupby("month_start")["order_id"].nunique().reset_index(name="orders"))
    fig_month = px.line(monthly, x="month_start", y="orders", markers=True, 
                        title="Monthly Order Volume")
    fig_month.update_traces(fill='tozeroy')
    fig_month.update_layout(xaxis_title="Month", yaxis_title="Number of Orders")
    
    st.plotly_chart(fig_month, use_container_width=True)

    st.info(
        "**Observation:** April 2024 tops the period at 28 orders, more than double "
        "compared to October 2025 trough at 11 orders, from here we have marginal "
        "decline. We have rebound in March 2025's at 24 orders so replicating whatever "
        "drove April's lift could potentially prevent future dips."
    )

    # Most frequently ordered products 
    st.subheader("2. Most Frequently Ordered Products")
    top_n = st.slider("Show top N products", 5, 30, 10)

    prod_freq = (df.groupby("product_name")["order_id"].nunique().reset_index(name="orders").sort_values("orders", ascending=False))
    fig = px.bar(prod_freq.head(top_n), x="product_name", y="orders", text="orders", title=f"Top {top_n} Products by Order Count")
    
    max_orders = prod_freq["orders"].max()
    fig.update_traces(textposition="outside", cliponaxis=False)      
    fig.update_yaxes(range=[0, max_orders + 5])                
    fig.update_layout(xaxis_tickangle=45, margin=dict(t=90))        
    st.plotly_chart(fig, use_container_width=True)

    if not prod_freq.empty:
        top_two = prod_freq.head(2)["product_name"].tolist()   # ['Deed of Trust', 'NDA Agreement']
        combined_share = (
            df.loc[df["product_name"].isin(top_two), "order_id"].nunique()
            / df["order_id"].nunique()
        )
        st.info(
            rf"**Observation:** Top products '{top_two[0]}' and '{top_two[1]}' each record "
            f"{prod_freq.iloc[0]['orders']} orders and together they appear in "
            rf"$\approx {combined_share*100:.0f}\%$ of all orders."
        )

def insights_page(df: pd.DataFrame) -> None:
    st.header("Additional BI")

    # Customer Value Analysis
    st.subheader("Customer Value Analysis")
    cust_val = (df.groupby(["customer_id", "first_name", "last_name"]).agg(
            item_revenue=("item_revenue", "sum"),
            orders       =("order_id",    "nunique"),
            quantity     =("quantity",    "sum"),).reset_index().sort_values("item_revenue", ascending=False))
    cust_val["customer_name"] = cust_val["first_name"] + " " + cust_val["last_name"]

    fig = px.bar(cust_val.head(10), x="customer_name", y="item_revenue",title="Top 10 Customers by Total Revenue",
                 labels={"item_revenue": "Total Revenue ($)", "customer_name": "Customer"})
    fig.update_layout(xaxis_tickangle=45)
    st.plotly_chart(fig, use_container_width=True)

    # values are from the notebook
    st.info(
        rf"**Observation**: The top 10 customers contribute $\approx 53{','}800$ "
        "(about 19.6% of total revenue) while representing only 6.71% of the "
        "customer base. Individual spend ranges from \$4,678 to \$6,695. "
    )

    category_colors = {
    'Real Estate': '#87CEEB',      # Light blue (from pie chart)
    'Business': '#4682B4',         # Medium blue
    'Personal': '#FFB6C1',         # Light pink/salmon
    'Intellectual Property': '#FF6B6B'  # Red
    }

    # Category 
    st.subheader("Product Category Analysis")
    category_perf = (df.groupby("category").agg(
            item_revenue=("item_revenue", "sum"),
            quantity     =("quantity",    "sum"),
            orders       =("order_id",    "nunique"),
        ).reset_index().sort_values("item_revenue", ascending=False))

    col1, col2 = st.columns([2, 1])
    with col1:
        pie = px.pie(category_perf, names="category", values="item_revenue",
                     title="Revenue Distribution by Category",
                     color="category", color_discrete_map=category_colors)
        st.plotly_chart(pie, use_container_width=True)

    with col2:
        st.markdown("### Category KPIs")
        for _, row in category_perf.iterrows():
            st.metric(row["category"], f"${row['item_revenue']:,.0f}", f"{row['orders']} orders")

    st.info(
        rf"**Observation**: Revenue is more or less evenly balanced across categories: Real Estate 30.6%, Business 30%, Personal 23.2%, IP 16.2%"
    )

    # Top products by revenue
    st.subheader("Top Products by Revenue")
    top_products = (df.groupby(["product_name", "category"]).agg(
            item_revenue=("item_revenue", "sum"),
            quantity     =("quantity",    "sum"),
        ).reset_index().sort_values("item_revenue", ascending=False).head(10))

    fig = px.bar(top_products, x="product_name", y="item_revenue", color="category",
                 title="Top 10 Products by Revenue", color_discrete_map=category_colors)
    fig.update_layout(xaxis_tickangle=45)
    st.plotly_chart(fig, use_container_width=True)

    st.info(
        rf"**Observation**: While 'NDA Agreement' tops frequency, it generates the highest revenue at $28K, showing it as the most valuable product overall. The color coding shows real estate and business categories dominate both volume and value."
    )    

def main() -> None:
    set_page_config()
    df = load_data()
    st.title("📑 Legal Desk Analytics Dashboard")
    st.sidebar.header("Navigation")
    page = st.sidebar.radio("Go to", ["Overview", "Required Analysis", "Additional Analysis"])
    if page == "Overview":
        overview_page(df)
    elif page == "Required Analysis":
        analysis_page(df)
    elif page == "Additional Analysis":
        insights_page(df)

if __name__ == "__main__":
    main()
