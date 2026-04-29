# Newlightemara Field Operations Management System

A production-ready Django/PostgreSQL rebuild of the Streamlit field-operations system for **Newlightemara**.

## Stack choice

**Django 5.2 LTS + PostgreSQL** was chosen because this product is CRUD-heavy, permission-heavy, and database-first. Django gives robust server-side sessions, CSRF protection, migrations, template rendering, form handling, and a simple deployment path while still preserving the exact PostgreSQL tables requested. This rebuild intentionally does **not** use Django's default auth tables; it uses the provided `system_users` table and SHA-256 hashes to match the original requirements.

PDFs are generated with ReportLab to avoid browser/runtime dependencies in production containers.

## Implemented modules

- Login with Newlightemara logo and server-side session cookie
- Roles: Admin, Technician, Client
- Role-aware dark sidebar navigation
- Dashboard KPIs, site performance, spend breakdown, recent activity
- Smart Estimator with historical cost-per-point, margin quote formula, PDF quote export
- Client Portfolios with add/edit/delete/complete and payment collection
- Timesheets with automatic `days × TJM` cost calculation and edit/delete
- Payroll filters, summaries, detailed logs, edit/delete
- Efficiency Matrix pivots and daily line chart
- Procurement expenses, phase spend bars, edit/delete
- Milestones with four editable phase sliders and SVG gauge
- Site Photos with multi-upload, base64 storage, filters, notes edit/delete
- Warehouse inventory CRUD, low-stock alerts, check-in/check-out, inventory log edit/delete, stock protection
- Invoicing with printable invoice card, PDF export, labour/material/payment tabs, payment edit/delete
- Dispatch message generator for WhatsApp/SMS and worker overview cards
- Settings: manage system users, worker rates, role references, and passwords
- Client VIP Portal: read-only project, progress, recent activity, photos

## Business logic

- Labour cost = `days × TJM`
- Total cost = `labour + materials`
- Profit = `advance/collected - total cost`
- Margin % = `(advance - total cost) / advance`
- Estimator:
  - `cost_per_point = total_historical_cost / total_historical_points`
  - `base_cost = points × cost_per_point`
  - `quote = base_cost / (1 - margin%)`
- Payment cannot exceed outstanding balance
- Inventory check-out cannot exceed current stock
- Client and worker renames cascade across string-reference tables
- Deleting clients removes related site data to avoid orphan operational records
- Payment edit/delete adjusts `clients.advance`
- Inventory log edit/delete reverses and reapplies stock movements

## Database schema

The migration creates the requested PostgreSQL tables:

- `workers` (`id`, `name`, `tjm`, `specialty`)
- `clients` (`id`, `client_name`, `work_type`, `budget`, `advance`, `total_points`, `status` default `active`)
- `labor_logs` (`id`, `date`, `client_name`, `worker_name`, `days`, `cost`, `phase`)
- `expenses` (`id`, `date`, `client_name`, `item`, `amount`, `phase`, `supplier`)
- `progress` (`client_name`, `phase1`, `phase2`, `phase3`, `phase4`)
- `site_photos` (`id`, `upload_date`, `client_name`, `phase`, `photo_data`, `notes`)
- `inventory` (`id`, `item_name`, `category`, `quantity`, `unit`)
- `inventory_logs` (`id`, `date`, `item_name`, `change_amount`, `direction`, `site_allocated`, `notes`)
- `system_users` (`username`, `password_hash`, `role`, `reference`)
- `payments` (`id`, `date`, `client_name`, `amount`, `method`, `notes`)

Seeded admin user:

- Username: `admin`
- Password: `Admin2026!`

## Local setup without Docker

```bash
python -m venv .venv
source .venv/bin/activate  # Windows: .venv\Scripts\activate
pip install -r requirements.txt
cp .env.example .env
# edit .env and point DATABASE_URL to your PostgreSQL database
python manage.py migrate
python manage.py seed_demo_data --noinput  # optional demo data
python manage.py runserver
```

Open: `http://127.0.0.1:8000`

## Docker setup

```bash
cp .env.example .env
# for local docker, make sure .env uses DATABASE_URL=postgres://newlightemara:newlightemara@db:5432/newlightemara
docker compose up --build
```

Open: `http://127.0.0.1:8000`

## Production notes

1. Set a strong `SECRET_KEY`.
2. Set `DEBUG=False`.
3. Set `ALLOWED_HOSTS` and `CSRF_TRUSTED_ORIGINS` for your real domain.
4. Set `SESSION_COOKIE_SECURE=True` and `CSRF_COOKIE_SECURE=True` behind HTTPS.
5. Run `python manage.py migrate` during deploy.
6. Run `python manage.py collectstatic --noinput` during build.
7. Put the app behind HTTPS and a reverse proxy such as Nginx, Caddy, Traefik, or a platform load balancer.
8. Rotate the seeded admin password immediately after first login.

## Role references

- For a `Technician` user, set `system_users.reference` to the exact `workers.name`.
- For a `Client` user, set `system_users.reference` to the exact `clients.client_name`.

## Security model

- Session data is stored in a signed, HTTP-only Django session cookie backed by the configured session engine.
- All mutating views are POST-only and CSRF-protected.
- Admin-only pages use server-side role checks.
- Technician access is limited to Timesheets and Site Photos. Technician labour edit/delete is limited to logs matching their `reference` worker name.
- Client VIP Portal is read-only and filtered to the client referenced by the user account.
