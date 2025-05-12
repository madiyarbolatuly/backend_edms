# Multi-Tenant Knowledge Management System

A secure knowledge management system built with FastAPI and Permit.io

## Technologies

- FastAPI
- PostgreSQL
- Permit.io

## Setup

### 1. Set up Virtual Environment

```bash
# Create virtual environment
python -m venv venv

# Activate virtual environment
# On Windows
venv\Scripts\activate
# On macOS/Linux
source venv/bin/activate
```

### 2. Install Dependencies

```bash
pip install -r requirements.txt
```

### 3. Environment Configuration

Create a `.env` file in the root directory with the following variables:

```env
# Database
DATABASE_URL=postgresql://user:password@localhost:5432/knowledge_db

# JWT Configuration
JWT_SECRET_KEY=your-super-secret-key
JWT_ALGORITHM=HS256
ACCESS_TOKEN_EXPIRE_MINUTES=30
REFRESH_TOKEN_EXPIRE_DAYS=7

# Permit.io
PERMIT_API_KEY=your-permit-api-key
PERMIT_PDP_URL=https://pdp.permit.io

# App Configuration
APP_NAME="Knowledge Management System"
ENV=development
```

### 4. Start the Application

```bash
# From the backend directory
fastapi dev main.py
```

The API will be available at `http://localhost:8000`
