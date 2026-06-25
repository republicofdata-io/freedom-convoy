-- Convoy-candidate GKG documents for one daily partition.
-- Boundary = web-news documents whose entity/theme/url text matches the convoy
-- regex token built from config/gdelt_candidate.yaml.
with src as (
  select
    GKGRECORDID as gkg_record_id,
    DocumentIdentifier as document_url,
    SourceCommonName as source_common_name,
    SourceCollectionIdentifier as source_collection_id,
    cast(`DATE` as string) as gkg_date_raw,
    parse_timestamp('%Y%m%d%H%M%S', cast(`DATE` as string)) as published_utc_ts,
    Themes as themes,
    V2Themes as v2_themes,
    Persons as persons,
    Organizations as organizations,
    AllNames as all_names,
    Locations as locations,
    V2Tone as v2_tone
  from `gdelt-bq.gdeltv2.gkg_partitioned`
  where _PARTITIONTIME = timestamp('__PARTITION_DATE__')
    and SourceCollectionIdentifier = __SOURCE_COLLECTION_ID__
),
matched as (
  select *
  from src
  where regexp_contains(
    lower(concat(
      ifnull(persons, ''), ' ; ', ifnull(organizations, ''), ' ; ',
      ifnull(all_names, ''), ' ; ', ifnull(themes, ''), ' ; ', ifnull(document_url, '')
    )),
    r'__CONVOY_REGEX__'
  )
)
select
  gkg_record_id,
  document_url,
  source_common_name,
  published_utc_ts,
  gkg_date_raw,
  themes,
  v2_themes,
  persons,
  organizations,
  all_names,
  locations,
  (
    select loc
    from unnest(split(locations, ';')) as loc
    order by case substr(loc, 1, 1)
      when '3' then 1 when '4' then 2 when '2' then 3 when '5' then 4 when '1' then 5 else 6
    end
    limit 1
  ) as primary_location,
  v2_tone,
  date('__PARTITION_DATE__') as event_date
from matched
