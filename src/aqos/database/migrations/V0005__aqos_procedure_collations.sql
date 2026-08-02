-- Pin the collation of stored procedure string parameters.
--
-- A VARCHAR parameter without an explicit collation inherits the database
-- default (utf8mb4_0900_ai_ci on MySQL 8), while AQOS tables pin
-- utf8mb4_unicode_ci. Comparing the two raises "Illegal mix of collations".
--
-- V0002 shipped sp_aqos_set_metadata before this was understood. Applied
-- migrations are never edited, so the procedure is redefined here instead.

DROP PROCEDURE IF EXISTS sp_aqos_set_metadata;

DELIMITER $$

CREATE PROCEDURE sp_aqos_set_metadata(
    IN p_metadata_key VARCHAR(191) CHARACTER SET utf8mb4
        COLLATE utf8mb4_unicode_ci,
    IN p_metadata_value VARCHAR(1024) CHARACTER SET utf8mb4
        COLLATE utf8mb4_unicode_ci
)
BEGIN
    INSERT INTO aqos_metadata (metadata_key, metadata_value)
    VALUES (p_metadata_key, p_metadata_value)
    ON DUPLICATE KEY UPDATE metadata_value = p_metadata_value;
END $$

DELIMITER ;
