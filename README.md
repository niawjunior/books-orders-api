# Books Orders API

1. **Configure environment**
```bash
cp .env.example .env
```

2. **Start services**
```bash
docker-compose up --build -d
```

3. **Run migrations**
```bash
docker-compose exec api uv run alembic upgrade head
```

### Local Development

1. **Set up Python environment**
```bash
python -m venv .venv
source .venv/bin/activate
uv sync
```

2. **Set up database**
```bash
docker-compose up -d db

# Run migrations
uv run alembic upgrade head

# Create new migration
uv run alembic revision --autogenerate -m "description"
```

3. **Run the API**
```bash
uv run fastapi dev
```


## API Endpoints

### Authors
- `POST /api/v1/authors` - Create author
- `GET /api/v1/authors` - List authors

### Books
- `POST /api/v1/books` - Create book
- `GET /api/v1/books` - List books with filters:
  - `author_id` - Filter by author
  - `q` - Search query
  - `sort` - Sort by title or published_at
  - `limit` / `offset` - Pagination

### Orders
- `POST /api/v1/orders` - Create draft order
- `POST /api/v1/orders/{id}/confirm` - Confirm order (with idempotency)

### Tenants
- `POST /api/v1/tenants/{tenant}/bootstrap` - Create tenant schema


### Environment Variables

**Database:**
```env
POSTGRES_USER=postgres
POSTGRES_PASSWORD=postgres
POSTGRES_DB=books_orders_db
POSTGRES_PORT=5432
```

**Application:**
```env
PROJECT_NAME=Books Orders API
API_V1_STR=/api/v1
API_PORT=8000
LOG_LEVEL=INFO
```

## Testing
<img width="1440" height="748" alt="image" src="https://github.com/user-attachments/assets/bbe8724e-ad66-4a47-9899-88865810f7e3" />


### Run all tests
```bash
# With Docker
docker-compose exec api uv run pytest --cov=app --cov-report=term-missing

# Locally
uv run pytest --cov=app --cov-report=html --cov-report=term-missing -v tests/

# Database Migration Commands
```bash
# Create new migration
docker-compose exec api uv run alembic revision --autogenerate -m "migration description"

# Apply migrations
docker-compose exec api uv run alembic upgrade head

# Downgrade migrations
docker-compose exec api uv run alembic downgrade -1

# View migration history
docker-compose exec api uv run alembic history
```

### Using Docker Compose Production

1. **Configure production environment**
```bash
cp .env.prod.example .env.prod
```

2. **Deploy**
```bash
docker-compose -f docker-compose.prod.yml up -d
```

3. **Run migrations**
```bash
docker-compose -f docker-compose.prod.yml exec api uv run alembic upgrade head
```

## API Examples

### Bootstrap a tenant
```bash
curl -X POST http://localhost:8000/api/v1/tenants/acme/bootstrap \
  -H "Content-Type: application/json"
```

### Create an author
```bash
curl -X POST http://localhost:8000/api/v1/authors \
  -H "Content-Type: application/json" \
  -H "X-Tenant: acme" \
  -d '{"name": "Pasupol", "email": "pasupol@example.com"}'
```

### Create a book
```bash
curl -X POST http://localhost:8000/api/v1/books \
  -H "Content-Type: application/json" \
  -H "X-Tenant: acme" \
  -d '{
    "title": "Harry Potter and the Philosopher'\''s Stone",
    "author_id": "author-uuid-here",
    "price": 19.99,
    "stock": 100,
    "published_at": "1997-06-26"
  }'
```

### Create and confirm an order
```bash
# Create order
curl -X POST http://localhost:8000/api/v1/orders \
  -H "Content-Type: application/json" \
  -H "X-Tenant: acme" \
  -d '{
    "items": [
      {"product_id": "book-uuid-here", "qty": 2}
    ]
  }'

# Confirm order with idempotency
curl -X POST http://localhost:8000/api/v1/orders/{order-id}/confirm \
  -H "X-Tenant: acme" \
  -H "Idempotency-Key: unique-confirmation-key"
```
