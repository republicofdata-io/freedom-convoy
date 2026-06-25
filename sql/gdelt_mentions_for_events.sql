-- Convoy-candidate GDELT Mentions for one daily partition.
-- Mentions are anchored to convoy-candidate GKG document URLs and deduplicated
-- on (mention_identifier, global_event_id), keeping the highest confidence row.
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
)
select
  GLOBALEVENTID as global_event_id,
  parse_timestamp('%Y%m%d%H%M%S', cast(EventTimeDate as string)) as event_time_utc_ts,
  parse_timestamp('%Y%m%d%H%M%S', cast(MentionTimeDate as string)) as mention_time_utc_ts,
  MentionType as mention_type,
  MentionSourceName as mention_source_name,
  MentionIdentifier as mention_identifier,
  SentenceID as sentence_id,
  Confidence as confidence,
  MentionDocLen as mention_doc_len,
  MentionDocTone as mention_doc_tone,
  date('__PARTITION_DATE__') as event_date
from `gdelt-bq.gdeltv2.eventmentions_partitioned`
where _PARTITIONTIME = timestamp('__PARTITION_DATE__')
  and MentionIdentifier in (select document_url from convoy_urls)
qualify row_number() over (
  partition by MentionIdentifier, GLOBALEVENTID order by Confidence desc
) = 1
