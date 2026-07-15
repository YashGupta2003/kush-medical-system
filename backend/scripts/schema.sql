-- Reference schema (SQLAlchemy creates these automatically on first run,
-- this file is for your project report / viva and manual inspection).

CREATE DATABASE IF NOT EXISTS kush_medical CHARACTER SET utf8mb4;
USE kush_medical;

CREATE TABLE medicines (
    id INT AUTO_INCREMENT PRIMARY KEY,
    particulars VARCHAR(255) NOT NULL,
    normalized_name VARCHAR(255) NOT NULL,
    unit VARCHAR(50),
    mrp DECIMAL(10,2),
    net_rate DECIMAL(10,2),
    company VARCHAR(100),
    stockist VARCHAR(100),
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    updated_at DATETIME DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    INDEX idx_normalized_name (normalized_name)
);

CREATE TABLE distributors (
    id INT AUTO_INCREMENT PRIMARY KEY,
    name VARCHAR(150) NOT NULL UNIQUE,
    gstin VARCHAR(20),
    address VARCHAR(255),
    phone VARCHAR(50)
);

CREATE TABLE bills (
    id INT AUTO_INCREMENT PRIMARY KEY,
    distributor_id INT,
    invoice_no VARCHAR(100),
    invoice_date DATETIME,
    year INT,
    month INT,
    image_path VARCHAR(500),
    total_amount DECIMAL(10,2),
    status ENUM('pending_review','confirmed','rejected') DEFAULT 'pending_review',
    uploaded_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    raw_ocr_text TEXT,
    FOREIGN KEY (distributor_id) REFERENCES distributors(id),
    INDEX idx_year_month (year, month)
);

CREATE TABLE bill_items (
    id INT AUTO_INCREMENT PRIMARY KEY,
    bill_id INT NOT NULL,
    medicine_id INT,
    raw_name VARCHAR(255) NOT NULL,
    pack VARCHAR(50),
    batch VARCHAR(50),
    exp_date VARCHAR(20),
    qty DECIMAL(10,2) DEFAULT 0,
    free_qty DECIMAL(10,2) DEFAULT 0,
    mrp DECIMAL(10,2),
    rate DECIMAL(10,2),
    discount_pct DECIMAL(5,2) DEFAULT 0,
    special_discount_pct DECIMAL(5,2) DEFAULT 0,
    gst_pct DECIMAL(5,2) DEFAULT 0,
    amount DECIMAL(10,2),
    computed_cost_per_unit DECIMAL(10,2),
    match_confidence DECIMAL(5,2),
    match_status ENUM('auto','manual','unmatched','confirmed') DEFAULT 'unmatched',
    FOREIGN KEY (bill_id) REFERENCES bills(id) ON DELETE CASCADE,
    FOREIGN KEY (medicine_id) REFERENCES medicines(id)
);

CREATE TABLE rate_history (
    id INT AUTO_INCREMENT PRIMARY KEY,
    medicine_id INT NOT NULL,
    bill_item_id INT,
    old_net_rate DECIMAL(10,2),
    new_net_rate DECIMAL(10,2),
    old_mrp DECIMAL(10,2),
    new_mrp DECIMAL(10,2),
    changed_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (medicine_id) REFERENCES medicines(id),
    FOREIGN KEY (bill_item_id) REFERENCES bill_items(id)
);
