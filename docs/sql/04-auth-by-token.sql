-- DB-1 stub: users.auth_by_token(_token text).
-- Materialised here so the dev compose database can authenticate experts
-- against the test data without depending on s3p-database #8/DB-1 landing.
-- The Python service still hashes the raw token with SHA-256 client-side
-- before logging anything; this function performs the same hash so the
-- DB only ever sees the raw token in the volatile function call and
-- only ever stores its hash in users."user".auth->>'token_hash'.

create extension if not exists pgcrypto;

create or replace function users.auth_by_token(_token text)
    returns table (user_id integer, privilege json)
    language plpgsql stable as
$$
declare
    _hash text;
begin
    if _token is null or length(_token) < 8 then
        return;
    end if;
    _hash := encode(digest(_token, 'sha256'), 'hex');
    return query
    select u.id, u.privilege
    from users."user" u
    where u.auth ->> 'token_hash' = _hash;
end;
$$;
