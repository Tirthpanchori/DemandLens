-- name: weekly_sales
WITH weekly AS (
 SELECT product_id, date(date, '-' || ((cast(strftime('%w', date) AS integer)+6)%7) || ' days') AS week,
        SUM(units_sold) AS units_sold, SUM(gross_sales_value) AS gross_sales_value
 FROM daily_sales WHERE (:product_id IS NULL OR product_id=:product_id)
 GROUP BY product_id, week
), compared AS (
 SELECT *, LAG(units_sold) OVER (PARTITION BY product_id ORDER BY week) AS previous_units
 FROM weekly
)
SELECT *, 100.0*(units_sold-previous_units)/NULLIF(previous_units,0) AS wow_percent
FROM compared ORDER BY week, product_id;

-- name: top_products
SELECT d.product_id, p.description, SUM(d.units_sold) AS units_sold,
       SUM(d.gross_sales_value) AS gross_sales_value
FROM daily_sales d JOIN products p USING(product_id)
WHERE (:product_id IS NULL OR d.product_id=:product_id)
GROUP BY d.product_id ORDER BY units_sold DESC, d.product_id;

-- name: weekday_sales
SELECT (cast(strftime('%w',date) AS integer)+6)%7 AS weekday,
       AVG(units_sold) AS average_units, SUM(units_sold) AS total_units, COUNT(*) AS product_days
FROM daily_sales WHERE (:product_id IS NULL OR product_id=:product_id)
GROUP BY weekday ORDER BY weekday;

-- name: zero_sales
SELECT product_id, COUNT(*) AS days, SUM(CASE WHEN units_sold=0 THEN 1 ELSE 0 END) AS zero_days,
       100.0*SUM(CASE WHEN units_sold=0 THEN 1 ELSE 0 END)/COUNT(*) AS zero_percent
FROM daily_sales WHERE (:product_id IS NULL OR product_id=:product_id) GROUP BY product_id;

-- name: variability
SELECT product_id, AVG(units_sold) AS mean_units,
       MAX(0,AVG(units_sold*units_sold)-AVG(units_sold)*AVG(units_sold)) AS variance_units,
       MAX(units_sold) AS maximum_units
FROM daily_sales WHERE (:product_id IS NULL OR product_id=:product_id) GROUP BY product_id;

-- name: model_metrics
SELECT model, COUNT(*) AS observations, AVG(ABS(prediction-actual)) AS mae,
       100.0*SUM(ABS(prediction-actual))/NULLIF(SUM(actual),0) AS wape,
       AVG(prediction-actual) AS bias
FROM forecasts WHERE split=:split AND actual IS NOT NULL
 AND (:product_id IS NULL OR product_id=:product_id) AND (:model IS NULL OR model=:model)
GROUP BY model ORDER BY wape,mae;

-- name: product_errors
SELECT product_id, model, AVG(ABS(prediction-actual)) AS mae, AVG(prediction-actual) AS bias,
       100.0*SUM(ABS(prediction-actual))/NULLIF(SUM(actual),0) AS wape,
       MAX(ABS(prediction-actual)) AS largest_daily_error
FROM forecasts WHERE split=:split AND actual IS NOT NULL
 AND (:product_id IS NULL OR product_id=:product_id) AND (:model IS NULL OR model=:model)
GROUP BY product_id,model ORDER BY mae DESC;

-- name: horizon_errors
SELECT model,horizon, AVG(ABS(prediction-actual)) AS mae,
       100.0*SUM(ABS(prediction-actual))/NULLIF(SUM(actual),0) AS wape
FROM forecasts WHERE split=:split AND actual IS NOT NULL
 AND (:product_id IS NULL OR product_id=:product_id) AND (:model IS NULL OR model=:model)
GROUP BY model,horizon ORDER BY model,horizon;

-- name: window_errors
SELECT model,origin,AVG(ABS(prediction-actual)) AS mae,
       100.0*SUM(ABS(prediction-actual))/NULLIF(SUM(actual),0) AS wape
FROM forecasts WHERE split=:split AND actual IS NOT NULL
 AND (:product_id IS NULL OR product_id=:product_id) AND (:model IS NULL OR model=:model)
GROUP BY model,origin ORDER BY origin,model;

-- name: worst_predictions
SELECT product_id,model,origin,target_date,horizon,actual,prediction,
       ABS(prediction-actual) AS absolute_error
FROM forecasts WHERE split=:split AND actual IS NOT NULL
 AND (:product_id IS NULL OR product_id=:product_id) AND (:model IS NULL OR model=:model)
ORDER BY absolute_error DESC LIMIT 20;

-- name: cumulative_errors
SELECT product_id,model,origin,SUM(actual) AS actual_units,SUM(prediction) AS predicted_units,
       ABS(SUM(prediction)-SUM(actual)) AS cumulative_absolute_error
FROM forecasts WHERE split=:split AND actual IS NOT NULL
 AND (:product_id IS NULL OR product_id=:product_id) AND (:model IS NULL OR model=:model)
GROUP BY product_id,model,origin ORDER BY cumulative_absolute_error DESC;
