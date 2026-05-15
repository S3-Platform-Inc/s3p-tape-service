-- DB-2 stub: NOTIFY tape-service when a score is inserted so the
-- worker can remove the scorer's matching tape entry from Redis.
-- Owned upstream by s3p-database (user-managed migration); materialised
-- here so the dev compose DB exercises the worker's LISTEN path.
--
-- Tape-service primary path: POST /score → score.save() → app-side
-- tape_store.remove(user_id, document_id). This trigger is the safety
-- net for scores inserted by other paths (e.g., the telegram bot)
-- so their tape entries also get cleaned up.

create or replace function score._notify_tape_inserted()
    returns trigger language plpgsql as
$$
begin
    perform pg_notify(
        'tape_score_inserted',
        json_build_object(
            'user_id',     NEW.user_id,
            'document_id', NEW.document_id
        )::text
    );
    return NEW;
end;
$$;

drop trigger if exists score_notify_tape on score.score;
create trigger score_notify_tape
    after insert on score.score
    for each row execute function score._notify_tape_inserted();
