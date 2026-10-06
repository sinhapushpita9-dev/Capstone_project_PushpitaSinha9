import pandas as pd
import matplotlib.pyplot as plt
import os

orders = pd.read_csv("/content/orders.csv")
customers = pd.read_csv("/content/customers.csv")
products = pd.read_csv("/content/products.csv")

print("Loaded orders.shape:", orders.shape)

orders['payment_method'] = orders['payment_method'].str.strip().str.upper()
natural_key = [
    'customer_id', 'product_id', 'order_date', 'quantity',
    'discount_pct', 'payment_method', 'rating', 'returned'
]
is_dup = orders.duplicated(subset=natural_key, keep='first')
orders_clean = orders.loc[~is_dup].copy()
print("orders_clean.shape after de-dup:", orders_clean.shape)
orders_clean['discount_pct'] = orders_clean['discount_pct'].fillna(0)
median_rating = orders_clean['rating'].median()
orders_clean['rating'] = orders_clean['rating'].fillna(median_rating)
merged = orders_clean.merge(products, on='product_id').merge(customers, on='customer_id')
merged['order_value'] = merged['quantity'] * merged['price'] * (1 - merged['discount_pct'] / 100)
print("Total order_value (should be 97358.30):", round(merged['order_value'].sum(), 2))

Q1 = merged['quantity'].quantile(0.25)
Q3 = merged['quantity'].quantile(0.75)
IQR = Q3 - Q1
lower = Q1 - 1.5 * IQR
upper = Q3 + 1.5 * IQR
merged['is_outlier'] = (merged['quantity'] < lower) | (merged['quantity'] > upper)
print("Number of outlier rows flagged (should be 2):", merged['is_outlier'].sum())

# CHART 1: return_rate_by_payment.png
# ============================================================
rates = merged.groupby('payment_method')['returned'].mean().mul(100).round(1)
rates = rates.sort_values(ascending=False)

fig, ax = plt.subplots(figsize=(7, 5))
bars = ax.bar(rates.index, rates.values, color=['#d9534f', '#f0ad4e', '#5bc0de'])

for bar, val in zip(bars, rates.values):
    ax.text(bar.get_x() + bar.get_width() / 2, bar.get_height() + 0.5,
             f"{val}%", ha='center', va='bottom', fontweight='bold')

ax.set_ylabel("Return Rate (%)")
ax.set_xlabel("Payment Method")
cod_rate = rates.get('COD', 0)
card_rate = rates.get('CARD', 1)
multiple = round(cod_rate / card_rate, 1) if card_rate else 0
ax.set_title(f"COD Returns at {cod_rate}% — {multiple}x Card")
ax.set_ylim(0, max(rates.values) * 1.2)
plt.tight_layout()
plt.savefig("visualizations/return_rate_by_payment.png", dpi=150)
plt.close()
print("Saved visualizations/return_rate_by_payment.png")


# ============================================================
# CHART 2: monthly_revenue_trend.png (outlier-corrected)
# ============================================================
merged['order_date'] = pd.to_datetime(merged['order_date'])
merged['year_month'] = merged['order_date'].dt.to_period('M').astype(str)

monthly_corrected = (
    merged.loc[~merged['is_outlier']]
    .groupby('year_month')['order_value'].sum().round(2)
)
peak_month = monthly_corrected.idxmax()
peak_value = monthly_corrected.max()

fig, ax = plt.subplots(figsize=(8, 5))
ax.plot(monthly_corrected.index, monthly_corrected.values, marker='o', linewidth=2, color='#5cb85c')
ax.set_xlabel("Month")
ax.set_ylabel("Total Revenue (Rs)")
ax.set_title(f"Outlier-Corrected Monthly Revenue — Peak Month: {peak_month} (Rs {peak_value:,.2f})")
ax.grid(True, alpha=0.3)
plt.tight_layout()
plt.savefig("visualizations/monthly_revenue_trend.png", dpi=150)
plt.close()
print("Saved visualizations/monthly_revenue_trend.png")
