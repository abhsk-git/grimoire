-- LinkVault Blog Schema
-- Run: mysql -u root -p linkvault < schema_blog.sql

CREATE TABLE IF NOT EXISTS blog_posts (
  id            INT AUTO_INCREMENT PRIMARY KEY,
  user_id       INT NOT NULL,
  title         VARCHAR(500) NOT NULL,
  slug          VARCHAR(600) NOT NULL,
  excerpt       TEXT,
  content       LONGTEXT,
  cover_image   VARCHAR(500) DEFAULT '',
  tags          VARCHAR(500) DEFAULT '',
  status        ENUM('draft','published') DEFAULT 'draft',
  reading_time  TINYINT UNSIGNED DEFAULT 1,
  views         INT UNSIGNED DEFAULT 0,
  likes         INT UNSIGNED DEFAULT 0,
  featured      TINYINT(1) DEFAULT 0,
  created_at    TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
  updated_at    TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
  published_at  TIMESTAMP NULL,
  UNIQUE KEY uq_slug (slug),
  FULLTEXT KEY ft_posts (title, excerpt, tags),
  FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE IF NOT EXISTS blog_likes (
  id           INT AUTO_INCREMENT PRIMARY KEY,
  post_id      INT NOT NULL,
  user_id      INT NULL,
  session_key  VARCHAR(64) NULL,
  created_at   TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
  UNIQUE KEY uq_user_like    (post_id, user_id),
  UNIQUE KEY uq_session_like (post_id, session_key),
  FOREIGN KEY (post_id) REFERENCES blog_posts(id) ON DELETE CASCADE,
  FOREIGN KEY (user_id) REFERENCES users(id)      ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE IF NOT EXISTS blog_comments (
  id           INT AUTO_INCREMENT PRIMARY KEY,
  post_id      INT NOT NULL,
  user_id      INT NULL,
  author_name  VARCHAR(100) DEFAULT 'Anonymous',
  content      TEXT NOT NULL,
  created_at   TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
  FOREIGN KEY (post_id) REFERENCES blog_posts(id) ON DELETE CASCADE,
  FOREIGN KEY (user_id) REFERENCES users(id)      ON DELETE SET NULL
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
