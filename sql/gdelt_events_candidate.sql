-- Convoy-candidate GDELT Events for one daily partition.
-- Events are anchored to the convoy GKG candidate URL set. Event type and
-- geography are not filtered; those distinctions belong to profiling/staging.
with convoy_urls as (
  select distinct DocumentIdentifier as document_url
  from `gdelt-bq.gdeltv2.gkg_partitioned`
  where _PARTITIONTIME = timestamp('__PARTITION_DATE__')
    and SourceCollectionIdentifier = __SOURCE_COLLECTION_ID__
    and regexp_contains(
      lower(concat(
        ifnull(Persons, ''), ' ; ', ifnull(Organizations, ''), ' ; ',
        ifnull(AllNames, ''), ' ; ', ifnull(Themes, ''), ' ; ', ifnull(DocumentIdentifier, '')
      )),
      r'__CONVOY_REGEX__'
    )
),
events as (
  select
    GLOBALEVENTID as global_event_id,
    SQLDATE as sql_date,
    parse_date('%Y%m%d', cast(SQLDATE as string)) as event_date,
    Actor1Code as actor1_code,
    Actor1Name as actor1_name,
    Actor1CountryCode as actor1_country_code,
    Actor1Type1Code as actor1_type1_code,
    Actor2Code as actor2_code,
    Actor2Name as actor2_name,
    Actor2CountryCode as actor2_country_code,
    Actor2Type1Code as actor2_type1_code,
    IsRootEvent as is_root_event,
    EventCode as event_code,
    EventBaseCode as event_base_code,
    EventRootCode as event_root_code,
    QuadClass as quad_class,
    GoldsteinScale as goldstein_scale,
    NumMentions as num_mentions,
    NumSources as num_sources,
    NumArticles as num_articles,
    AvgTone as avg_tone,
    ActionGeo_Type as action_geo_type,
    ActionGeo_FullName as action_geo_full_name,
    ActionGeo_CountryCode as action_geo_country_code,
    ActionGeo_ADM1Code as action_geo_adm1_code,
    ActionGeo_Lat as action_geo_lat,
    ActionGeo_Long as action_geo_long,
    ActionGeo_FeatureID as action_geo_feature_id,
    parse_timestamp('%Y%m%d%H%M%S', cast(DATEADDED as string)) as date_added_utc_ts,
    SOURCEURL as source_url
  from `gdelt-bq.gdeltv2.events_partitioned`
  where _PARTITIONTIME = timestamp('__PARTITION_DATE__')
)
select e.*
from events e
where e.source_url in (select document_url from convoy_urls)
   or regexp_contains(lower(e.source_url), r'__CONVOY_REGEX__')
