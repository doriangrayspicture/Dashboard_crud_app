create database dashboard;
--creating database

ALTER USER 'root'@'localhost' IDENTIFIED WITH mysql_native_password BY 'sunetra';
FLUSH PRIVILEGES;
USE dashboard;
--letting sql authenticate using given password without cryptography
CREATE TABLE data (
    id INT AUTO_INCREMENT PRIMARY KEY,
    particular_id INT NOT NULL,
    date DATE NOT NULL,
    mu FLOAT NOT NULL,
    rate FLOAT NOT NULL,
    FOREIGN KEY (particular_id) REFERENCES particulars(id),
    UNIQUE (particular_id, date)   -- ensures only one row per particular per date

);
CREATE TABLE particulars (
    id INT AUTO_INCREMENT PRIMARY KEY,
    pname VARCHAR(100) NOT NULL UNIQUE
);


INSERT INTO users (id,username, userpassword,userrole)
VALUES (1,'admin','1234','admin);' 
--inserting first admin or user


CREATE TABLE log (
    logid INT AUTO_INCREMENT PRIMARY KEY,
    username VARCHAR(255) NOT NULL,
    action ENUM('insert', 'edit', 'new_particular') NOT NULL,
    details VARCHAR(255),
    datetime TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
