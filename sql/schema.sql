-- WanderSync database schema (MySQL 8.0 / InnoDB)
-- Safe to run on an existing database: every statement uses IF NOT EXISTS / INSERT IGNORE.
--
-- Run with:   mysql -u root -p wandersync < sql/schema.sql

CREATE TABLE IF NOT EXISTS users (
    user_id       INT PRIMARY KEY AUTO_INCREMENT,
    name          VARCHAR(50)  NOT NULL,
    email         VARCHAR(100) NOT NULL UNIQUE,
    password_hash VARCHAR(255) NOT NULL,
    role          ENUM('user','admin') NOT NULL DEFAULT 'user',
    created_at    TIMESTAMP NULL DEFAULT CURRENT_TIMESTAMP
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

CREATE TABLE IF NOT EXISTS cities (
    city_id INT PRIMARY KEY AUTO_INCREMENT,
    name    VARCHAR(50) NOT NULL UNIQUE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

CREATE TABLE IF NOT EXISTS categories (
    category_id INT PRIMARY KEY AUTO_INCREMENT,
    name        VARCHAR(50) NOT NULL UNIQUE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

CREATE TABLE IF NOT EXISTS places (
    place_id    INT PRIMARY KEY AUTO_INCREMENT,
    name        VARCHAR(100) NOT NULL,
    avg_cost    DECIMAL(10,2) DEFAULT 0.00,
    rating      DECIMAL(2,1) NULL,
    latitude    DECIMAL(9,6) NOT NULL,
    longitude   DECIMAL(9,6) NOT NULL,
    city_id     INT NOT NULL,
    category_id INT NOT NULL,
    FOREIGN KEY (city_id) REFERENCES cities(city_id),
    FOREIGN KEY (category_id) REFERENCES categories(category_id),
    INDEX idx_places_rating (rating)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

CREATE TABLE IF NOT EXISTS trips (
    trip_id        INT PRIMARY KEY AUTO_INCREMENT,
    user_id        INT NOT NULL,
    city_id        INT NOT NULL,
    planned_budget DECIMAL(10,2) DEFAULT 0.00,
    start_date     DATE NULL,
    end_date       DATE NULL,
    created_at     TIMESTAMP NULL DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (user_id) REFERENCES users(user_id),
    FOREIGN KEY (city_id) REFERENCES cities(city_id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

CREATE TABLE IF NOT EXISTS trip_places (
    id           INT PRIMARY KEY AUTO_INCREMENT,
    trip_id      INT NOT NULL,
    place_id     INT NOT NULL,
    day_number   INT NOT NULL,
    visit_order  INT NOT NULL,
    planned_cost DECIMAL(10,2) DEFAULT 0.00,
    FOREIGN KEY (trip_id) REFERENCES trips(trip_id),
    FOREIGN KEY (place_id) REFERENCES places(place_id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

CREATE TABLE IF NOT EXISTS favorites (
    id       INT PRIMARY KEY AUTO_INCREMENT,
    user_id  INT NOT NULL,
    place_id INT NOT NULL,
    FOREIGN KEY (user_id) REFERENCES users(user_id),
    FOREIGN KEY (place_id) REFERENCES places(place_id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

CREATE TABLE IF NOT EXISTS reviews (
    id         INT PRIMARY KEY AUTO_INCREMENT,
    user_id    INT NOT NULL,
    place_id   INT NOT NULL,
    rating     DECIMAL(2,1) NULL,
    comment    TEXT NULL,
    created_at TIMESTAMP NULL DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (user_id) REFERENCES users(user_id),
    FOREIGN KEY (place_id) REFERENCES places(place_id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

CREATE TABLE IF NOT EXISTS user_searches (
    id          INT PRIMARY KEY AUTO_INCREMENT,
    user_id     INT NULL,
    city_id     INT NOT NULL,
    searched_at TIMESTAMP NULL DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (user_id) REFERENCES users(user_id),
    FOREIGN KEY (city_id) REFERENCES cities(city_id),
    INDEX idx_searches_time (searched_at)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

CREATE TABLE IF NOT EXISTS expenses (
    id         INT PRIMARY KEY AUTO_INCREMENT,
    trip_id    INT NOT NULL,
    amount     DECIMAL(10,2) NOT NULL,
    category   VARCHAR(50) NULL,
    spent_date DATE NOT NULL,
    note       VARCHAR(255) NULL,
    FOREIGN KEY (trip_id) REFERENCES trips(trip_id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

-- NEW TABLE (not in your original 10): needed for the "forgot password" feature.
-- Only a SHA-256 hash of the token is stored, never the token itself.
CREATE TABLE IF NOT EXISTS password_resets (
    id         INT PRIMARY KEY AUTO_INCREMENT,
    user_id    INT NOT NULL,
    token_hash CHAR(64) NOT NULL,
    expires_at DATETIME NOT NULL,
    used       TINYINT(1) NOT NULL DEFAULT 0,
    FOREIGN KEY (user_id) REFERENCES users(user_id),
    INDEX idx_reset_token (token_hash)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

-- Seed data
INSERT IGNORE INTO categories (name) VALUES ('Hotel'), ('Restaurant'), ('Attraction');
