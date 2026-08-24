-- Intent cards gain a first-class title: the generator's own one-line summary,
-- required at submission time going forward. Legacy rows are backfilled from
-- the first plan's title (the de-facto title the notification already used),
-- falling back to a bounded prefix of the body for light-style rows whose
-- plans array is empty.
ALTER TABLE intent_cards ADD COLUMN title TEXT;

UPDATE intent_cards SET title = COALESCE(
    json_extract(plans_json, '$[0].title'),
    substr(proactive_view, 1, 120)
) WHERE title IS NULL;
