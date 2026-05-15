-- Extensions required by the rest of the init scripts.
-- pg_trgm: used by 02-ddl.sql GIN trigram indexes.
-- pgcrypto: used by 04-auth-by-token.sql and 05-fake-data.sql (digest).
-- vector:   used by 02-ddl.sql similarity columns; needs the
--           pgvector/pgvector:pg16 image (not stock postgres:16-alpine).
create extension if not exists pg_trgm;
create extension if not exists pgcrypto;
create extension if not exists vector;
