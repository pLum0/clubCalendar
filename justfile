set dotenv-load

man := "docker compose exec web python manage.py"

[private]
ensure-env:
    @test -f .env || (echo "Error: .env file not found. Copy .env_example to .env first." && exit 1)

# Start the stack in detached mode
up: ensure-env
    docker compose up -d

# Stop the stack
down:
    docker compose down

# View logs
logs:
    docker compose logs -f

# Run Django management commands (pass command as argument)
manage *args: ensure-env
    docker compose exec web python manage.py {{ args }}

# Run migrations
migrate: ensure-env
    {{ man }} migrate

# Create migrations
makemigrations: ensure-env
    {{ man }} makemigrations

# Create and apply migrations
makemigrate: makemigrations migrate

# Regenerate German translation messages
makemessages: ensure-env
    {{ man }} makemessages -l de

# Compile translation messages
compilemessages: ensure-env
    {{ man }} compilemessages

# Full i18n workflow: regenerate and compile
i18n: makemessages compilemessages

# Collect static files
collectstatic: ensure-env
    {{ man }} collectstatic --noinput

# Run the test suite
test: ensure-env
    {{ man }} test calendar_app.tests --verbosity=2

# Run a specific test module or class (pass as argument)
test-only module: ensure-env
    {{ man }} test {{ module }} --verbosity=2

# Create a superuser
createsuperuser: ensure-env
    {{ man }} createsuperuser

# Open a Django shell
shell: ensure-env
    docker compose exec web python manage.py shell

# Install/check dependencies
pip-freeze: ensure-env
    docker compose exec web pip freeze

# Build without starting
build: ensure-env
    docker compose build

# Start the stack in detached mode with production override (if docker-compose.prod.yml exists)
up-prod: ensure-env
    @if [ -f docker-compose.prod.yml ]; then docker compose -f docker-compose.yml -f docker-compose.prod.yml up -d; else docker compose up -d; fi

# Lint Python files with ruff
lint-python: ensure-env
    docker compose exec web ruff check .

# Lint HTML templates with djlint
lint-html: ensure-env
    docker compose exec web djlint calendar_app/templates --check

# Lint CSS with stylelint
lint-css: ensure-env
    docker compose exec web /app/node_modules/.bin/stylelint "calendar_app/static/calendar_app/css/style.css"

# Lint JavaScript in HTML templates with ESLint
lint-js: ensure-env
    docker compose exec web /app/node_modules/.bin/eslint "calendar_app/**/*.js"

# Run all linters
lint: lint-python lint-html lint-css lint-js

# Fix Python lint issues
lint-python-fix: ensure-env
    docker compose exec web ruff check --fix .

# Fix HTML lint issues
lint-html-fix: ensure-env
    docker compose exec web djlint calendar_app/templates --reformat

# Fix all auto-fixable lint issues
lint-fix: lint-python-fix lint-html-fix
