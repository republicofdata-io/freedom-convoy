from pathlib import Path

import duckdb

DB_PATH = Path("data/freedom_convoy.duckdb")
EXPORT_DIR = Path("data/derived/observation_layer")

QUERIES = {
    "weekly_volume": """
        with events as (
            select date_trunc('week', event_date)::date as week_start, count(*) as events
            from main_staging.stg_gdelt__events
            group by 1
        ), mentions as (
            select date_trunc('week', event_date)::date as week_start, count(*) as mentions
            from main_staging.stg_gdelt__mentions
            group by 1
        ), gkg as (
            select date_trunc('week', event_date)::date as week_start, count(*) as gkg_docs
            from main_staging.stg_gdelt__gkg
            group by 1
        )
        select coalesce(e.week_start, m.week_start, g.week_start) as week_start,
               coalesce(events, 0) as events,
               coalesce(mentions, 0) as mentions,
               coalesce(gkg_docs, 0) as gkg_docs
        from events e
        full outer join mentions m using (week_start)
        full outer join gkg g using (week_start)
        order by 1
    """,
    "source_concentration_top25": """
        with sources as (
            select coalesce(nullif(mention_domain, ''), mention_source_name) as source, count(*) as mentions
            from main_staging.stg_gdelt__mentions
            group by 1
        ), ranked as (
            select source, mentions,
                   mentions * 1.0 / sum(mentions) over () as mention_share,
                   sum(mentions) over (order by mentions desc rows between unbounded preceding and current row) * 1.0 / sum(mentions) over () as cumulative_share,
                   row_number() over (order by mentions desc) as source_rank
            from sources
        )
        select * from ranked order by mentions desc limit 25
    """,
    "location_distribution_top30": """
        select coalesce(nullif(action_geo_full_name, ''), 'Unknown') as location,
               action_geo_country_code as country_code,
               count(*) as events,
               sum(num_mentions) as coded_mentions,
               avg(avg_tone) as avg_tone
        from main_staging.stg_gdelt__events
        group by 1, 2
        order by events desc
        limit 30
    """,
    "ottawa_border_weekly": """
        with event_places as (
            select event_date,
                   case
                       when regexp_matches(lower(coalesce(action_geo_full_name, '')), 'ottawa') then 'Ottawa'
                       when regexp_matches(lower(coalesce(action_geo_full_name, '') || ' ' || coalesce(actor1_name, '') || ' ' || coalesce(actor2_name, '') || ' ' || coalesce(source_url, '')), 'coutts|windsor|ambassador|emerson|surrey|pacific highway|border') then 'Border blockade'
                       else 'Other/unclear'
                   end as place_frame,
                   count(*) as events,
                   sum(num_mentions) as coded_mentions
            from main_staging.stg_gdelt__events
            group by 1, 2
        )
        select date_trunc('week', event_date)::date as week_start, place_frame, sum(events) as events, sum(coded_mentions) as coded_mentions
        from event_places
        group by 1, 2
        order by 1, 2
    """,
    "actor_amplification_top30": """
        with actors as (
            select actor1_name as actor, count(*) as event_roles, sum(num_mentions) as coded_mentions from main_staging.stg_gdelt__events where actor1_name is not null group by 1
            union all
            select actor2_name as actor, count(*) as event_roles, sum(num_mentions) as coded_mentions from main_staging.stg_gdelt__events where actor2_name is not null group by 1
        )
        select actor, sum(event_roles) as event_roles, sum(coded_mentions) as coded_mentions,
               sum(coded_mentions) * 1.0 / nullif(sum(event_roles), 0) as mentions_per_event_role
        from actors
        group by 1
        having event_roles >= 3
        order by coded_mentions desc
        limit 30
    """,
    "mention_lead_lag": """
        select date_diff('day', event_time_utc_ts::date, mention_time_utc_ts::date) as mention_lag_days,
               count(*) as mentions,
               avg(confidence) as avg_confidence,
               avg(mention_doc_tone) as avg_tone
        from main_staging.stg_gdelt__mentions
        where event_time_utc_ts is not null and mention_time_utc_ts is not null
        group by 1
        order by 1
    """,
    "quality_flags": """
        select 'events_without_location' as flag, count(*) as records from main_staging.stg_gdelt__events where action_geo_full_name is null or action_geo_full_name = ''
        union all select 'events_without_source_domain', count(*) from main_staging.stg_gdelt__events where source_domain is null or source_domain = ''
        union all select 'mentions_low_confidence_lt_50', count(*) from main_staging.stg_gdelt__mentions where confidence < 50
        union all select 'mentions_without_matching_event_in_extract', count(*) from main_staging.stg_gdelt__mentions m left join main_staging.stg_gdelt__events e using (global_event_id) where e.global_event_id is null
        union all select 'gkg_without_source_common_name', count(*) from main_staging.stg_gdelt__gkg where source_common_name is null or source_common_name = ''
    """,
}


def main() -> None:
    EXPORT_DIR.mkdir(parents=True, exist_ok=True)
    con = duckdb.connect(str(DB_PATH), read_only=True)
    for name, query in QUERIES.items():
        out = EXPORT_DIR / f"{name}.csv"
        con.sql(f"copy ({query}) to '{out}' (header, delimiter ',')")
        print(out)


if __name__ == "__main__":
    main()
