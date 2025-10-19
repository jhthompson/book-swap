# Show this help message
default:
    just --list --unsorted

# Run the development server
run:
    uv run manage.py runserver

# Make migrations
makemigrations:
    uv run manage.py makemigrations

# Migrate the database
migrate:
    uv run manage.py migrate

# Recreate the database and admin account
reset-for-local-development:
    psql -U postgres -d postgres -c "DROP DATABASE IF EXISTS bookswap;"
    psql -U postgres -d postgres -c "DROP ROLE IF EXISTS bookswap;"
    psql -U postgres -d postgres -c "CREATE ROLE bookswap WITH LOGIN PASSWORD 'bookswap';"
    psql -U postgres -d postgres -c "CREATE DATABASE bookswap WITH OWNER bookswap;"
    psql -U postgres -d bookswap -c "GRANT ALL PRIVILEGES ON DATABASE bookswap TO bookswap;"
    psql -U postgres -d bookswap -c "CREATE EXTENSION postgis;"
    uv run manage.py migrate
    DJANGO_SUPERUSER_PASSWORD=test uv run manage.py createsuperuser --no-input --username=admin --email=admin@test.com
    uv run manage.py create_user_profile admin --city="Ottawa" --latitude=45.4215 --longitude=-75.6972
    uv run manage.py verify_user_email admin
