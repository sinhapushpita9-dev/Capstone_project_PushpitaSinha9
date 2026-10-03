---Task 3: Reports

--a) Order totals —
SELECT
    COUNT(*) AS total_orders,
    ROUND(SUM(o.quantity * p.price * (1 - COALESCE(o.discount_pct, 0) / 100.0)), 2) AS total_revenue,
    ROUND(SUM(o.quantity * p.price * (1 - COALESCE(o.discount_pct, 0) / 100.0)) / COUNT(*), 2) AS avg_order_value
FROM orders o
JOIN products p ON o.product_id = p.product_id;

--b)COUNT(*) vs COUNT(column)
 SELECT
    COUNT(*) AS total_rows,
    COUNT(rating) AS rated_rows,
    COUNT(*) - COUNT(rating) AS unrated_rows
FROM orders;


--c) LEFT JOIN with a genuine zero-match row --
SELECT c.customer_id, c.name
FROM customers c
LEFT JOIN orders o ON c.customer_id = o.customer_id
GROUP BY c.customer_id, c.name
HAVING COUNT(o.order_id) = 0;

SELECT customer_id, name
FROM customers
WHERE customer_id NOT IN (SELECT DISTINCT customer_id FROM orders);


--d) GROUP BY + HAVING--
SELECT
    c.city,
    COUNT(*) AS total_orders,
    SUM(o.returned) AS returned_orders,
    ROUND(SUM(o.returned) * 100.0 / COUNT(*), 1) AS return_rate_pct
FROM orders o
JOIN customers c ON o.customer_id = c.customer_id
GROUP BY c.city
HAVING ROUND(SUM(o.returned) * 100.0 / COUNT(*), 1) > 20
ORDER BY return_rate_pct DESC;

--e)Ranking with ORDER BY + LIMIT/OFFSET--
SELECT
    c.customer_id, c.name,
    ROUND(SUM(o.quantity * p.price * (1 - COALESCE(o.discount_pct, 0) / 100.0)), 2) AS total_spend
FROM orders o
JOIN products p ON o.product_id = p.product_id
JOIN customers c ON o.customer_id = c.customer_id
GROUP BY c.customer_id, c.name
ORDER BY total_spend DESC, c.customer_id ASC
LIMIT 5;

SELECT
    c.customer_id, c.name,
    ROUND(SUM(o.quantity * p.price * (1 - COALESCE(o.discount_pct, 0) / 100.0)), 2) AS total_spend
FROM orders o
JOIN products p ON o.product_id = p.product_id
JOIN customers c ON o.customer_id = c.customer_id
GROUP BY c.customer_id, c.name
ORDER BY total_spend DESC, c.customer_id ASC
LIMIT 3 OFFSET 2;

--f)Three-table JOIN with GROUP BY --
SELECT
    p.category,
    COUNT(*) AS order_count,
    ROUND(SUM(o.quantity * p.price * (1 - COALESCE(o.discount_pct, 0) / 100.0)), 2) AS category_revenue
FROM orders o
JOIN products p ON o.product_id = p.product_id
JOIN customers c ON o.customer_id = c.customer_id
GROUP BY p.category
ORDER BY category_revenue DESC;

--g) LIKE pattern match--
SELECT customer_id, name
FROM customers
WHERE name LIKE 'A%';

--h)DISTINCT-
SELECT DISTINCT acquisition_source
FROM customers;

--i)ALTER TABLE + UPDATE with CASE--
ALTER TABLE customers ADD COLUMN loyalty_tier VARCHAR(10);
 
UPDATE customers
SET loyalty_tier = CASE WHEN city_tier = 1 THEN 'Gold' ELSE 'Silver' END;
 
SELECT loyalty_tier, COUNT(*)
FROM customers
GROUP BY loyalty_tier;
 
