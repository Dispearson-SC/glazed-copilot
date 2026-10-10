-- Runs once on first start of the glazed-db container (superuser: postgres).
-- Agent-Core creates and migrates its own database; only the backend's role/db are made here.
CREATE ROLE glazed_app LOGIN PASSWORD 'glazed_dev';
CREATE DATABASE glazed_app OWNER glazed_app;
\connect glazed_app
CREATE SCHEMA IF NOT EXISTS glazed AUTHORIZATION glazed_app;
ALTER ROLE glazed_app SET search_path = glazed, public;
