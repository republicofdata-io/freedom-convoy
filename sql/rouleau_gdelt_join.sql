-- Example join: Rouleau Commission ground-truth events vs the GDELT
-- observation layer.
--
-- There is no shared identifier between the two datasets, by design: the
-- commission report names people and places; GDELT encodes CAMEO actor codes
-- and FIPS geography. The join is analytical — date + geography (ADM1)
-- alignment, with the CAMEO actor-type crosswalk as a soft secondary filter.
-- It measures how the media-derived event stream covered each ground-truth
-- day/place, not row-level identity.
--
-- Run inside data/freedom_convoy.duckdb (e.g. `make duckdb-ui`).

with ground_truth as (
  select
    e.event_id,
    coalesce(e.event_date, e.event_start_date) as event_date,
    e.title,
    e.event_type,
    e.movement_phase_id,
    l.name       as location_name,
    l.adm1_code,
    l.latitude,
    l.longitude
  from rouleau.protest_event e
  join rouleau.event_location el on el.event_id = e.event_id
  join rouleau.location l on l.location_id = el.location_id
  where coalesce(e.event_date, e.event_start_date) is not null
    and l.adm1_code is not null
),

gdelt_daily as (
  select
    event_date,
    action_geo_adm1_code as adm1_code,
    count(*)                                    as gdelt_event_count,
    sum(num_articles)                           as gdelt_article_count,
    avg(avg_tone)                               as gdelt_avg_tone,
    count(*) filter (
      where event_root_code = '14'              -- CAMEO 14x: protest events
    )                                           as gdelt_protest_coded_count,
    count(*) filter (
      where 'COP' in (actor1_type1_code, actor2_type1_code)
    )                                           as gdelt_police_actor_count
  from main_staging.stg_gdelt__events
  where matches_convoy_boundary
  group by 1, 2
)

select
  gt.event_date,
  gt.location_name,
  gt.adm1_code,
  gt.title                                      as ground_truth_event,
  gt.event_type,
  gt.movement_phase_id,
  coalesce(g.gdelt_event_count, 0)              as gdelt_event_count,
  coalesce(g.gdelt_article_count, 0)            as gdelt_article_count,
  coalesce(g.gdelt_protest_coded_count, 0)      as gdelt_protest_coded_count,
  coalesce(g.gdelt_police_actor_count, 0)       as gdelt_police_actor_count,
  g.gdelt_avg_tone
from ground_truth gt
left join gdelt_daily g
  on g.event_date = gt.event_date
 and g.adm1_code = gt.adm1_code
order by gt.event_date, gt.location_name, gt.title;
