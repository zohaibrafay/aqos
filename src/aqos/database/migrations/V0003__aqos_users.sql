-- AQOS user profiles, credentials, sessions and preferences.

CREATE TABLE IF NOT EXISTS user_profiles (
    user_id VARCHAR(64) NOT NULL,
    email VARCHAR(191) NOT NULL,
    display_name VARCHAR(191) NOT NULL,
    role VARCHAR(32) NOT NULL DEFAULT 'trader',
    status VARCHAR(32) NOT NULL DEFAULT 'active',
    timezone VARCHAR(64) NOT NULL DEFAULT 'UTC',
    locale VARCHAR(16) NOT NULL DEFAULT 'en',
    created_at_utc DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at_utc DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP
        ON UPDATE CURRENT_TIMESTAMP,
    metadata_json JSON NOT NULL,
    PRIMARY KEY (user_id),
    UNIQUE KEY uq_user_profiles_email (email),
    KEY ix_user_profiles_status (status)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE IF NOT EXISTS user_credentials (
    user_id VARCHAR(64) NOT NULL,
    password_hash VARCHAR(512) NOT NULL,
    failed_attempt_count INT NOT NULL DEFAULT 0,
    locked_until_utc DATETIME NULL,
    last_login_at_utc DATETIME NULL,
    password_updated_at_utc DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    created_at_utc DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at_utc DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP
        ON UPDATE CURRENT_TIMESTAMP,
    metadata_json JSON NOT NULL,
    PRIMARY KEY (user_id),
    CONSTRAINT fk_user_credentials_user_id_user_profiles
        FOREIGN KEY (user_id) REFERENCES user_profiles (user_id)
        ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE IF NOT EXISTS user_sessions (
    session_id VARCHAR(64) NOT NULL,
    user_id VARCHAR(64) NOT NULL,
    token_hash CHAR(64) NOT NULL,
    created_at_utc DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    expires_at_utc DATETIME NOT NULL,
    revoked_at_utc DATETIME NULL,
    last_seen_at_utc DATETIME NULL,
    client_label VARCHAR(191) NULL,
    metadata_json JSON NOT NULL,
    PRIMARY KEY (session_id),
    UNIQUE KEY uq_user_sessions_token_hash (token_hash),
    KEY ix_user_sessions_user_id (user_id, expires_at_utc),
    CONSTRAINT fk_user_sessions_user_id_user_profiles
        FOREIGN KEY (user_id) REFERENCES user_profiles (user_id)
        ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE IF NOT EXISTS user_preferences (
    preferences_id VARCHAR(64) NOT NULL,
    user_id VARCHAR(64) NOT NULL,
    theme VARCHAR(32) NOT NULL DEFAULT 'system',
    default_currency CHAR(3) NOT NULL DEFAULT 'USD',
    date_format VARCHAR(32) NOT NULL DEFAULT 'YYYY-MM-DD',
    landing_page VARCHAR(32) NOT NULL DEFAULT 'dashboard',
    notification_channels JSON NOT NULL,
    email_notifications_enabled TINYINT(1) NOT NULL DEFAULT 1,
    push_notifications_enabled TINYINT(1) NOT NULL DEFAULT 1,
    created_at_utc DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at_utc DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP
        ON UPDATE CURRENT_TIMESTAMP,
    metadata_json JSON NOT NULL,
    PRIMARY KEY (preferences_id),
    UNIQUE KEY uq_user_preferences_user_id (user_id),
    CONSTRAINT fk_user_preferences_user_id_user_profiles
        FOREIGN KEY (user_id) REFERENCES user_profiles (user_id)
        ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

DROP PROCEDURE IF EXISTS sp_aqos_user_status_counts;

DELIMITER $$

CREATE PROCEDURE sp_aqos_user_status_counts()
BEGIN
    SELECT status, COUNT(*) AS total
    FROM user_profiles
    GROUP BY status
    ORDER BY status;
END $$

DELIMITER ;

DROP PROCEDURE IF EXISTS sp_aqos_purge_expired_sessions;

DELIMITER $$

CREATE PROCEDURE sp_aqos_purge_expired_sessions(
    IN p_now_utc DATETIME,
    OUT p_deleted INT
)
BEGIN
    DELETE FROM user_sessions WHERE expires_at_utc <= p_now_utc;
    SET p_deleted = ROW_COUNT();
END $$

DELIMITER ;
