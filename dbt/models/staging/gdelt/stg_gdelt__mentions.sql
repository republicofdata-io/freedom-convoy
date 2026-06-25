with source as (
    select * from {{ ref('raw_gdelt__mentions') }}
)

select
    cast(global_event_id as bigint) as global_event_id,
    cast(event_time_utc_ts as timestamp) as event_time_utc_ts,
    cast(mention_time_utc_ts as timestamp) as mention_time_utc_ts,
    cast(event_date as date) as event_date,
    cast(mention_type as integer) as mention_type,
    lower(cast(mention_source_name as varchar)) as mention_source_name,
    cast(mention_identifier as varchar) as mention_identifier,
    regexp_extract(cast(mention_identifier as varchar), '^https?://([^/]+)', 1) as mention_domain,
    cast(sentence_id as integer) as sentence_id,
    cast(confidence as integer) as confidence,
    cast(mention_doc_len as integer) as mention_doc_len,
    cast(mention_doc_tone as double) as mention_doc_tone,
    exists (
        select 1
        from {{ ref('movement_boundary') }} boundary
        where regexp_matches(
            lower(coalesce(mention_source_name, '') || ' ' || coalesce(mention_identifier, '')),
            lower(boundary.pattern)
        )
    ) as matches_convoy_boundary
from source
