-- AQOS baseline stored procedures.
-- Stored procedures are first-class database artifacts and ship as migrations.

DROP PROCEDURE IF EXISTS sp_aqos_schema_version;

DELIMITER $$

CREATE PROCEDURE sp_aqos_schema_version()
BEGIN
    SELECT
        COALESCE(MAX(version), 0) AS schema_version,
        COUNT(*) AS applied_count
    FROM schema_migrations;
END $$

DELIMITER ;

DROP PROCEDURE IF EXISTS sp_aqos_set_metadata;

DELIMITER $$

CREATE PROCEDURE sp_aqos_set_metadata(
    IN p_metadata_key VARCHAR(191),
    IN p_metadata_value VARCHAR(1024)
)
BEGIN
    INSERT INTO aqos_metadata (metadata_key, metadata_value)
    VALUES (p_metadata_key, p_metadata_value)
    ON DUPLICATE KEY UPDATE metadata_value = p_metadata_value;
END $$

DELIMITER ;

DROP PROCEDURE IF EXISTS sp_aqos_metadata_count;

DELIMITER $$

CREATE PROCEDURE sp_aqos_metadata_count(
    OUT p_total INT
)
BEGIN
    SELECT COUNT(*) INTO p_total FROM aqos_metadata;
END $$

DELIMITER ;
