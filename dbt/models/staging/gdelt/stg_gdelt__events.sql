with source as (
    select * from {{ ref('raw_gdelt__events') }}
)

select
    cast(global_event_id as bigint) as global_event_id,
    cast(sql_date as integer) as sql_date,
    cast(event_date as date) as event_date,
    cast(date_added_utc_ts as timestamp) as date_added_utc_ts,
    cast(actor1_code as varchar) as actor1_code,
    cast(actor1_name as varchar) as actor1_name,
    cast(actor1_country_code as varchar) as actor1_country_code,
    cast(actor1_type1_code as varchar) as actor1_type1_code,
    cast(actor2_code as varchar) as actor2_code,
    cast(actor2_name as varchar) as actor2_name,
    cast(actor2_country_code as varchar) as actor2_country_code,
    cast(actor2_type1_code as varchar) as actor2_type1_code,
    cast(is_root_event as boolean) as is_root_event,
    cast(event_code as varchar) as event_code,
    cast(event_base_code as varchar) as event_base_code,
    cast(event_root_code as varchar) as event_root_code,
    cast(quad_class as integer) as quad_class,
    cast(goldstein_scale as double) as goldstein_scale,
    cast(num_mentions as integer) as num_mentions,
    cast(num_sources as integer) as num_sources,
    cast(num_articles as integer) as num_articles,
    cast(avg_tone as double) as avg_tone,
    cast(action_geo_type as integer) as action_geo_type,
    cast(action_geo_full_name as varchar) as action_geo_full_name,
    cast(action_geo_country_code as varchar) as action_geo_country_code,
    cast(action_geo_adm1_code as varchar) as action_geo_adm1_code,
    cast(action_geo_lat as double) as action_geo_lat,
    cast(action_geo_long as double) as action_geo_long,
    cast(action_geo_feature_id as varchar) as action_geo_feature_id,
    cast(source_url as varchar) as source_url,
    regexp_extract(cast(source_url as varchar), '^https?://([^/]+)', 1) as source_domain,
    exists (
        select 1
        from {{ ref('movement_boundary') }} boundary
        where regexp_matches(
            lower(coalesce(actor1_name, '') || ' ' || coalesce(actor2_name, '') || ' ' || coalesce(action_geo_full_name, '') || ' ' || coalesce(source_url, '')),
            lower(boundary.pattern)
        )
    ) as matches_convoy_boundary
from source
