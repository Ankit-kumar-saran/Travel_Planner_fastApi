-- Stored procedure used by GET /places/best-value
-- Ranks places inside a budget by rating-to-cost ratio.
--
-- Run as a MySQL user that has CREATE ROUTINE rights (e.g. root):
--   mysql -u root -p wandersync < sql/procedures.sql
-- Then give the app user permission to call it:
--   GRANT EXECUTE ON wandersync.* TO 'wandersync_user'@'localhost';

DROP PROCEDURE IF EXISTS GetBestValuePlaces;

DELIMITER //
CREATE PROCEDURE GetBestValuePlaces(
    IN in_city_id INT,
    IN in_max_cost DECIMAL(10,2)
)
BEGIN
    SELECT p.place_id, p.name, p.avg_cost, p.rating,
           p.latitude, p.longitude,
           c.name AS city, cat.name AS category,
           (p.rating / NULLIF(p.avg_cost, 0)) AS value_score
    FROM places p
    JOIN cities c ON p.city_id = c.city_id
    JOIN categories cat ON p.category_id = cat.category_id
    WHERE p.city_id = in_city_id
      AND p.avg_cost <= in_max_cost
      AND p.rating IS NOT NULL
    ORDER BY value_score DESC
    LIMIT 10;
END //
DELIMITER ;
