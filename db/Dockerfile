# PostgreSQL server for the Neural Support Help Desk.
# Build:  docker build -t helpdesk-postgres ./db
# Run:    docker compose up -d db     (see docker-compose.yml)
FROM postgres:17.2-alpine

# Application database and owner. The password is supplied at run time
# (POSTGRES_PASSWORD), never baked into the image.
ENV POSTGRES_DB=helpdesk \
    POSTGRES_USER=helpdesk \
    TZ=UTC

# Runs once, when the data volume is first initialised.
COPY init/ /docker-entrypoint-initdb.d/

HEALTHCHECK --interval=5s --timeout=3s --start-period=10s --retries=10 \
    CMD pg_isready -U "$POSTGRES_USER" -d "$POSTGRES_DB" || exit 1

EXPOSE 5432
