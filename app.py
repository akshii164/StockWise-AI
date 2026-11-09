import streamlit as st
import pandas as pd
import plotly.express as px
from io import StringIO

st.set_page_config(page_title="StockWise AI", page_icon="📦", layout="wide")
st.title("📦 StockWise AI")
st.caption("Smart Inventory, Demand Forecasting & Profit Decision Assistant")

sample = """Product,Category,Stock,Cost,Price,Monthly_Sales,Lead_Days
Cotton T-Shirt,Clothing,25,8,20,80,7
Denim Jeans,Clothing,12,22,55,60,10
Summer Dress,Clothing,40,18,45,50,8
Sneakers,Footwear,8,30,75,45,14
Handbag,Accessories,30,15,40,35,9
Hoodie,Clothing,15,20,50,70,12
Sandals,Footwear,60,12,30,40,7
Sunglasses,Accessories,10,6,25,55,15
Jacket,Clothing,18,35,90,30,14
Cap,Accessories,50,5,18,45,6"""

st.sidebar.header("⚙️ Business Controls")
demand = st.sidebar.slider("Expected demand change (%)", -50, 100, 0, 5)
budget = st.sidebar.number_input("Reorder budget ($)", 0, 100000, 2000, 100)
safety = st.sidebar.slider("Safety stock (days)", 0, 30, 7)
uploaded = st.sidebar.file_uploader("Upload inventory CSV", type=["csv"])
st.sidebar.download_button("Download sample CSV", sample, "sample_inventory.csv", "text/csv")

try:
    df = pd.read_csv(uploaded if uploaded else StringIO(sample))
    required = ["Product","Category","Stock","Cost","Price","Monthly_Sales","Lead_Days"]
    if not set(required).issubset(df.columns):
        st.error("Missing columns: " + ", ".join(set(required)-set(df.columns)))
        st.stop()
    for col in ["Stock","Cost","Price","Monthly_Sales","Lead_Days"]:
        df[col] = pd.to_numeric(df[col], errors="coerce")
    if df[required].isna().any().any() or (df[["Stock","Cost","Price","Monthly_Sales","Lead_Days"]] < 0).any().any():
        st.error("Invalid data: missing values, nonnumeric values, or negative numbers.")
        st.stop()
    if df["Product"].duplicated().any():
        st.error("Product names must be unique.")
        st.stop()
except Exception as e:
    st.error(f"Could not read the CSV: {e}")
    st.stop()

df["Forecast_Monthly"] = df["Monthly_Sales"] * (1+demand/100)
df["Daily_Demand"] = df["Forecast_Monthly"]/30
df["Reorder_Point"] = (df["Lead_Days"]+safety)*df["Daily_Demand"]
df["Target_Stock"] = (df["Lead_Days"]+safety+30)*df["Daily_Demand"]
df["Recommended_Units"] = (df["Target_Stock"]-df["Stock"]).clip(lower=0).apply(lambda x: int(x+0.999999))
df["Stockout_Risk"] = df["Stock"] < df["Reorder_Point"]
df["Gross_Margin_%"] = ((df["Price"]-df["Cost"])/df["Price"].replace(0,float("nan"))*100).fillna(0)
df["Potential_Revenue"] = df["Forecast_Monthly"]*df["Price"]
df["Potential_Gross_Profit"] = df["Forecast_Monthly"]*(df["Price"]-df["Cost"])
df["Reorder_Cost"] = df["Recommended_Units"]*df["Cost"]

st.subheader("📊 Executive Overview")
a,b,c,d = st.columns(4)
a.metric("Forecast Monthly Revenue",f"${df.Potential_Revenue.sum():,.0f}")
b.metric("Forecast Gross Profit",f"${df.Potential_Gross_Profit.sum():,.0f}")
c.metric("At-Risk Products",int(df.Stockout_Risk.sum()))
d.metric("Inventory Value",f"${(df.Stock*df.Cost).sum():,.0f}")

tab1,tab2,tab3,tab4 = st.tabs(["📊 Analytics","🚨 Stock Alerts","🛒 Reorder Planner","🤖 Decision Assistant"])

with tab1:
    st.plotly_chart(px.bar(df,x="Product",y="Potential_Gross_Profit",color="Category",title="Forecast Gross Profit by Product"),use_container_width=True)
    st.plotly_chart(px.scatter(df,x="Forecast_Monthly",y="Gross_Margin_%",size="Stock",color="Category",hover_name="Product",title="Demand vs Gross Margin"),use_container_width=True)
    st.dataframe(df[["Product","Category","Stock","Forecast_Monthly","Gross_Margin_%"]],use_container_width=True)

with tab2:
    risk = df[df.Stockout_Risk]
    if risk.empty:
        st.success("No products currently below their reorder points.")
    else:
        st.warning(f"{len(risk)} products are at risk of stockout.")
        st.dataframe(risk[["Product","Stock","Reorder_Point","Lead_Days","Recommended_Units"]],use_container_width=True)
    st.caption("Risk occurs when stock is below expected demand during supplier lead time plus safety days.")

with tab3:
    st.write("Budget-aware reorder plan. Products are prioritized by stockout risk and forecast gross profit.")
    plan = df.sort_values(["Stockout_Risk","Potential_Gross_Profit"],ascending=[False,False]).copy()
    remaining = float(budget)
    approved = []
    for _,r in plan.iterrows():
        units = int(r["Recommended_Units"])
        if r["Cost"] > 0:
            units = min(units,int(remaining//r["Cost"]))
        approved.append(units)
        remaining -= units*r["Cost"]
    plan["Approved_Units"] = approved
    plan["Approved_Cost"] = plan["Approved_Units"]*plan["Cost"]
    st.metric("Planned Purchasing Cost",f"${plan.Approved_Cost.sum():,.2f}")
    st.metric("Budget Remaining",f"${remaining:,.2f}")
    st.dataframe(plan[["Product","Stockout_Risk","Recommended_Units","Approved_Units","Approved_Cost"]],use_container_width=True)
    st.download_button("⬇️ Download Reorder Plan",plan.to_csv(index=False),"stockwise_reorder_plan.csv","text/csv")

with tab4:
    st.subheader("Business Decision Assistant")
    question = st.selectbox("What would you like to know?",[
        "Which products should I reorder first?",
        "Which products have the highest profit potential?",
        "How does changing demand affect inventory?"
    ])
    if question.startswith("Which products should I reorder"):
        result = df[df.Stockout_Risk].sort_values("Potential_Gross_Profit",ascending=False)
        st.write("Prioritize these at-risk products:",", ".join(result.Product.head(5)) if len(result) else "No urgent reorders.")
    elif question.startswith("Which products have the highest"):
        result = df.sort_values("Potential_Gross_Profit",ascending=False)
        st.write("Highest forecast gross-profit products:",", ".join(result.Product.head(5)))
    else:
        st.write(f"Current demand scenario: {demand:+}% compared with historical monthly sales.")
        st.write(f"Estimated monthly demand: {df.Forecast_Monthly.sum():,.0f} units.")
        st.write(f"Products below reorder points: {df.Stockout_Risk.sum()}.")
    st.info("Recommendations use explainable business rules and scenario calculations, not a live generative AI model.")

st.caption("Educational prototype | Forecast assumes the most recent monthly sales rate continues, adjusted by the scenario slider.")
