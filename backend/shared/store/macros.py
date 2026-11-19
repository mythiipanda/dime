NAME_KEY_MACRO = (
    "CREATE OR REPLACE TEMP MACRO name_key(s) AS nullif(regexp_replace(regexp_replace("
    "lower(strip_accents(trim(s))), '\\s+(jr|sr|ii|iii|iv|v)\\.?$', ''), '[^a-z]', '', 'g'), '')"
)
