CREATE DATABASE IF NOT EXISTS pet_adoption;
USE pet_adoption;

CREATE TABLE shelters (
    shelter_id INT AUTO_INCREMENT PRIMARY KEY,
    name VARCHAR(100) NOT NULL,
    email VARCHAR(100) UNIQUE NOT NULL,
    password VARCHAR(255) NOT NULL,
    phone VARCHAR(15),
    address VARCHAR(255)
);

CREATE TABLE users (
    user_id INT AUTO_INCREMENT PRIMARY KEY,
    name VARCHAR(100) NOT NULL,
    email VARCHAR(100) UNIQUE NOT NULL,
    password VARCHAR(255) NOT NULL,
    phone VARCHAR(15)
);

CREATE TABLE pets (
    pet_id INT AUTO_INCREMENT PRIMARY KEY,
    shelter_id INT NOT NULL,
    name VARCHAR(50) NOT NULL,
    species ENUM('Dog','Cat','Rabbit','Bird') NOT NULL,
    breed VARCHAR(50),
    age INT,
    description TEXT,
    image_filename VARCHAR(255),
    status ENUM('Available','Pending','Adopted') DEFAULT 'Available',
    FOREIGN KEY (shelter_id) REFERENCES shelters(shelter_id)
);

CREATE TABLE adoption_requests (
    request_id INT AUTO_INCREMENT PRIMARY KEY,
    user_id INT NOT NULL,
    pet_id INT NOT NULL,
    request_date DATETIME DEFAULT CURRENT_TIMESTAMP,
    status ENUM('Pending','Approved','Rejected') DEFAULT 'Pending',
    FOREIGN KEY (user_id) REFERENCES users(user_id),
    FOREIGN KEY (pet_id) REFERENCES pets(pet_id)
);

-- Seed data so every fresh environment (a teammate's laptop, a redeployed
-- AWS server) shows demo pets immediately instead of an empty homepage.
-- Login: demo@shelter.com / Demo@1234
INSERT INTO shelters (name, email, password, phone, address) VALUES
('Happy Paws Shelter', 'demo@shelter.com', 'scrypt:32768:8:1$MJJLnahWtKBIYUli$bff9658257b7d83a8c0d8d50adac7bcb34a2819735b67db3c0bac38a11b8bf447791910b09cc3fbda03c626a6efe203b9cb19c2438eb8deeb3de69b3037881f5', '9999999999', 'Pune, Maharashtra');

INSERT INTO pets (shelter_id, name, species, breed, age, description, status) VALUES
(1, 'Bruno', 'Dog', 'Labrador', 2, 'Friendly and playful, great with kids.', 'Available'),
(1, 'Whiskers', 'Cat', 'Persian', 1, 'Calm and affectionate lap cat.', 'Available'),
(1, 'Coco', 'Rabbit', 'Holland Lop', 1, 'Curious and loves to hop around the garden.', 'Available');