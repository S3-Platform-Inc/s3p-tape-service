create sequence tasks.sessions_n_session_id_seq
    as integer;

create table if not exists nodes.node
(
    id     serial
        constraint node_pkey
            primary key,
    name   text not null,
    ip     text,
    config json
);

create table if not exists nodes.sessions
(
    id     serial
        constraint sessions_pkey
            primary key,
    start  timestamp with time zone not null,
    stop   timestamp with time zone,
    alive  timestamp with time zone,
    nodeid serial
        constraint sessions_nodeid_fkey
            references nodes.node
);

create table if not exists plugins.plugin
(
    id         serial
        constraint plugin_pkey
            primary key,
    repository text    not null,
    active     boolean not null,
    loaded     timestamp with time zone,
    config     json
);

create table if not exists tasks.status
(
    code integer not null
        constraint status_pkey
            primary key,
    name text    not null
        constraint status_pk
            unique
);

create table if not exists tasks.errors
(
    id       serial
        constraint errors_pkey
            primary key,
    datetime timestamp with time zone not null,
    comment  text                     not null,
    taskid   serial
);

create table if not exists tasks.schedule
(
    id     serial
        constraint schedule_pkey
            primary key,
    start  timestamp with time zone not null,
    taskid serial
);

create table if not exists ml.model
(
    id     serial
        constraint model_pkey
            primary key,
    name   text,
    config json
);

create table if not exists sources.source
(
    id      serial
        constraint source_pkey
            primary key,
    name    text not null
        constraint source_name_pk
            unique,
    sphere  text,
    created timestamp with time zone
);

create index if not exists idx_source_sphere_trgm
    on sources.source using gin (sphere public.gin_trgm_ops);

create table if not exists documents.document
(
    id          serial
        constraint document_pkey
            primary key,
    sourceid    serial
        constraint document_sourceid_fkey
            references sources.source,
    title       text                     not null,
    weblink     text                     not null,
    published   timestamp with time zone not null,
    abstract    text,
    text        text,
    storagelink text,
    loaded      timestamp with time zone,
    otherdata   json
);

create index if not exists document_sourceid_index
    on documents.document (sourceid);

create index if not exists document_published_index
    on documents.document (published);

create index if not exists document_sourceid_published_index
    on documents.document (sourceid asc, published desc);

create table if not exists ml.plugin
(
    modelid serial
        constraint plugin_modelid_fkey
            references ml.model,
    constraint plugin_pkey
        primary key (id)
)
    inherits (plugins.plugin);

create table if not exists sources.plugin
(
    sourceid serial
        constraint plugin_sourceid_fkey
            references sources.source,
    constraint plugin_pkey
        primary key (id)
)
    inherits (plugins.plugin);

create table if not exists tasks.task
(
    id       serial
        constraint task_pkey
            primary key,
    status   integer not null
        constraint task_status_fkey
            references tasks.status,
    pluginid integer not null
        constraint task_pluginid_key
            unique
);

create table if not exists tasks.sessions
(
    id           serial
        constraint sessions_pkey
            primary key,
    start        timestamp with time zone not null,
    stop         timestamp with time zone,
    taskid       serial
        constraint sessions_task_id_fk
            references tasks.task,
    n_session_id integer default nextval('tasks.sessions_n_session_id_seq'::regclass)
        constraint sessions_n_session_id_fkey
            references nodes.sessions
);

alter sequence tasks.sessions_n_session_id_seq owned by tasks.sessions.n_session_id;

create table if not exists ml.score
(
    id         serial
        constraint score_pkey
            primary key,
    score      json                     not null,
    date       timestamp with time zone not null,
    config     json,
    documentid serial
        constraint score_documentid_fkey
            references documents.document,
    pluginid   serial
        constraint score_pluginid_fkey
            references ml.plugin
);

create table if not exists analytics.offload
(
    id     serial
        constraint offload_pkey
            primary key,
    date   timestamp with time zone not null,
    params json
);

create table if not exists analytics.offloaded_documents
(
    document integer not null
        constraint offloaded_documents_pkey
            primary key
        constraint offloaded_documents_document_fkey
            references documents.document,
    offload  integer
        constraint offloaded_documents_offload_fkey
            references analytics.offload
);

create table if not exists users.role
(
    id   serial
        constraint role_pkey
            primary key,
    name text not null
);

create table if not exists users.role_source
(
    role   integer not null
        constraint role_source_role_fkey
            references users.role,
    source integer not null
        constraint role_source_source_fkey
            references sources.source,
    constraint role_source_role_source_key
        unique (role, source)
);

create table if not exists users."user"
(
    id        serial
        constraint user_pkey
            primary key,
    name      text not null,
    privilege json,
    auth      json
);

create table if not exists users.user_role
(
    user_id integer not null
        constraint user_role_user_id_fkey
            references users."user",
    role    integer not null
        constraint user_role_role_fkey
            references users.role,
    constraint user_role_user_id_role_key
        unique (user_id, role)
);

create table if not exists score.score
(
    id          serial
        constraint score_pkey
            primary key,
    score       json,
    comment     text,
    document_id integer
        constraint score_document_id_fkey
            references documents.document,
    user_id     integer
        constraint score_user_id_fkey
            references users."user",
    role_id     integer
        constraint score_role_id_fkey
            references users.role,
    date        timestamp with time zone,
    constraint score_pk
        unique (user_id, role_id, document_id)
);

create index if not exists score_document_id_index
    on score.score using hash (document_id);

create index if not exists score_user_id_document_id_index
    on score.score (user_id, document_id);

create table if not exists analytics.digest
(
    id      serial
        constraint digest_pk
            primary key,
    date    timestamp with time zone not null,
    comment text
);

comment on table analytics.digest is 'for digests';

create table if not exists analytics.digest_documents
(
    digest   integer not null,
    document integer not null,
    constraint digest_documents_pk
        unique (digest, document)
);

create table if not exists documents.embeddings
(
    id          serial
        constraint embeddings_pkey
            primary key,
    document_id integer      not null
        constraint embeddings_document_id_fkey
            references documents.document
            on delete cascade,
    chunk_index integer      not null,
    embedding   vector(1536) not null,
    chunk_text  text,
    created_at  timestamp with time zone default now(),
    part        text,
    constraint embeddings_document_id_chunk_index_key
        unique (document_id, chunk_index)
);

create index if not exists idx_embeddings_doc_chunk
    on documents.embeddings (document_id, chunk_index);

create materialized view if not exists control.experts_score_view as
SELECT sr.document_id,
       d.sourceid,
       d.title,
       d.weblink,
       d.published,
       d.abstract,
       d.loaded,
       d.otherdata,
       (SELECT s1.score ->> 'score'::text
        FROM score.score s1
        WHERE s1.user_id = 4
          AND s1.document_id = sr.document_id
        LIMIT 1) AS user_1_score,
       (SELECT s1.score ->> 'comment'::text
        FROM score.score s1
        WHERE s1.user_id = 4
          AND s1.document_id = sr.document_id
        LIMIT 1) AS user_1_comment,
       (SELECT s1.score ->> 'score'::text
        FROM score.score s1
        WHERE s1.user_id = 5
          AND s1.document_id = sr.document_id
        LIMIT 1) AS user_2_score,
       (SELECT s1.score ->> 'comment'::text
        FROM score.score s1
        WHERE s1.user_id = 5
          AND s1.document_id = sr.document_id
        LIMIT 1) AS user_2_comment,
       (SELECT s1.score ->> 'score'::text
        FROM score.score s1
        WHERE s1.user_id = 6
          AND s1.document_id = sr.document_id
        LIMIT 1) AS user_3_score,
       (SELECT s1.score ->> 'comment'::text
        FROM score.score s1
        WHERE s1.user_id = 6
          AND s1.document_id = sr.document_id
        LIMIT 1) AS user_3_comment
FROM score.score sr
         JOIN documents.document d ON sr.document_id = d.id
GROUP BY sr.document_id, d.id;

create materialized view if not exists control.experts_score_view_with_date as
SELECT sr.document_id,
       d.sourceid,
       d.title,
       d.weblink,
       d.published,
       d.abstract,
       d.loaded,
       d.otherdata,
       (SELECT s1.score ->> 'score'::text
        FROM score.score s1
        WHERE s1.user_id = 4
          AND s1.document_id = sr.document_id
        LIMIT 1) AS user_1_score,
       (SELECT s1.score ->> 'comment'::text
        FROM score.score s1
        WHERE s1.user_id = 4
          AND s1.document_id = sr.document_id
        LIMIT 1) AS user_1_comment,
       (SELECT s1.date
        FROM score.score s1
        WHERE s1.user_id = 4
          AND s1.document_id = sr.document_id
        LIMIT 1) AS user_1_date,
       (SELECT s1.score ->> 'score'::text
        FROM score.score s1
        WHERE s1.user_id = 5
          AND s1.document_id = sr.document_id
        LIMIT 1) AS user_2_score,
       (SELECT s1.score ->> 'comment'::text
        FROM score.score s1
        WHERE s1.user_id = 5
          AND s1.document_id = sr.document_id
        LIMIT 1) AS user_2_comment,
       (SELECT s1.date
        FROM score.score s1
        WHERE s1.user_id = 5
          AND s1.document_id = sr.document_id
        LIMIT 1) AS user_2_date,
       (SELECT s1.score ->> 'score'::text
        FROM score.score s1
        WHERE s1.user_id = 6
          AND s1.document_id = sr.document_id
        LIMIT 1) AS user_3_score,
       (SELECT s1.score ->> 'comment'::text
        FROM score.score s1
        WHERE s1.user_id = 6
          AND s1.document_id = sr.document_id
        LIMIT 1) AS user_3_comment,
       (SELECT s1.date
        FROM score.score s1
        WHERE s1.user_id = 6
          AND s1.document_id = sr.document_id
        LIMIT 1) AS user_3_date
FROM score.score sr
         JOIN documents.document d ON sr.document_id = d.id
GROUP BY sr.document_id, d.id;

create or replace view plugins.complete(tid, status, pid, repository, loaded, config, type, refid, refname) as
SELECT task.id AS tid,
       task.status,
       pl.id   AS pid,
       pl.repository,
       pl.loaded,
       pl.config,
       pl.type,
       pl.refid,
       pl.refname
FROM tasks.task
         JOIN (SELECT plugin.id,
                      plugin.repository,
                      plugin.loaded,
                      plugin.config,
                      'SOURCE'::text                      AS type,
                      plugin.sourceid                     AS refid,
                      (SELECT source.name
                       FROM sources.source
                       WHERE source.id = plugin.sourceid) AS refname
               FROM sources.plugin
               UNION ALL
               SELECT plugin.id,
                      plugin.repository,
                      plugin.loaded,
                      plugin.config,
                      'ML'::text                        AS type,
                      plugin.modelid                    AS refid,
                      (SELECT model.name
                       FROM ml.model
                       WHERE model.id = plugin.modelid) AS refname
               FROM ml.plugin) pl ON task.pluginid = pl.id;

comment on view plugins.complete is 'Выбирает задачи и добавляет к ним данные о плагине и связанным с ним объектом (источник, модель, pipeline)';

create or replace view control.plugins_status
            (pl_id, pl_active, src_id, src_name, pl_rep, status_name, docs, percent, next_start) as
WITH plugin_data AS (SELECT pl.id    AS plid,
                            pl.active,
                            ss.id    AS ssid,
                            ss.name,
                            pl.repository,
                            pl.config,
                            st.name  AS status_name,
                            ts.start AS next_start
                     FROM tasks.task t
                              JOIN tasks.status st ON t.status = st.code
                              LEFT JOIN tasks.schedule ts ON t.id = ts.taskid
                              JOIN sources.plugin pl ON t.pluginid = pl.id
                              JOIN sources.source ss ON ss.id = pl.sourceid),
     document_counts AS (SELECT d.sourceid,
                                count(d.id)   AS doc_count,
                                count(sse.id) AS score_count
                         FROM documents.document d
                                  LEFT JOIN score.score sse ON sse.document_id = d.id
                         GROUP BY d.sourceid)
SELECT pls.plid                                                                                  AS pl_id,
       pls.active                                                                                AS pl_active,
       pls.ssid                                                                                  AS src_id,
       pls.name                                                                                  AS src_name,
       'https://github.com/'::text || pls.repository                                             AS pl_rep,
       pls.status_name,
       COALESCE(dc.doc_count, 0::bigint)                                                         AS docs,
       COALESCE(dc.score_count::numeric / NULLIF(dc.doc_count::numeric, 0::numeric), 0::numeric) AS percent,
       pls.next_start
FROM plugin_data pls
         LEFT JOIN document_counts dc ON pls.ssid = dc.sourceid;

create or replace view score.parsed_score(id, document_id, user_id, role_id, date, numeric, sourceid) as
SELECT ps.id,
       ps.document_id,
       ps.user_id,
       ps.role_id,
       ps.date,
       ps."numeric",
       dd.sourceid
FROM (SELECT score.id,
             score.document_id,
             score.user_id,
             score.role_id,
             score.date,
             (score.score ->> 'score'::text)::numeric AS "numeric"
      FROM score.score) ps
         JOIN (SELECT document.id,
                      document.sourceid
               FROM documents.document) dd ON ps.document_id = dd.id;

create or replace view control.view_experts_score_with_datetime
            (document_id, sourceid, title, weblink, published, abstract, loaded, otherdata, user_1_score,
             user_1_comment, user_1_date, user_2_score, user_2_comment, user_2_date, user_3_score, user_3_comment,
             user_3_date)
as
SELECT sr.document_id,
       d.sourceid,
       d.title,
       d.weblink,
       d.published,
       d.abstract,
       d.loaded,
       d.otherdata,
       (SELECT s1.score ->> 'score'::text
        FROM score.score s1
        WHERE s1.user_id = 4
          AND s1.document_id = sr.document_id
        LIMIT 1) AS user_1_score,
       (SELECT s1.score ->> 'comment'::text
        FROM score.score s1
        WHERE s1.user_id = 4
          AND s1.document_id = sr.document_id
        LIMIT 1) AS user_1_comment,
       (SELECT s1.date
        FROM score.score s1
        WHERE s1.user_id = 4
          AND s1.document_id = sr.document_id
        LIMIT 1) AS user_1_date,
       (SELECT s1.score ->> 'score'::text
        FROM score.score s1
        WHERE s1.user_id = 5
          AND s1.document_id = sr.document_id
        LIMIT 1) AS user_2_score,
       (SELECT s1.score ->> 'comment'::text
        FROM score.score s1
        WHERE s1.user_id = 5
          AND s1.document_id = sr.document_id
        LIMIT 1) AS user_2_comment,
       (SELECT s1.date
        FROM score.score s1
        WHERE s1.user_id = 5
          AND s1.document_id = sr.document_id
        LIMIT 1) AS user_2_date,
       (SELECT s1.score ->> 'score'::text
        FROM score.score s1
        WHERE s1.user_id = 6
          AND s1.document_id = sr.document_id
        LIMIT 1) AS user_3_score,
       (SELECT s1.score ->> 'comment'::text
        FROM score.score s1
        WHERE s1.user_id = 6
          AND s1.document_id = sr.document_id
        LIMIT 1) AS user_3_comment,
       (SELECT s1.date
        FROM score.score s1
        WHERE s1.user_id = 6
          AND s1.document_id = sr.document_id
        LIMIT 1) AS user_3_date
FROM score.score sr
         JOIN documents.document d ON sr.document_id = d.id
GROUP BY sr.document_id, d.id;

create or replace view control.view_experts_score_with_src_name_datetime
            (doc_id, src_id, src_name, title, weblink, published, abstract, loaded, otherdata, user_1_score,
             user_1_comment, user_1_date, user_2_score, user_2_comment, user_2_date, user_3_score, user_3_comment,
             user_3_date)
as
SELECT d.id      AS doc_id,
       s.id      AS src_id,
       s.name    AS src_name,
       d.title,
       d.weblink,
       d.published,
       d.abstract,
       d.loaded,
       d.otherdata,
       (SELECT s1.score ->> 'score'::text
        FROM score.score s1
        WHERE s1.user_id = 4
          AND s1.document_id = sr.document_id
        LIMIT 1) AS user_1_score,
       (SELECT s1.score ->> 'comment'::text
        FROM score.score s1
        WHERE s1.user_id = 4
          AND s1.document_id = sr.document_id
        LIMIT 1) AS user_1_comment,
       (SELECT s1.date
        FROM score.score s1
        WHERE s1.user_id = 4
          AND s1.document_id = sr.document_id
        LIMIT 1) AS user_1_date,
       (SELECT s1.score ->> 'score'::text
        FROM score.score s1
        WHERE s1.user_id = 5
          AND s1.document_id = sr.document_id
        LIMIT 1) AS user_2_score,
       (SELECT s1.score ->> 'comment'::text
        FROM score.score s1
        WHERE s1.user_id = 5
          AND s1.document_id = sr.document_id
        LIMIT 1) AS user_2_comment,
       (SELECT s1.date
        FROM score.score s1
        WHERE s1.user_id = 5
          AND s1.document_id = sr.document_id
        LIMIT 1) AS user_2_date,
       (SELECT s1.score ->> 'score'::text
        FROM score.score s1
        WHERE s1.user_id = 6
          AND s1.document_id = sr.document_id
        LIMIT 1) AS user_3_score,
       (SELECT s1.score ->> 'comment'::text
        FROM score.score s1
        WHERE s1.user_id = 6
          AND s1.document_id = sr.document_id
        LIMIT 1) AS user_3_comment,
       (SELECT s1.date
        FROM score.score s1
        WHERE s1.user_id = 6
          AND s1.document_id = sr.document_id
        LIMIT 1) AS user_3_date
FROM score.score sr
         JOIN documents.document d ON sr.document_id = d.id
         JOIN sources.source s ON d.sourceid = s.id
GROUP BY sr.document_id, d.id, s.id;

create or replace view control.scheduled_plugin_tasks
            (pl_id, pl_active, repository, src_name, task_id, status_code, status_name, schedule_id, next_start) as
WITH plugins AS (SELECT pl.id     AS pl_id,
                        s.id      AS src_id,
                        s.name    AS src_name,
                        pl.repository,
                        pl.active AS pl_active
                 FROM sources.plugin pl
                          JOIN sources.source s ON pl.sourceid = s.id),
     tasks AS (SELECT tt.id       AS task_id,
                      tt.pluginid AS pl_id,
                      ts.code     AS status_code,
                      ts.name     AS status_name
               FROM tasks.task tt
                        JOIN tasks.status ts ON tt.status = ts.code),
     plugin_tasks AS (SELECT p.pl_id,
                             p.pl_active,
                             p.repository,
                             p.src_name,
                             t.task_id,
                             t.status_code,
                             t.status_name
                      FROM plugins p
                               JOIN tasks t ON p.pl_id = t.pl_id),
     scheduled_plugin_tasks AS (SELECT pt.pl_id,
                                       pt.pl_active,
                                       pt.repository,
                                       pt.src_name,
                                       pt.task_id,
                                       pt.status_code,
                                       pt.status_name,
                                       ts.id    AS schedule_id,
                                       ts.start AS next_start
                                FROM plugin_tasks pt
                                         LEFT JOIN tasks.schedule ts ON ts.taskid = pt.task_id)
SELECT scheduled_plugin_tasks.pl_id,
       scheduled_plugin_tasks.pl_active,
       scheduled_plugin_tasks.repository,
       scheduled_plugin_tasks.src_name,
       scheduled_plugin_tasks.task_id,
       scheduled_plugin_tasks.status_code,
       scheduled_plugin_tasks.status_name,
       scheduled_plugin_tasks.schedule_id,
       scheduled_plugin_tasks.next_start
FROM scheduled_plugin_tasks;

create or replace view control.scored_documents
            (doc_id, src_id, src_name, title, weblink, published, abstract, loaded, otherdata, user_1_score,
             user_1_comment, user_1_date, user_2_score, user_2_comment, user_2_date, user_3_score, user_3_comment,
             user_3_date, text)
as
SELECT cv.doc_id,
       cv.src_id,
       cv.src_name,
       cv.title,
       cv.weblink,
       cv.published,
       cv.abstract,
       cv.loaded,
       cv.otherdata,
       cv.user_1_score,
       cv.user_1_comment,
       cv.user_1_date,
       cv.user_2_score,
       cv.user_2_comment,
       cv.user_2_date,
       cv.user_3_score,
       cv.user_3_comment,
       cv.user_3_date,
       d.text
FROM control.view_experts_score_with_src_name_datetime cv
         LEFT JOIN documents.document d ON d.id = cv.doc_id;

create or replace function nodes.active_sessions()
    returns TABLE(session_id integer, node_id integer, alive timestamp with time zone)
    language plpgsql
as
$$
begin
    RETURN QUERY SELECT ns.id, ns.nodeid, ns.alive as alive
                 FROM nodes.sessions ns
                 WHERE (ns.alive is NOT NULL AND ns.stop IS NULL AND ns.start < NOW());
end;
$$;

comment on function nodes.active_sessions() is 'Возвращает таблицу со всеми активными сессиями всех узлов';

create or replace function nodes.active_session(nodeid integer) returns integer
    language plpgsql
as
$$
    declare sid integer;
begin

    select session_id into sid from nodes.active_sessions() where node_id = nodeid ORDER BY alive DESC LIMIT 1;
    RETURN sid;
end;
$$;

comment on function nodes.active_session(integer) is 'Возвращает id активной сессии узла по его id (передаваемый параметр)';

create or replace function nodes.alive(__id integer) returns integer
    language plpgsql
as
$$
    declare
        sid integer;
begin
    select nodes.active_session(__id) into sid;
    if (sid IS NULL)
    THEN
        insert into nodes.sessions(start, nodeid, alive)
        VALUES (now(), __id, now());
    end if;

    UPDATE nodes.sessions SET alive = now() WHERE id = sid;

    return sid;
end;
$$;

comment on function nodes.alive(integer) is 'Функция, которую вызывает узел SPP для обновления статуса "я жив"';

create or replace function nodes.observe_node_session() returns integer
    language plpgsql
as
$$
    declare
        dead_sessions integer;
begin

    SELECT COUNT(*) into dead_sessions FROM nodes.active_sessions() n, LATERAL nodes.kill_session(n.session_id) sid WHERE AGE(now(), alive) > '3 secs'::interval;

--     SELECT sid FROM nodes.active_sessions() n, LATERAL nodes.kill_session(n.session_id) sid WHERE AGE(now(), alive) > interval '3 secs';

    return dead_sessions;
end;
$$;

comment on function nodes.observe_node_session() is 'Просматривает все активные сессии и проверяет, чтобы дата последнего обновления статуса "я жив" узла SPP был не больше N секунд. Если находятся сессии, чей статус не обновился, то для этой сессии вызывается функция nodes.kill_session(id integer)';

create or replace function nodes.kill_session(__id integer) returns integer
    language plpgsql
as
$$
begin
    UPDATE nodes.sessions SET alive = NULL, stop = now() WHERE id = __id;
    return __id;
end;
$$;

comment on function nodes.kill_session(integer) is 'Фукнция для уничтожения активной сессии узла SPP';

create or replace function tasks.add_task(__pluginid integer, iscreateschedule boolean) returns integer
    language plpgsql
as
$$
    declare
        tid integer;
begin
    INSERT INTO tasks.task (status, pluginid) values (0, __pluginID) RETURNING id into tid;

    IF isCreateSchedule is true THEN
        perform tasks.schedule(tid, null);
    end if;

    return tid;
end
$$;

create or replace function plugins.on_addition_plugin() returns trigger
    language plpgsql
as
$$
begin

    if not EXISTS(select *
                  FROM tasks.task t
                  WHERE t.pluginid = new.id)
    THEN
--         Добавлен плагин, задача для которого не была создана
        perform tasks.add_task(new.id, new.active);
    end if;

--     perform public.observe_plugins();

    return new;
end
$$;

create trigger plugin_insert_observer
    after insert
    on plugins.plugin
execute procedure plugins.on_addition_plugin();

create trigger ml_plugin_insert_observer
    after insert
    on ml.plugin
    for each row
execute procedure plugins.on_addition_plugin();

create trigger s_plugin_insert_observer
    after insert
    on sources.plugin
    for each row
execute procedure plugins.on_addition_plugin();

create or replace function plugins.plugin_update_active() returns trigger
    language plpgsql
as
$$
    declare tid integer;
begin

    select id into tid from tasks.task where pluginid = new."id";

    if (new.active is true) then
        perform tasks.schedule(tid, now());
    else
        perform * from tasks.schedule sch, lateral tasks.unschedule(sch.id, 80) where sch.taskid = tid;
    end if;

    return new;
end
$$;

create trigger plugin_update_observer
    after update
        of active
    on plugins.plugin
    for each row
execute procedure plugins.plugin_update_active();

create trigger s_plugin_update_observer
    after update
        of active
    on ml.plugin
    for each row
execute procedure plugins.plugin_update_active();

create trigger s_plugin_update_observer
    after update
        of active
    on sources.plugin
    for each row
execute procedure plugins.plugin_update_active();

create or replace function tasks.check_add_task() returns trigger
    language plpgsql
as
$$
    declare pluginIdExists boolean;
begin
    select (pl.id is not null) from plugins.plugin pl where pl.id = new.pluginid into pluginIdExists;
    if (pluginIdExists) then
        return NEW;
    else
        raise exception 'Nonexistent ID --> %', new.pluginid;
        return null;
    end if;
end
$$;

create trigger pluginid_add_task_check
    before insert or update
    on tasks.task
    for each row
execute procedure tasks.check_add_task();

create or replace function tasks.schedule(taskid integer, start timestamp with time zone) returns integer
    language plpgsql
as
$$
    declare schID integer;
begin

    if (start is null) then
--         Если время запуска не указана, то выбрать текущее время
        start := now();
    end if;
    if (start < now()) then
        raise exception 'Start time --> % in the past', start;
    end if;

    insert into tasks.schedule (start, taskid) values (start, schedule.taskID) returning schedule.id into schID;
    UPDATE tasks.task t set status = 10 where t.id = taskID;

    return schID;
end
$$;

create or replace function tasks.unschedule(scheduleid integer, _status integer) returns integer
    language plpgsql
as
$$
begin

    if (_status is not null) then
--         Изменение статуса при необходимости
        perform tasks.set_status((select taskid from tasks.schedule where id = scheduleID), _status);
    end if;

--     Удаление записи из таблицы расписания
    delete from tasks.schedule where id = scheduleID;

    return scheduleID;
end
$$;

create or replace function tasks.set_status(taskid integer, _status integer) returns integer
    language plpgsql
as
$$
begin

    UPDATE tasks.task set status = _status where id = taskID;
    return taskID;
end
$$;

create or replace function nodes.plugin_types(nodeid integer)
    returns TABLE(type text)
    language plpgsql
as
$$
begin
    return query select value as type from json_array_elements_text((select config -> 'plugins' -> 'types' from nodes.node where id = nodeID));
end
$$;

create or replace function nodes.init(__name text, __ip text, __config json) returns integer
    language plpgsql
as
$$
    declare
        __id integer;
begin
    if not EXISTS(select *
                  FROM nodes.node
                  WHERE name = __name)
    THEN

        insert into nodes.node (name, ip, config)
        VALUES (__name, __ip, __config);

        RETURN currval('nodes.node_id_seq');
    else
        select id into __id
                  FROM nodes.node
                  WHERE name = __name;
        return __id;
    end if;
end;
$$;

create or replace function tasks.broke(nodeid integer, sessionid integer, comment text) returns integer
    language plpgsql
as
$$
    declare _tid integer;
begin
    UPDATE tasks.sessions set stop = now() where id = broke.sessionID;
    UPDATE tasks.task set status = 60 where id = (select taskid from tasks.sessions where id = broke.sessionID) returning id into _tid;

    insert into tasks.errors (datetime, comment, taskid) values (now(), broke.comment, _tid);
    return _tid;
end
$$;

create or replace function plugins.timer(id integer) returns interval
    language plpgsql
as
$$
    declare int interval;
begin
    select (config -> 'task' -> 'trigger' ->> 'interval')::interval into int from plugins.plugin where plugin.id = timer.id limit 1;
    return int;
end
$$;

create or replace function tasks.finish(nodeid integer, sessionid integer) returns integer
    language plpgsql
as
$$
    declare _tid integer; _pid integer;
begin
    UPDATE tasks.sessions set stop = now() where id = finish.sessionID; -- // Завершение текущей сессии
    UPDATE tasks.task set status = 50
                      where id = (select taskid from tasks.sessions where id = finish.sessionID)
                      returning id into _tid; -- // Обновление статуса задача на 'finished'
    select pc.pid into _pid from plugins.complete pc where pc.tid = _tid;

    if (select * from plugins.timer(_pid)) is not null then
        perform tasks.schedule(_tid, now() + (select * from plugins.timer(_pid))); -- // Добавление нового расписания
    end if;

    return _tid;

end
$$;

create or replace function tasks.relevant(nodeid integer)
    returns TABLE(sessionid integer, taskid integer, taskstatus integer, pluginid integer, repository text, loaded timestamp with time zone, config json, type text, referenceid integer, referencename text)
    language plpgsql
as
$$
    declare
        _tid integer; _schid integer; _tsession integer; _pluginId integer;
begin
--         Эта функция должна выбрать одну задачу, основываясь на таблице расписания. Удалить выбранную запись расписания, собрать данные о задаче и об плагине этой задачи и вернуть их в форме таблицы.
    LOCK TABLE tasks.schedule;

--     Выбираются такие задачи, для которых плагин имеет тип, который поддерживает узел. При этом на полученные задачи должно иметься расписание. Затем выбирается одна старая запланированная задача.
    select sch.id, pl.tid, pl.pid into _schid, _tid, _pluginId from plugins.complete pl
        left join tasks.schedule sch on sch.taskid = pl.tid
             where
                 pl.type in (select * from nodes.plugin_types(nodeID))
                 and sch.id is not null
                 and sch.start < now()
             order by sch.start
             limit 1;

--     select schedule.id, schedule.taskid into schid, tid from tasks.schedule where tasks.schedule.start < now() order by schedule.start limit 1;
    if (_schid is null) then
--         Если не было получена запись расписания, значит нет задач для запуска
        return;
    end if;

    perform tasks.set_status(_tid, 20); -- // Задача перешла в режим "получена" (<given> status)
    perform tasks.unschedule(_schid, null); -- // удаление записи расписания

    insert into tasks.sessions (start, stop, taskid, n_session_id)
        values (
                now(),
                null,
                _tid,
                null
        )
        returning id into _tsession; -- // Создание сессии задачи и получение id новой сессии
    return query select _tsession as sessionid, * from plugins.complete where complete.tid = _tid; -- // полные данные о задаче с ID сессии этой задачи
end
$$;

create or replace function documents.equals(lhid integer, lhtitle text, lhweblink text, lhpubdate timestamp with time zone, lhsource integer, rhid integer, rhtitle text, rhweblink text, rhpubdate timestamp with time zone, rhsource integer) returns boolean
    language plpgsql
as
$$

begin

    --     1. Сначала проверяем совпадают ли у документов источники
--     Если источники документов не равны, то ДОКУМЕНТЫ НЕ РАВНЫ
    IF (lhSource <> rhSource) THEN
        RETURN FALSE;
    end if;

--      2. Проверяем есть ли у документов поле ID. Если у какого-нибудь документа поля ID нет, то проверять соответствие будем по 3 уникальным полям, который должны быть.
    IF (lhID IS NULL) OR (rhID IS NULL) THEN
        RETURN (lhTitle = rhTitle) AND (lhWebLink = rhWebLink) AND (lhPubDate = rhPubDate);
    end if;

--      3. Если у двух документов есть ID, то сравнение происходит по ним
    IF (lhID IS NOT NULL) AND (rhID IS NOT NULL) THEN
        RETURN lhID = rhID;
    end if;

    RETURN FALSE;
end;
$$;

create or replace function documents.save(sourceid integer, newtitle text, newabstract text, newtext text, newweblink text, newlocallink text, newotherdata json, newpubdate timestamp with time zone, newloaddate timestamp with time zone) returns integer
    language plpgsql
as
$$
declare
    docID INTEGER;

begin

    select id into docID FROM documents.document d
             WHERE d.sourceid = save.sourceID
               AND d.title = save.newTitle
               AND d.weblink = save.newWeblink
               AND d.published = save.newPubDate;

    if (docID is null) then
        insert into documents.document (sourceid, title, weblink, published, abstract, text, storagelink, loaded, otherdata)
        VALUES (save.sourceID, newTitle, newWeblink, newPubDate, newAbstract, newText, newLocalLink, newLoadDate, newOtherData) returning id into docID;
    else
        update documents.document d set
                                      abstract = newAbstract,
                                      text = newText,
                                      storagelink = newLocalLink,
                                      loaded = newLoadDate,
                                      otherdata = newOtherData
        where d.id = docID;

    end if;

    return docID;
end;
$$;

create or replace function documents."all"(_sourceid integer)
    returns TABLE(id integer, sourceid integer, title text, weblink text, published timestamp with time zone, abstract text, text text, storagelink text, loaded timestamp with time zone, otherdata json)
    language plpgsql
as
$$
begin
--     Фукнция для получения всех документов.
--          Если источник указан, то выбираются все документы этого источника
--          Если источник не указан, то выдаются все документы
    return query select * from documents.document d
                          where (_sourceID is NULL) or (_sourceID = d.sourceid);
end
$$;

create or replace function documents.littles(_sourceid integer)
    returns TABLE(id integer, sourceid integer, title text, weblink text, published timestamp with time zone)
    language plpgsql
as
$$
begin
--     Функция возвращает все документы (как в функции documents."all"), но обрезает, чтобы уменьшить размер получаемого пакета
--          такая функция используется там, где нужно сравнить документы (например, в модуле фильтрации платформы)
    return query select "all".id, "all".sourceid, "all".title, "all".weblink, "all".published from documents.all(_sourceid);
end
$$;

create or replace function analytics.offload_document(offloadid integer, documentid integer) returns integer
    language plpgsql
as
$$
    declare __id integer;
begin
--         Добавление новой выгрузки
    insert into analytics.offloaded_documents (document, offload) VALUES (documentID, offloadID) returning document into __id;
    return 1;
end
$$;

create or replace function analytics.export(export_id integer)
    returns TABLE(id integer, title text, weblink text, published timestamp with time zone, abstract text, text text, storagelink text, loaded timestamp with time zone, otherdata json, source_id integer, source_name text)
    language plpgsql
as
$$
    declare offid integer;
begin
--         Добавление новой выгрузки
    if (export_id is NULL) then
        if exists(select * from documents.document d where d.id not in (select document from analytics.offloaded_documents)) then
            insert into analytics.offload (date) VALUES (now()) returning offload.id into offid;
            return query select d.id, d.title, d.weblink, d.published, d.abstract, d.text, d.storagelink, d.loaded, d.otherdata, s.id, s.name
                     from documents.document d join sources.source s on d.sourceid = s.id,
                         lateral analytics.offload_document(offid, d.id)
                     where d.id not in (select document from analytics.offloaded_documents);
        end if;
    else
        return query select d.id, d.title, d.weblink, d.published, d.abstract, d.text, d.storagelink, d.loaded, d.otherdata, s.id, s.name
                         from analytics.offloaded_documents offdoc left join documents.document d on offdoc.document = d.id join sources.source s on s.id = d.sourceid
                         where offdoc.offload = export_id;
    end if;
end
$$;

create or replace function analytics.export_lists()
    returns TABLE(id integer, date timestamp with time zone, count bigint)
    language plpgsql
as
$$
begin
    return query select o.id, o.date, count(*) from analytics.offload o left join analytics.offloaded_documents od on o.id = od.offload
                 group by o.id order by o.id;
end
$$;

create or replace function control.plugins_observe()
    returns TABLE(id integer, name text, repository text, active boolean, status_code integer, status text, docs bigint, errors bigint)
    language plpgsql
as
$$
begin
    return query select sp.id as id,s.name, sp.repository, sp.active, ts.code as status_code, ts.name as status, count(d.id) as docs, count(te.id) as errors
        from (((sources.plugin sp join sources.source s on sp.sourceid = s.id)
            join tasks.task t on sp.id = t.pluginid)
            left join tasks.status ts on ts.code = t.status
            left join tasks.errors te on te.taskid = t.id)
            left join documents.document d on d.sourceid = sp.sourceid
        group by sp.id, s.id, t.id, ts.code order by sp.id;
end
$$;

create or replace function users.roleinfo(_id integer)
    returns TABLE(id integer, name text, src_id integer, src_name text, src_sphere text)
    language plpgsql
as
$$
begin
    return query select r.id, r.name, s.id, s.name, s.sphere
                 from users.role r join users.role_source rs on r.id = rs.role
                     join sources.source s on rs.source = s.id
                 where r.id = _id;
end
$$;

create or replace function score.save(_uid integer, telegram_id integer, _did integer, _rid integer, _score json, _comment text) returns integer
    language plpgsql
as
$$
    declare sid integer;
begin

    insert into score.score (score, comment, document_id, user_id, role_id, date)
        values (_score, _comment, _did, _uid, _rid, now()) returning id into sid;
    return sid;
end
$$;

create or replace function users.sources(_id integer) returns integer[]
    language plpgsql
as
$$
    declare srcs integer[];
begin
--         Array всех источников, доступных для пользователя (user ID)
    select ARRAY(
    select distinct rs.source
    from (users.user u join users.user_role ur on u.id = ur.user_id)
        join users.role_source rs on ur.role = rs.role
    where u.id = _id
    order by rs.source
       ) into srcs;
    return srcs;
end
$$;

create or replace function users.roles(_id integer) returns integer[]
    language plpgsql
as
$$
    declare roles integer[];
begin
--         Array всех ролей, доступных для пользователя (user ID)
    select ARRAY(
    select distinct ur.role
    from (users.user u join users.user_role ur on u.id = ur.user_id)
    where u.id = _id
    order by ur.role
       ) into roles;
    return roles;
end
$$;

create or replace function score.documents(_uid integer)
    returns TABLE(id integer, sourceid integer, title text, weblink text, published timestamp with time zone, abstract text, text text, storagelink text, loaded timestamp with time zone, otherdata json)
    language plpgsql
as
$$
begin
    return query
        SELECT
            d.id,
            d.sourceid,
            d.title,
            d.weblink,
            d.published,
            d.abstract,
            d.text,
            d.storagelink,
            d.loaded,
            d.otherdata
        FROM documents.document d
        WHERE
          -- 1. Index-Friendly Date Filter
          -- Replaces: dc.published::date > date '2025.12.01'
            d.published >= (now() - interval '4 month')

          -- 2. User's Sources Filter
          and d.sourceid = ANY(users.sources(_uid))

          -- 3. Efficient Anti-Join (Scored Check)
          -- Replaces: LEFT JOIN user_scores ... WHERE score_id IS NULL
          AND NOT EXISTS (
            SELECT 1
            FROM score.score s
            WHERE s.user_id = _uid
              AND s.document_id = d.id
        );

--     return query
--     with
--         user_docs (id, sourceid, title, weblink, published, abstract, text, storagelink, loaded, otherdata) as (
--             SELECT od.*
--             FROM documents.document od
--             WHERE od.sourceid = ANY(users.sources(_uid))
--         ),
--         user_scores (score_id, document_id) as (
--             SELECT ss.id, ss.document_id
--             FROM score.score ss
--             WHERE user_id = _uid
--         ),
--         document_to_score (id, sourceid, title, weblink, published, abstract, text, storagelink, loaded, otherdata) as (
--             SELECT d.*
-- --             SELECT d.id, d.sourceid, d.title, d.weblink, d.published, d.abstract, d.text, d.storagelink, d.loaded, d.otherdata
--             FROM user_docs d
--             LEFT JOIN user_scores s ON s.document_id = d.id
--             WHERE s.score_id IS NULL
--         )
--     select dc.*
--     from document_to_score dc
--     where dc.published::date > date '2025.12.01';
end
$$;

create or replace function score.stats(_uid integer)
    returns TABLE(srcid integer, srcname text, documents bigint)
    language plpgsql
as
$$
begin
--     Возвращает количество документов для каждого источника, которые были оценены пользователем (user ID)
    return query select src.id, src.name, count(d.id)
        from documents.document d
            left join sources.source src on d.sourceid = src.id
            join score.score s on d.id = s.document_id
        where s.user_id = _uid
        group by src.id;
end
$$;

create or replace function score.document(_uid integer, srcid integer)
    returns TABLE(id integer, title text, weblink text, published timestamp with time zone, abstract text, storagelink text, loaded timestamp with time zone, otherdata json, src_id integer, src_name text, src_sphere text)
    language plpgsql
as
$$
begin
    return query
        select od.id, od.title, od.weblink, od.published, od.abstract, od.storagelink, od.loaded, od.otherdata, src.id, src.name, src.sphere
        from (select d.* from score.documents(_uid) d
        where (
            (srcid is null) or ((srcid is not null) and (d.sourceid = srcid))
            ) and d.published >= (now() - interval '4 month') -- TODO: Временное ограничение на отбор материалов за последний месяц
        order by d.published
              limit 1) od
        join sources.source src on od.sourceid = src.id;
end
$$;

create or replace function score.roles(_uid integer)
    returns TABLE(id integer, name text)
    language plpgsql
as
$$
begin
    return query
        select r.id, r.name
        from users.role r
        where r.id = ANY(users.roles(_uid));
end
$$;

create or replace function users.roles(_uid integer, _sid integer)
    returns TABLE(id integer, name text)
    language plpgsql
as
$$
    declare roles integer[];
begin
--         Array всех ролей, доступных для источника (source ID) для пользователя (user ID)
    return query select distinct r.id, r.name
    from users.role_source rs join users.role r on rs.role = r.id
    where rs.role = ANY(users.roles(_uid)) and rs.source = _sid;
end
$$;

create or replace function sources."create"(_name text, _sphere text, _roles integer[]) returns integer
    language plpgsql
as
$$
    declare sid integer; _role integer;
begin
    insert into sources.source (name, sphere, created)
        values (_name, _sphere, now()) returning id into sid;

    foreach _role in array _roles loop
        insert into users.role_source (role, source) VALUES (_role, sid);
    end loop;
    return sid;
end
$$;

create or replace function users.auth(_id bigint, _token text)
    returns TABLE(id integer, name text, privilege json, role_id integer, role_name text)
    language plpgsql
as
$$
    declare uid integer;
begin
    select u.id into uid from users.user u where (u.auth#>>'{telegram}')::bigint = _id;

    if uid is not null
    THEN
        return query select u.id, u.name, u.privilege, r.id, r.name
                     from users.user u join users.user_role ur on u.id = ur.user_id
                         join users.role r on ur.role = r.id
                     where u.id = uid;
    end if;
end
$$;

create or replace function analytics.digests()
    returns TABLE(id integer, date timestamp with time zone, comment text)
    language plpgsql
as
$$
begin
    return query select *
                 from analytics.digest;
end
$$;

create or replace function analytics.selection(_role integer)
    returns TABLE(document integer, sids integer[], users integer[], scores json[])
    language plpgsql
as
$$
begin
    return query select ss.document_id, array_agg(ss.id), array_agg(ss.user_id), array_agg(ss.score)
                 from score.score ss
                     join (select distinct s.document_id
                     from score.score s join users."user" u on u.id = s.user_id
                        left join analytics.digest_documents dd on dd.document = s.document_id
                     where dd.digest is null) sdd on ss.document_id = sdd.document_id
                where ss.role_id = _role
                group by ss.document_id;
end
$$;

create or replace function documents.without_text(_did integer)
    returns TABLE(id integer, sourceid integer, title text, weblink text, published timestamp with time zone, abstract text, storagelink text, loaded timestamp with time zone, otherdata json)
    language plpgsql
as
$$
begin
    return query select d.id, d.sourceid, d.title, d.weblink, d.published, d.abstract, d.storagelink, d.loaded, d.otherdata
                 from documents.document d
                 where d.id = _did
                 limit 1;
end
$$;

create or replace function documents.last(_sourcename text)
    returns TABLE(id integer, sourceid integer, title text, weblink text, published timestamp with time zone)
    language plpgsql
as
$$
    declare _sid integer;
begin
--     Функция возвращает последний документ (как в функции documents."all"), но обрезает, чтобы уменьшить размер получаемого пакета
--          такая функция используется там, где нужно сравнить документы (например, в модуле фильтрации платформы)

    select id into _sid from sources.source where name = _sourcename;
    return query select d.id, d.sourceid, d.title, d.weblink, d.published
                 from documents.document d
                 where d.sourceid = _sid
                 order by d.published desc
                 limit 1;
end
$$;

create or replace function documents.last(_sourceid integer)
    returns TABLE(id integer, sourceid integer, title text, weblink text, published timestamp with time zone)
    language plpgsql
as
$$
begin
--     Функция возвращает все документы (как в функции documents."all"), но обрезает, чтобы уменьшить размер получаемого пакета
--          такая функция используется там, где нужно сравнить документы (например, в модуле фильтрации платформы)
    return query select d.id, d.sourceid, d.title, d.weblink, d.published
                 from documents.document d
                 where d.sourceid = _sourceid
                 order by d.published desc
                 limit 1;
end
$$;

create or replace function score.info_for(_uid integer)
    returns TABLE(srcid integer, srcname text)
    language plpgsql
as
$$
begin
--     Возвращает количество документов для каждого источника, которые еще не оценивались пользователем (user ID)
    return query select s.id, s.name
        from sources.source s
            join documents.document d on s.id = d.sourceid
        where d.published > (now() - interval '4 month')
            and s.id = ANY(users.sources(_uid))
            and not exists(
                select 1 from score.score sc
                         where sc.user_id = _uid and sc.document_id = d.id
            )
        group by s.id, s.name;
end
$$;

create or replace function tasks.stop(_taskid integer) returns integer
    language plpgsql
as
$$
begin
    if exists(select * from tasks.schedule s where s.taskid = _taskid) then
        --     Удаление записи из таблицы расписания
        delete from tasks.schedule where taskid = _taskid;
    end if;
    select tasks.set_status(_taskid, 0);

    return 1;
end
$$;

create or replace function plugins.update_trigger_interval(p_id integer, p_new_interval text) returns void
    language plpgsql
as
$$
BEGIN
    UPDATE plugins.plugin
    SET config = jsonb_set(
        config::jsonb,
        '{task,trigger,interval}',
        p_new_interval,
        false
    )::json
    WHERE id = p_id;
END;
$$;

create or replace function documents.exists(_sourceid integer, _title text, _weblink text, _published timestamp with time zone) returns boolean
    language plpgsql
as
$$
begin
--     Функция находит документ в таблице documents.document по сложному идентификатору (title, weblink, published)
--     Возвращает значение TRUE или FALSE
    return exists(SELECT *
FROM
    documents.littles(_sourceid) d
WHERE
    d.title = _title
    AND
    d.weblink = _weblink
    AND
    d.published = _published);
end
$$;

create or replace function sources.add_plugin(_src_id integer, _repository text, _active boolean, _config json) returns integer
    language plpgsql
as
$$
    declare _pl_id integer;
begin
    insert into sources.plugin (repository, active, loaded, config, sourceid)
        values (_repository, _active, now(), _config, _src_id) returning id into _pl_id;

    return _pl_id;
end
$$;

create or replace function documents.save_if_exist(_sourceid integer, newtitle text, newabstract text, newtext text, newweblink text, newlocallink text, newotherdata json, newpubdate timestamp with time zone, newloaddate timestamp with time zone) returns integer
    language plpgsql
as
$$
declare
    docID INTEGER;
    _loaded timestamp with time zone;
    _is_exists BOOLEAN;
begin
    -- Check if document already exists
    SELECT documents.exists(_sourceid, newtitle, newweblink, newpubdate) INTO _is_exists;

    -- Determine load date
    _loaded := COALESCE(newloaddate, NOW());

    -- Insert document if it doesn't exist
    IF NOT _is_exists THEN
        INSERT INTO documents.document (
            sourceid,
            title,
            weblink,
            published,
            abstract,
            text,
            storagelink,
            loaded,
            otherdata
        )
        VALUES (
            _sourceid,
            newtitle,
            newweblink,
            newpubdate,
            newabstract,
            newtext,
            newlocallink,
            _loaded,
            newotherdata
        )
        RETURNING id INTO docID;

        RETURN docID;
    END IF;

    return -1;
end;
$$;

create or replace function documents.find_similar(target_doc_id integer, industry text, months_back integer DEFAULT 6, limit_results integer DEFAULT 5)
    returns TABLE(document_id integer, title text, weblink text, published timestamp with time zone, similarity_score double precision)
    language plpgsql
as
$$
BEGIN
    RETURN QUERY
        SELECT
            d.id,
            d.title,
            d.weblink,
            d.published,
            1 - (e.embedding <=> target.embedding) as similarity_score
        FROM documents.embeddings e
                 JOIN documents.document d ON e.document_id = d.id
                 JOIN sources.source s ON d.sourceid = s.id
                 CROSS JOIN documents.embeddings target
        WHERE target.document_id = target_doc_id
          AND s.sphere = industry
          AND d.published >= DATE_TRUNC('month', CURRENT_DATE - INTERVAL '1 month' * months_back)
          AND d.published < (SELECT published FROM documents.document WHERE id = target_doc_id)
          AND e.document_id != target_doc_id
        ORDER BY e.embedding <=> target.embedding
        LIMIT limit_results;
END;
$$;

create or replace function analytics.monthly_scores_stats(target_month date, industry text DEFAULT NULL::text)
    returns TABLE(industry_name text, avg_quality numeric, avg_usefulness numeric, top_rated_documents json, total_evaluations bigint)
    language plpgsql
as
$$
BEGIN
    RETURN QUERY
        WITH industry_scores AS (
            SELECT
                s.sphere,
                d.id,
                d.title,
                AVG((sc.score ->> 'quality')::NUMERIC) as doc_avg_quality,
                AVG((sc.score ->> 'usefulness')::NUMERIC) as doc_avg_usefulness,
                COUNT(sc.comment) as comments_count
            FROM score.score sc
                     JOIN documents.document d ON sc.document_id = d.id
                     JOIN sources.source s ON d.sourceid = s.id
            WHERE DATE_TRUNC('month', sc.date) = DATE_TRUNC('month', target_month)
              AND (industry IS NULL OR s.sphere = industry)
            GROUP BY s.sphere, d.id, d.title
        ),
             ranked_docs AS (
                 SELECT
                     sphere,
                     id,
                     title,
                     doc_avg_quality,
                     doc_avg_usefulness,
                     comments_count,
                     ROW_NUMBER() OVER (PARTITION BY sphere ORDER BY doc_avg_quality DESC) as rank
                 FROM industry_scores
             )
        SELECT
            rd.sphere as industry_name,
            AVG(rd.doc_avg_quality) as avg_quality,
            AVG(rd.doc_avg_usefulness) as avg_usefulness,
            json_agg(
            json_build_object(
                    'document_id', rd.id,
                    'title', rd.title,
                    'avg_score', (rd.doc_avg_quality + rd.doc_avg_usefulness) / 2,
                    'comments_count', rd.comments_count
            ) ORDER BY rd.doc_avg_quality DESC
                    ) FILTER (WHERE rd.rank <= 10) as top_rated_documents,
            COUNT(rd.id) as total_evaluations
        FROM ranked_docs rd
        GROUP BY rd.sphere;
END;
$$;

