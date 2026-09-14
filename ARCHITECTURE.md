# Architecture — Pet Adoption Portal

Diagrams and data flows for the full system: the DevOps pipeline, the running containers, the database, and the key request flows through the app.

---

## 1. Deployment Pipeline (the DevOps part)

```mermaid
flowchart TD
    A[Developer's Laptop] -->|git push| B[GitHub Repository]
    B --> C{Terraform}
    C -->|creates| D[AWS EC2 Instance<br/>+ Security Group]
    D --> E{Ansible}
    E -->|installs Docker, git<br/>clones repo, deploys| F[Docker Compose on the VM]
    F --> G[frontend container<br/>nginx, port 80]
    F --> H[backend container<br/>Flask, port 5000]
    F --> I[db container<br/>MySQL, internal only]
    G <--> H
    H <--> I
    J[Browser] -->|http://VM public IP| G
    J -->|http://VM public IP:5000| H
```

**Read it as:** code goes to GitHub → Terraform creates the server → Ansible configures the server and deploys the app → Docker Compose runs the 3 containers → the browser talks to the frontend and backend containers directly.

---

## 2. Container & Volume Layout

```mermaid
flowchart LR
    Browser((Browser))

    subgraph VM["AWS EC2 Instance"]
        FE["frontend container<br/>nginx"]
        BE["backend container<br/>Flask"]
        DB["db container<br/>MySQL"]
        VOL1[("pet_images volume")]
        VOL2[("mysql_data volume")]

        FE -->|"fetch() calls"| BE
        BE -->|SQL queries| DB
        BE -.->|reads/writes photos| VOL1
        DB -.->|reads/writes tables| VOL2
    end

    Browser -->|":80"| FE
    Browser -->|":5000"| BE
```

**Why the volumes matter:** `pet_images` and `mysql_data` live *outside* the containers' own filesystem. If a container is deleted and recreated (`docker compose down` then `up`), its own filesystem is thrown away and rebuilt from the image — but the volumes survive, so uploaded photos and database rows are untouched. Only `docker compose down -v` deletes the volumes themselves.

---

## 3. Database Schema (ER Diagram)

```mermaid
erDiagram
    SHELTERS ||--o{ PETS : lists
    USERS ||--o{ ADOPTION_REQUESTS : makes
    PETS ||--o{ ADOPTION_REQUESTS : "is requested in"

    SHELTERS {
        int shelter_id PK
        string name
        string email
        string password
        string phone
        string address
    }
    USERS {
        int user_id PK
        string name
        string email
        string password
        string phone
    }
    PETS {
        int pet_id PK
        int shelter_id FK
        string name
        enum species
        string breed
        int age
        string description
        string image_filename
        enum status
    }
    ADOPTION_REQUESTS {
        int request_id PK
        int user_id FK
        int pet_id FK
        datetime request_date
        enum status
    }
```

---

## 4. Request Flow — Login & Authorization

```mermaid
sequenceDiagram
    participant B as Browser
    participant F as Flask API
    participant D as MySQL

    B->>F: POST /api/users/login {email, password}
    F->>D: SELECT * FROM users WHERE email=?
    D-->>F: user row (password is a hash)
    F->>F: check_password_hash(stored_hash, given_password)
    F->>F: build JWT {user_id, role, exp}
    F-->>B: {token, name}
    Note over B: token saved in localStorage

    B->>F: GET /api/adoption-requests/my-requests<br/>Authorization: Bearer <token>
    F->>F: decode token → get user_id from it (NOT from the URL)
    F->>D: SELECT ... WHERE user_id = (from token)
    D-->>F: only this user's requests
    F-->>B: JSON response
```

**Why "from the token, not the URL" matters:** this is the fix for the IDOR bug found during development — the server never trusts a client-supplied ID for "whose data is this," only what it verified via the token's signature.

---

## 5. Request Flow — Adding a Pet & Uploading a Photo

```mermaid
sequenceDiagram
    participant Shelter as Shelter (Browser)
    participant F as Flask API
    participant D as MySQL
    participant Disk as Uploads Volume

    Shelter->>F: POST /api/pets {name, species, ...} + JWT
    F->>F: verify role == "shelter"
    F->>D: INSERT INTO pets (shelter_id from token, ...)
    D-->>F: new pet_id
    F-->>Shelter: {pet_id}
    Note over Shelter: redirected to My Pets page

    Shelter->>F: POST /api/pets/<id>/upload-image (multipart file) + JWT
    F->>D: SELECT shelter_id FROM pets WHERE pet_id=?
    D-->>F: shelter_id
    F->>F: confirm pet belongs to this shelter (ownership check)
    F->>Disk: save file to /app/uploads/
    F->>D: UPDATE pets SET image_filename=?
    F-->>Shelter: {message: "Image uploaded"}
```

---

## 6. Request Flow — Adoption Request Lifecycle

```mermaid
stateDiagram-v2
    [*] --> Available
    Available --> Pending: user submits adoption request
    Pending --> Adopted: shelter approves
    Pending --> Available: shelter rejects or user cancels
```

A pet's `status` and its adoption request's `status` are always changed together in the same backend function — never independently — so they can't drift out of sync.

---

## 7. Security Model Summary

| Boundary | Enforced by |
|---|---|
| Must be logged in | `token_required` decorator checks a valid JWT on every protected route |
| Must be the right role (user vs shelter) | Each route checks `payload["role"]` after decoding the token |
| Must own the resource (a pet, a request) | The route fetches the resource's owner from the database and compares it to the token's identity before allowing edit/delete |
| Passwords | Hashed with Werkzeug's `generate_password_hash` — never stored or compared in plain text |
| File uploads | Extension whitelist (`png/jpg/jpeg/gif`) + `secure_filename()` to block path-traversal filenames |

For the two real ownership bugs found and fixed during development (any shelter could edit another shelter's pet), see [PROJECT_LOG.md](PROJECT_LOG.md), Step 13b.
