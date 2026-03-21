-- Create database if not exists
CREATE DATABASE IF NOT EXISTS workshop_db;
USE workshop_db;

-- ----------------------
-- 1. Users Table (all types: technician, complaint locker, admin)
-- ----------------------
DROP TABLE IF EXISTS users;
CREATE TABLE users (
    id INT AUTO_INCREMENT PRIMARY KEY,
    username VARCHAR(100) NOT NULL UNIQUE,
    full_name VARCHAR(150),
    email VARCHAR(100) NOT NULL UNIQUE,
    password_hash VARCHAR(255) NOT NULL,
    role ENUM('technician', 'complaint_locker', 'admin', 'other') NOT NULL,
    designation VARCHAR(100),
    department VARCHAR(100),
    staff_no VARCHAR(50) UNIQUE,
    contact VARCHAR(50),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- ----------------------
-- 2. Technicians Table (extra info for technicians)
-- ----------------------
DROP TABLE IF EXISTS technicians;
CREATE TABLE technicians (
    id INT AUTO_INCREMENT PRIMARY KEY,
    user_id INT NOT NULL,
    skills TEXT,              -- comma separated skills or JSON string
    experience_years INT,
    FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
);

-- ----------------------
-- 3. Complaint Lockers Table (extra info for complaint lockers)
-- ----------------------
DROP TABLE IF EXISTS complaint_lockers;
CREATE TABLE complaint_lockers (
    id INT AUTO_INCREMENT PRIMARY KEY,
    user_id INT NOT NULL,
    department VARCHAR(100),
    location VARCHAR(100),
    FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
);

-- ----------------------
-- 4. Complaints Table (linked to lockers and technicians)
-- ----------------------
DROP TABLE IF EXISTS complaints;
CREATE TABLE complaints (
    id INT AUTO_INCREMENT PRIMARY KEY,
    locker_id INT NOT NULL,
    technician_id INT,
    title VARCHAR(200),
    description TEXT,
    status ENUM('open', 'in_progress', 'closed') DEFAULT 'open',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    FOREIGN KEY (locker_id) REFERENCES complaint_lockers(id),
    FOREIGN KEY (technician_id) REFERENCES technicians(id)
);

-- ----------------------
-- 5. Service Memo Table
-- ----------------------
DROP TABLE IF EXISTS service_memo;
CREATE TABLE service_memo (
    service_id INT AUTO_INCREMENT PRIMARY KEY,
    complain_no VARCHAR(50) NOT NULL,
    location VARCHAR(100),
    ext_no VARCHAR(20),
    user_name VARCHAR(100),
    staff_no VARCHAR(50),
    ip_address VARCHAR(45),
    product_name VARCHAR(100),
    model VARCHAR(100),
    serial_no VARCHAR(100),
    ram VARCHAR(50),
    hdd VARCHAR(50),
    lniata VARCHAR(50),
    fault BOOLEAN DEFAULT FALSE,
    diagnosed BOOLEAN DEFAULT FALSE,
    data_backup BOOLEAN DEFAULT FALSE,
    date_out DATE,
    date_in DATE,
    status VARCHAR(100),
    assigned_to INT, -- foreign key user_id
    user_details TEXT,
    task_performed BOOLEAN DEFAULT FALSE,
    last_updated TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    FOREIGN KEY (assigned_to) REFERENCES users(id)
);

-- ----------------------
-- 6. Hardware Workshop Table
-- ----------------------
DROP TABLE IF EXISTS hardware_workshop;
CREATE TABLE hardware_workshop (
    voucher_id INT AUTO_INCREMENT PRIMARY KEY,
    complaint_no VARCHAR(50),
    item_description VARCHAR(255),
    qty_issued INT,
    remarks TEXT,
    material_issued_by INT, -- foreign key to users
    material_issued_by_designation VARCHAR(100),
    material_issued_by_staff_no VARCHAR(50),
    material_issued_by_signature VARCHAR(255),
    user_name VARCHAR(100),
    user_department VARCHAR(100),
    user_designation VARCHAR(100),
    user_staff_no VARCHAR(50),
    user_contact VARCHAR(50),
    user_signature VARCHAR(255),
    technician_id INT, -- foreign key to users
    technician_designation VARCHAR(100),
    technician_staff_no VARCHAR(50),
    technician_signature VARCHAR(255),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (material_issued_by) REFERENCES users(id),
    FOREIGN KEY (technician_id) REFERENCES users(id)
);

-- ----------------------
-- 7. Internal Demand Issue Voucher Table
-- ----------------------
DROP TABLE IF EXISTS internal_demand_issue_vouchers;
CREATE TABLE internal_demand_issue_vouchers (
    id INT AUTO_INCREMENT PRIMARY KEY,
    complaint_id INT NOT NULL UNIQUE,
    item_description VARCHAR(255) NOT NULL,
    quantity_issued INT NOT NULL,
    remarks TEXT,
    created_by_admin_id INT NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    FOREIGN KEY (complaint_id) REFERENCES complaints(id) ON DELETE CASCADE,
    FOREIGN KEY (created_by_admin_id) REFERENCES users(id)
);

-- ----------------------
-- 8. Locations Table
-- ----------------------
DROP TABLE IF EXISTS locations;
CREATE TABLE locations (
    id INT AUTO_INCREMENT PRIMARY KEY,
    name VARCHAR(50) NOT NULL UNIQUE,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

INSERT INTO locations (name) VALUES
    ('head_office'),
    ('station'),
    ('workshop'),
    ('other');
