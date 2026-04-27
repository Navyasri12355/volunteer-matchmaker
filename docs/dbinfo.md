Follow the steps below to set up the database locally.

### 1. Install PostgreSQL

Download and install PostgreSQL (with pgAdmin).

### 2. Create Database

Open pgAdmin → Query Tool and run:

```sql
CREATE DATABASE ngo_platform;
```

### 3. Run Schema

1. Open the `schema.sql` file in this repository
2. Copy all contents
3. Run it inside the `ngo_platform` database

This will create all required tables: NGO, Event, Volunteer, Assignment and Audit

### 4. Configure Environment Variables

Create a `.env` file in the project root:

```env
DATABASE_URL=postgresql://postgres:YOUR_PASSWORD@localhost:5432/ngo_platform
```
Replace `YOUR_PASSWORD` with your PostgreSQL password.
