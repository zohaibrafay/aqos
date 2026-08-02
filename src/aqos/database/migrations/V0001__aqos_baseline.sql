-- AQOS baseline schema.
-- Creates the migration ledger and the platform metadata table.

CREATE TABLE IF NOT EXISTS schema_migrations (
    version INT NOT NULL,
    name VARCHAR(255) NOT NULL,
    checksum VARCHAR(64) NOT NULL,
    applied_at_utc DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (version)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE IF NOT EXISTS aqos_metadata (
    metadata_key VARCHAR(191) NOT NULL,
    metadata_value VARCHAR(1024) NOT NULL,
    updated_at_utc DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP
        ON UPDATE CURRENT_TIMESTAMP,
    PRIMARY KEY (metadata_key)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

INSERT INTO aqos_metadata (metadata_key, metadata_value)
VALUES ('schema_owner', 'aqos')
ON DUPLICATE KEY UPDATE metadata_value = VALUES(metadata_value);
