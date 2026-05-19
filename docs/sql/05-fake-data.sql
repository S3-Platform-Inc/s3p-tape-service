-- Fake data for the dev compose DB and integration tests.
-- Idempotent via ON CONFLICT DO NOTHING so re-applies are safe.
--
-- Test tokens (plain text — not secret, dev only):
--   ALPHA   = 'expert-alpha-token-XXXXXXXXXXXXXXXX'   user_id=1, expert
--   BRAVO   = 'expert-bravo-token-YYYYYYYYYYYYYYYY'   user_id=2, expert
--   CHARLIE = 'reader-charlie-token-ZZZZZZZZZZZZZZ'   user_id=3, NOT expert
-- These are public dev-only values; the hash is what lands in the DB.

create extension if not exists pgcrypto;

-- Sources --------------------------------------------------------------
insert into sources.source (id, name, sphere, created) values
    (1, 'Test Source One',   'tech',     now()),
    (2, 'Test Source Two',   'finance',  now()),
    (3, 'Test Source Three', 'science',  now()),
    (4, 'Test Source Four',  'politics', now()),
    (5, 'Test Source Five',  'sports',   now()),
    (6, 'Test Source Six',   'tech',     now())
on conflict (id) do nothing;
select setval(pg_get_serial_sequence('sources.source', 'id'),
              greatest((select max(id) from sources.source), 1));

-- Roles ----------------------------------------------------------------
insert into users.role (id, name) values
    (1, 'ALL'),
    (2, 'FINTECH')
on conflict (id) do nothing;
select setval(pg_get_serial_sequence('users.role', 'id'),
              greatest((select max(id) from users.role), 1));

-- Role <-> Source ------------------------------------------------------
insert into users.role_source (role, source) values
    (1, 1),
    (1, 2),
    (1, 3),
    (1, 4),
    (1, 5),
    (1, 6),
    (2, 2)
on conflict do nothing;

-- Users ---------------------------------------------------------------
-- We compute token_hash inline so the raw token is the source of truth
-- and the inserted hash is guaranteed to match what users.auth_by_token
-- recomputes at lookup time.
insert into users."user" (id, name, privilege, auth) values
    (1, 'Alpha Expert',
        '{"bot": ["expert"]}'::json,
        json_build_object('token_hash',
            encode(digest('expert-alpha-token-XXXXXXXXXXXXXXXX', 'sha256'), 'hex'))),
    (2, 'Bravo Expert',
        '{"expert": true, "roles": ["expert"]}'::json,
        json_build_object('token_hash',
            encode(digest('expert-bravo-token-YYYYYYYYYYYYYYYY', 'sha256'), 'hex'))),
    (3, 'Charlie Reader',
        '{"reader": true, "roles": ["reader"]}'::json,
        json_build_object('token_hash',
            encode(digest('reader-charlie-token-ZZZZZZZZZZZZZZ', 'sha256'), 'hex')))
on conflict (id) do nothing;
select setval(pg_get_serial_sequence('users."user"', 'id'),
              greatest((select max(id) from users."user"), 1));

-- User <-> Role -------------------------------------------------------
insert into users.user_role (user_id, role) values
    (1, 1),
    (2, 1),
    (2, 2),
    (3, 1)
on conflict do nothing;

-- Documents -----------------------------------------------------------
insert into documents.document
    (id, sourceid, title, weblink, published, abstract, text)
values
    (1, 1, 'Test doc 1: source-1 baseline',
        'https://example.test/doc/1', '2026-05-01 10:00+00',
        'Short abstract for doc 1.', 'Body text of doc 1.'),
    (2, 1, 'Test doc 2: source-1 follow-up',
        'https://example.test/doc/2', '2026-05-03 10:00+00',
        'Short abstract for doc 2.', 'Body text of doc 2.'),
    (3, 2, 'Test doc 3: source-2 financial brief',
        'https://example.test/doc/3', '2026-05-05 10:00+00',
        'Short abstract for doc 3.', 'Body text of doc 3.'),
    (4, 2, 'Test doc 4: source-2 macro update',
        'https://example.test/doc/4', '2026-05-08 10:00+00',
        'Short abstract for doc 4.', 'Body text of doc 4.'),
    (5, 1, 'Test doc 5: source-1 retrospective',
        'https://example.test/doc/5', '2026-05-10 10:00+00',
        'Short abstract for doc 5.', 'Body text of doc 5.'),
    (6, 3, 'Test doc 6: source-3 science primer',
        'https://example.test/doc/6', '2026-05-11 09:00+00',
        'Short abstract for doc 6.', 'Body text of doc 6.'),
    (7, 3, 'Test doc 7: source-3 lab notes',
        'https://example.test/doc/7', '2026-05-12 09:00+00',
        'Short abstract for doc 7.', 'Body text of doc 7.'),
    (8, 4, 'Test doc 8: source-4 policy digest',
        'https://example.test/doc/8', '2026-05-12 14:00+00',
        'Short abstract for doc 8.', 'Body text of doc 8.'),
    (9, 4, 'Test doc 9: source-4 election recap',
        'https://example.test/doc/9', '2026-05-13 14:00+00',
        'Short abstract for doc 9.', 'Body text of doc 9.'),
    (10, 5, 'Test doc 10: source-5 match report',
        'https://example.test/doc/10', '2026-05-13 20:00+00',
        'Short abstract for doc 10.', 'Body text of doc 10.'),
    (11, 5, 'Test doc 11: source-5 transfer rumor',
        'https://example.test/doc/11', '2026-05-14 20:00+00',
        'Short abstract for doc 11.', 'Body text of doc 11.'),
    (12, 6, 'Test doc 12: source-6 product launch',
        'https://example.test/doc/12', '2026-05-14 08:00+00',
        'Short abstract for doc 12.', 'Body text of doc 12.'),
    (13, 6, 'Test doc 13: source-6 engineering deep-dive',
        'https://example.test/doc/13', '2026-05-15 08:00+00',
        'Short abstract for doc 13.', 'Body text of doc 13.'),
    (14, 2, 'Test doc 14: source-2 earnings preview',
        'https://example.test/doc/14', '2026-05-15 16:00+00',
        'Short abstract for doc 14.', 'Body text of doc 14.'),
    (15, 1, 'Test doc 15: source-1 incident postmortem',
        'https://example.test/doc/15', '2026-05-16 10:00+00',
        'Short abstract for doc 15.', 'Body text of doc 15.')
on conflict (id) do nothing;
select setval(pg_get_serial_sequence('documents.document', 'id'),
              greatest((select max(id) from documents.document), 1));
