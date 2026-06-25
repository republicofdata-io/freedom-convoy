with source as (
    select * from {{ ref('raw_gdelt__gkg') }}
)

select
    cast(gkg_record_id as varchar) as gkg_record_id,
    cast(document_url as varchar) as document_url,
    regexp_extract(cast(document_url as varchar), '^https?://([^/]+)', 1) as document_domain,
    lower(cast(source_common_name as varchar)) as source_common_name,
    cast(published_utc_ts as timestamp) as published_utc_ts,
    cast(event_date as date) as event_date,
    cast(gkg_date_raw as varchar) as gkg_date_raw,
    cast(themes as varchar) as themes_raw,
    cast(v2_themes as varchar) as v2_themes_raw,
    cast(persons as varchar) as persons_raw,
    cast(organizations as varchar) as organizations_raw,
    cast(all_names as varchar) as all_names_raw,
    cast(locations as varchar) as locations_raw,
    cast(primary_location as varchar) as primary_location_raw,
    cast(v2_tone as varchar) as v2_tone_raw,
    try_cast(split_part(cast(v2_tone as varchar), ',', 1) as double) as tone,
    exists (
        select 1
        from {{ ref('movement_boundary') }} boundary
        where regexp_matches(
            lower(coalesce(themes, '') || ' ' || coalesce(v2_themes, '') || ' ' || coalesce(all_names, '') || ' ' || coalesce(document_url, '')),
            lower(boundary.pattern)
        )
    ) as matches_convoy_boundary
from source
