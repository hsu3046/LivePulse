BEGIN;

ALTER TABLE public."LivePulse_questions"
    DROP CONSTRAINT IF EXISTS "LivePulse_questions_event_id_position_key";

DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1
          FROM pg_constraint
         WHERE conname = 'LivePulse_questions_event_position_unique'
           AND conrelid = 'public."LivePulse_questions"'::REGCLASS
    ) THEN
        ALTER TABLE public."LivePulse_questions"
            ADD CONSTRAINT "LivePulse_questions_event_position_unique"
            UNIQUE (event_id, position)
            DEFERRABLE INITIALLY DEFERRED;
    END IF;
END
$$;

COMMIT;
