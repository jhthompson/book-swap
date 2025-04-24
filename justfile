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
