-- LinkVault Database Schema
-- Run this once to set up your database

CREATE DATABASE IF NOT EXISTS linkvault CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;
USE linkvault;

-- Users table
CREATE TABLE IF NOT EXISTS users (
    id INT AUTO_INCREMENT PRIMARY KEY,
    name VARCHAR(100) NOT NULL,
    email VARCHAR(255) NOT NULL UNIQUE,
    password_hash VARCHAR(255),
    google_id VARCHAR(255),
    avatar VARCHAR(500),
    bio VARCHAR(300),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    INDEX idx_email (email),
    INDEX idx_google (google_id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

-- Collections (folders)
CREATE TABLE IF NOT EXISTS collections (
    id INT AUTO_INCREMENT PRIMARY KEY,
    user_id INT NOT NULL,
    name VARCHAR(100) NOT NULL,
    color VARCHAR(20) DEFAULT '#6366f1',
    icon VARCHAR(10) DEFAULT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE,
    INDEX idx_user (user_id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

-- Links table
CREATE TABLE IF NOT EXISTS links (
    id INT AUTO_INCREMENT PRIMARY KEY,
    user_id INT NOT NULL,
    collection_id INT,
    url TEXT NOT NULL,
    title VARCHAR(255),
    description VARCHAR(500),
    image VARCHAR(500),
    favicon VARCHAR(255),
    tags VARCHAR(255),
    notes TEXT,
    is_public TINYINT(1) DEFAULT 0,
    visit_count INT DEFAULT 0,
    last_visited TIMESTAMP NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE,
    FOREIGN KEY (collection_id) REFERENCES collections(id) ON DELETE SET NULL,
    INDEX idx_user (user_id),
    INDEX idx_public (is_public),
    FULLTEXT INDEX ft_search (title, description, tags)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;