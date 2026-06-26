import marimo

__generated_with = "0.23.10"
app = marimo.App(width="full")


@app.cell
def _():
    from html import escape
    from pathlib import Path

    import duckdb
    import marimo as mo
    import pandas as pd

    DB_PATH = Path("data/freedom_convoy.duckdb")
    EXPORT_DIR = Path("data/derived/observation_layer")
    return DB_PATH, EXPORT_DIR, Path, duckdb, escape, mo, pd


@app.cell
def _(DB_PATH, duckdb):
    con = duckdb.connect(str(DB_PATH), read_only=True)
    return (con,)


@app.cell
def _(con):
    boundary_counts = con.sql("""
        with tagged as (
            select
                action_geo_country_code = 'CA' as is_canada,
                event_root_code in ('14') or event_base_code in ('141', '142', '143', '144', '145') as is_protest
            from main_staging.stg_gdelt__events
        )
        select 'All candidate events' as rule, count(*) as events, 1 as rule_order
        from tagged
        union all
        select 'Canada or protest-coded', count(*), 2
        from tagged
        where is_canada or is_protest
        union all
        select 'Canada and protest-coded', count(*), 3
        from tagged
        where is_canada and is_protest
        order by rule_order
    """).df()

    boundary_buckets = con.sql("""
        with tagged as (
            select
                action_geo_country_code = 'CA' as is_canada,
                event_root_code in ('14') or event_base_code in ('141', '142', '143', '144', '145') as is_protest
            from main_staging.stg_gdelt__events
        )
        select 'Canada + protest-coded' as bucket, count(*) as events, 1 as bucket_order
        from tagged where is_canada and is_protest
        union all
        select 'Canada, not protest-coded', count(*), 2
        from tagged where is_canada and not is_protest
        union all
        select 'Protest-coded, outside Canada', count(*), 3
        from tagged where is_protest and not is_canada
        union all
        select 'Neither Canada nor protest-coded', count(*), 4
        from tagged where not is_canada and not is_protest
        order by bucket_order
    """).df()

    weekly_volume = con.sql("""
        with events as (
            select date_trunc('week', event_date)::date as week_start,
                   count(*) as events,
                   sum(num_articles) as articles
            from main_staging.stg_gdelt__events
            group by 1
        ), mentions as (
            select date_trunc('week', event_date)::date as week_start, count(*) as mentions
            from main_staging.stg_gdelt__mentions
            group by 1
        )
        select coalesce(e.week_start, m.week_start) as week_start,
               coalesce(events, 0) as events,
               coalesce(mentions, 0) as mentions,
               coalesce(articles, 0) as articles,
               coalesce(mentions, 0) * 1.0 / nullif(coalesce(events, 0), 0) as mentions_per_event
        from events e
        full outer join mentions m using (week_start)
        order by 1
    """).df()

    source_concentration = con.sql("""
        with sources as (
            select coalesce(nullif(mention_domain, ''), mention_source_name) as source, count(*) as mentions
            from main_staging.stg_gdelt__mentions
            group by 1
        ), ranked as (
            select source, mentions,
                   mentions * 1.0 / sum(mentions) over () as mention_share,
                   row_number() over (order by mentions desc) as source_rank
            from sources
        )
        select * from ranked order by mentions desc limit 10
    """).df()

    source_metrics = con.sql("""
        with sources as (
            select coalesce(nullif(mention_domain, ''), mention_source_name) as source, count(*) as mentions
            from main_staging.stg_gdelt__mentions
            group by 1
        ), shares as (
            select mentions * 1.0 / sum(mentions) over () as share,
                   row_number() over (order by mentions) as rn,
                   count(*) over () as n,
                   sum(mentions) over () as total_mentions,
                   mentions
            from sources
        )
        select
            count(*) as distinct_sources,
            sum(share * share) as hhi,
            sum(case when rn > n - 10 then mentions else 0 end) * 1.0 / max(total_mentions) as top10_share
        from shares
    """).df().iloc[0].to_dict()

    location_distribution = con.sql("""
        select coalesce(nullif(action_geo_full_name, ''), 'Unknown') as location,
               action_geo_country_code as country_code,
               count(*) as events
        from main_staging.stg_gdelt__events
        group by 1, 2
        order by events desc
        limit 8
    """).df()

    place_lens = con.sql("""
        with event_places as (
            select event_date,
                   case
                       when regexp_matches(lower(coalesce(action_geo_full_name, '')), 'ottawa') then 'Ottawa'
                       when regexp_matches(lower(coalesce(action_geo_full_name, '') || ' ' || coalesce(actor1_name, '') || ' ' || coalesce(actor2_name, '') || ' ' || coalesce(source_url, '')), 'coutts|windsor|ambassador|emerson|surrey|pacific highway|border') then 'border'
                       else 'other'
                   end as place_frame,
                   count(*) as events
            from main_staging.stg_gdelt__events
            group by 1, 2
        )
        select date_trunc('week', event_date)::date as week_start,
               sum(case when place_frame = 'Ottawa' then events else 0 end) as ottawa,
               sum(case when place_frame = 'border' then events else 0 end) as border
        from event_places
        group by 1
        order by 1
    """).df()

    actor_amplification = con.sql("""
        with actors as (
            select coalesce(actor1_name, '(no actor)') as actor, count(*) as event_roles, sum(num_mentions) as coded_mentions
            from main_staging.stg_gdelt__events group by 1
            union all
            select coalesce(actor2_name, '(no actor)') as actor, count(*) as event_roles, sum(num_mentions) as coded_mentions
            from main_staging.stg_gdelt__events group by 1
        )
        select actor, sum(coded_mentions) * 1.0 / nullif(sum(event_roles), 0) as mentions_per_event
        from actors
        group by 1
        having sum(event_roles) >= 10
        order by mentions_per_event desc
        limit 6
    """).df()

    lead_lag = con.sql("""
        select least(greatest(date_diff('hour', event_time_utc_ts, mention_time_utc_ts), 0), 240) as lag_hour,
               count(*) as mentions
        from main_staging.stg_gdelt__mentions
        where event_time_utc_ts is not null and mention_time_utc_ts is not null
        group by 1
        order by 1
    """).df()

    lead_lag_metrics = con.sql("""
        with lags as (
            select date_diff('hour', event_time_utc_ts, mention_time_utc_ts) as lag_hour
            from main_staging.stg_gdelt__mentions
            where event_time_utc_ts is not null and mention_time_utc_ts is not null
        )
        select median(lag_hour) as median_lag_h,
               quantile_cont(lag_hour, 0.9) as p90_lag_h,
               avg(case when lag_hour between 0 and 24 then 1 else 0 end) as within_24h
        from lags
    """).df().iloc[0].to_dict()

    confidence_hist = con.sql("""
        select floor(confidence / 10) * 10 as confidence_bin, count(*) as mentions
        from main_staging.stg_gdelt__mentions
        where confidence is not null
        group by 1
        order by 1
    """).df()

    quality_flags = con.sql("""
        select
            count(*) filter (where action_geo_full_name is null or action_geo_full_name = '') * 1.0 / count(*) as ungeocoded_event_share,
            count(*) filter (where actor1_name is null and actor2_name is null) * 1.0 / count(*) as null_actor_event_share
        from main_staging.stg_gdelt__events
    """).df().iloc[0].to_dict()
    mention_quality = con.sql("""
        select count(*) filter (where confidence < 50) * 1.0 / count(*) as low_conf_mention_share
        from main_staging.stg_gdelt__mentions
    """).df().iloc[0].to_dict()
    quality_flags.update(mention_quality)

    totals = con.sql("""
        select
            (select min(event_date) from main_staging.stg_gdelt__events) as min_date,
            (select max(event_date) from main_staging.stg_gdelt__events) as max_date,
            (select count(*) from main_staging.stg_gdelt__events) as events,
            (select count(*) from main_staging.stg_gdelt__mentions) as mentions
    """).df().iloc[0].to_dict()
    return (
        actor_amplification,
        boundary_buckets,
        boundary_counts,
        confidence_hist,
        lead_lag,
        lead_lag_metrics,
        location_distribution,
        place_lens,
        quality_flags,
        source_concentration,
        source_metrics,
        totals,
        weekly_volume,
    )


@app.cell
def _(escape, pd):
    def fmt_int(x):
        return f"{int(x):,}"

    def fmt_pct(x):
        return f"{float(x) * 100:.1f}%"

    def fmt_h(x):
        return f"{float(x):.0f}h"

    def bars(df, label_col, value_col, color="#3d91e2", value_fmt=fmt_int):
        max_v = max(float(df[value_col].max()), 1)
        rows = []
        for _, row in df.iterrows():
            v = float(row[value_col])
            rows.append(f"""
            <div class='bar-row'>
              <div class='bar-label'>{escape(str(row[label_col]))}</div>
              <div class='bar-track'><div class='bar-fill' style='width:{v / max_v * 100:.1f}%;background:{color}'></div></div>
              <div class='bar-value'>{value_fmt(v)}</div>
            </div>""")
        return "".join(rows)

    def funnel(df):
        max_v = max(float(df['events'].max()), 1)
        rows = []
        for _, row in df.iterrows():
            v = float(row['events'])
            rows.append(f"""
            <div class='funnel-step'>
              <div class='funnel-label'>{escape(str(row['rule']))}</div>
              <div class='funnel-track'><div class='funnel-bar' style='width:{max(v / max_v * 100, 8):.1f}%'></div></div>
              <div class='funnel-value'>{fmt_int(v)}</div>
            </div>""")
        return "".join(rows)

    def bucket_blocks(df):
        total = max(float(df['events'].sum()), 1)
        colors = ['#3d806f', '#5c7284', '#a97324', '#8a8170']
        rows = []
        for i, (_, row) in enumerate(df.iterrows()):
            v = float(row['events'])
            rows.append(f"""
            <div class='bucket-card' style='border-top-color:{colors[i % len(colors)]}'>
              <b>{escape(str(row['bucket']))}</b>
              <span>{fmt_int(v)} events</span>
              <em>{fmt_pct(v / total)} of candidate events</em>
            </div>""")
        return "".join(rows)

    def tiny_bars(df, value_col, color="#7b72d8"):
        max_v = max(float(df[value_col].max()), 1)
        return "".join(
            f"<div class='tiny-bar' style='height:{float(row[value_col]) / max_v * 100:.1f}%;background:{color}'></div>"
            for _, row in df.iterrows()
        )

    def tiny_bar_chart(df, value_col, color="#7b72d8", x_start="", x_mid="", x_end="", y_fmt=lambda x: f"{x:.0f}"):
        max_v = max(float(df[value_col].max()), 1)
        bars_html = tiny_bars(df, value_col, color)
        return f"""
        <div class='tiny-chart'>
          <div class='tiny-yaxis'>
            <span>{y_fmt(max_v)}</span>
            <span>{y_fmt(max_v * .75)}</span>
            <span>{y_fmt(max_v * .5)}</span>
            <span>{y_fmt(max_v * .25)}</span>
            <span>0</span>
          </div>
          <div class='tiny-plot'>
            <div class='tiny-grid' style='top:42px'></div>
            <div class='tiny-grid' style='top:80px'></div>
            <div class='tiny-grid' style='top:118px'></div>
            <div class='tiny-bars'>{bars_html}</div>
            <div class='tiny-xaxis'><span>{x_start}</span><span>{x_mid}</span><span>{x_end}</span></div>
          </div>
        </div>
        """

    def line_svg(df, series):
        width, height = 760, 250
        left, right, top, bottom = 72, 18, 18, 42
        max_v = max([float(df[s].max()) for s, _ in series] + [1])
        n = max(len(df) - 1, 1)
        x0, x1 = left, width - right
        y0, y1 = height - bottom, top
        paths = []
        for col, color in series:
            pts = []
            for i, row in df.reset_index(drop=True).iterrows():
                x = x0 + i * (x1 - x0) / n
                y = y0 - (float(row[col]) / max_v) * (y0 - y1)
                pts.append(f"{x:.1f},{y:.1f}")
            paths.append(f"<polyline points='{' '.join(pts)}' fill='none' stroke='{color}' stroke-width='4'/>")
        tick_rows = df.reset_index(drop=True)
        step = max(1, len(tick_rows) // 6)
        x_ticks = []
        for i, row in tick_rows.iterrows():
            if i % step == 0 or i == len(tick_rows) - 1:
                x = x0 + i * (x1 - x0) / n
                label = pd.to_datetime(row['week_start']).strftime('%b %-d')
                anchor = 'middle'
                if i == 0:
                    anchor = 'start'
                elif i == len(tick_rows) - 1:
                    anchor = 'end'
                x_ticks.append(f"<line x1='{x:.1f}' y1='{y0}' x2='{x:.1f}' y2='{y0+6}' /><text x='{x:.1f}' y='{height-12}' text-anchor='{anchor}'>{label}</text>")
        return f"""<svg viewBox='0 0 {width} {height}' class='line-svg'>
            <line x1='{x0}' y1='{y0}' x2='{x1}' y2='{y0}' />
            <line x1='{x0}' y1='{(y0+y1)*.75}' x2='{x1}' y2='{(y0+y1)*.75}' class='grid' />
            <line x1='{x0}' y1='{(y0+y1)/2}' x2='{x1}' y2='{(y0+y1)/2}' class='grid' />
            <line x1='{x0}' y1='{(y0+y1)*.25}' x2='{x1}' y2='{(y0+y1)*.25}' class='grid' />
            <line x1='{x0}' y1='{y1}' x2='{x0}' y2='{y0}' />
            <text x='{x0-10}' y='{y0+4}' text-anchor='end'>0</text>
            <text x='{x0-10}' y='{y0-(y0-y1)*.25+4}' text-anchor='end'>{fmt_int(max_v*.25)}</text>
            <text x='{x0-10}' y='{(y0+y1)/2+4}' text-anchor='end'>{fmt_int(max_v*.5)}</text>
            <text x='{x0-10}' y='{y0-(y0-y1)*.75+4}' text-anchor='end'>{fmt_int(max_v*.75)}</text>
            <text x='{x0-10}' y='{y1+4}' text-anchor='end'>{fmt_int(max_v)}</text>
            {''.join(x_ticks)}
            {''.join(paths)}
        </svg>"""

    def area_svg(df):
        width, height = 430, 230
        left, right, top, bottom = 52, 12, 16, 38
        max_v = max(float(df["ottawa"].max()), float(df["border"].max()), 1)
        n = max(len(df) - 1, 1)
        x0, x1 = left, width - right
        y0, y1 = height - bottom, top
        def area(col, color):
            top_points = []
            for i, row in df.reset_index(drop=True).iterrows():
                x = x0 + i * (x1 - x0) / n
                y = y0 - (float(row[col]) / max_v) * (y0 - y1)
                top_points.append((x, y))
            pts = [(x0, y0)] + top_points + [(x1, y0)]
            return f"<polygon points='{' '.join(f'{x:.1f},{y:.1f}' for x, y in pts)}' fill='{color}' opacity='.82'/>"
        start = pd.to_datetime(df['week_start'].min()).strftime('%b %-d')
        end = pd.to_datetime(df['week_start'].max()).strftime('%b %-d')
        return f"""<svg viewBox='0 0 {width} {height}' class='area-svg'>
            {area('ottawa', '#3d91e2')}{area('border', '#c98925')}
            <line x1='{x0}' y1='{y0}' x2='{x1}' y2='{y0}' />
            <line x1='{x0}' y1='{y1}' x2='{x0}' y2='{y0}' />
            <text x='{x0-8}' y='{y0+4}' text-anchor='end'>0</text>
            <text x='{x0-8}' y='{y1+4}' text-anchor='end'>{fmt_int(max_v)}</text>
            <text x='{x0}' y='{height-10}' text-anchor='start'>{start}</text>
            <text x='{x1}' y='{height-10}' text-anchor='end'>{end}</text>
        </svg>"""

    return (
        area_svg,
        bars,
        bucket_blocks,
        fmt_h,
        fmt_int,
        fmt_pct,
        funnel,
        line_svg,
        tiny_bar_chart,
    )


@app.cell
def _(
    actor_amplification,
    area_svg,
    bars,
    boundary_buckets,
    boundary_counts,
    bucket_blocks,
    confidence_hist,
    fmt_h,
    fmt_int,
    fmt_pct,
    funnel,
    lead_lag,
    lead_lag_metrics,
    line_svg,
    location_distribution,
    mo,
    pd,
    place_lens,
    quality_flags,
    source_concentration,
    source_metrics,
    tiny_bar_chart,
    totals,
    weekly_volume,
):
    boundary_html = funnel(boundary_counts)
    bucket_html = bucket_blocks(boundary_buckets)
    source_html = bars(source_concentration.head(5), "source", "mentions", color="#3d91e2")
    _location_display = location_distribution.assign(display=location_distribution["location"].str.slice(0, 28))
    location_html = bars(_location_display.head(6), "display", "events", color="#2da77d")
    actor_html = bars(actor_amplification, "actor", "mentions_per_event", color="#ef6536", value_fmt=lambda x: f"{x:.1f}")
    _week_start = pd.to_datetime(weekly_volume['week_start'].min()).strftime('%b %-d')
    _week_mid = pd.to_datetime(weekly_volume['week_start'].iloc[len(weekly_volume)//2]).strftime('%b %-d')
    _week_end = pd.to_datetime(weekly_volume['week_start'].max()).strftime('%b %-d')
    mpe_html = tiny_bar_chart(weekly_volume, "mentions_per_event", color="#7b72d8", x_start=_week_start, x_mid=_week_mid, x_end=_week_end, y_fmt=lambda x: f"{x:.1f}")
    _confidence_buckets = pd.DataFrame({
        "confidence": ["Low confidence (<50)", "Medium confidence (50-79)", "High confidence (80-100)"],
        "mentions": [
            int(confidence_hist.loc[confidence_hist["confidence_bin"] < 50, "mentions"].sum()),
            int(confidence_hist.loc[(confidence_hist["confidence_bin"] >= 50) & (confidence_hist["confidence_bin"] < 80), "mentions"].sum()),
            int(confidence_hist.loc[confidence_hist["confidence_bin"] >= 80, "mentions"].sum()),
        ],
    })
    confidence_html = bars(_confidence_buckets, "confidence", "mentions", color="#27a983")
    _lag_binned = lead_lag[lead_lag["lag_hour"] <= 24].copy()
    lag_html = tiny_bar_chart(_lag_binned, "mentions", color="#6658ca", x_start="0h", x_mid="12h", x_end="24h", y_fmt=fmt_int)
    weekly_svg = line_svg(weekly_volume, [("mentions", "#24ad8c"), ("events", "#3d91e2"), ("articles", "#ef6536")])
    place_svg = area_svg(place_lens)

    _start_date = pd.to_datetime(totals['min_date']).strftime('%Y-%m-%d')
    _end_date = pd.to_datetime(totals['max_date']).strftime('%Y-%m-%d')
    _window_days = (pd.to_datetime(totals['max_date']) - pd.to_datetime(totals['min_date'])).days + 1

    html = f"""
    <style>
    .fc-wrap {{ background:#f5f1e8; color:#1b2028; padding:56px; font-family: Inter, ui-sans-serif, system-ui, -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif; max-width:1180px; margin:auto; border:1px solid #d8d0bf; }}
    .eyebrow {{ color:#5e625d; font-family: ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, monospace; font-size:13px; font-weight:800; letter-spacing:.04em; text-transform:uppercase; }}
    .fc-wrap h1 {{ margin:14px 0 0 0; font-size:46px; line-height:.98; font-weight:900; letter-spacing:-.045em; color:#19202a; }}
    .dek {{ color:#343230; font-family: Georgia, 'Times New Roman', serif; font-style:italic; font-size:21px; margin-top:12px; }}
    .top-rule {{ border-top:3px solid #1d2430; margin-top:22px; }}
    .statstrip {{ display:grid; grid-template-columns:repeat(5, 1fr); gap:34px; margin:18px 0 26px 0; }}
    .stat b {{ display:block; font-size:24px; line-height:1; letter-spacing:-.03em; color:#1d2430; }}
    .stat span {{ display:block; margin-top:5px; color:#6d6a62; font-family:ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, monospace; font-size:11px; font-weight:800; text-transform:uppercase; }}
    .stat em {{ display:block; margin-top:6px; color:#68645b; font-family:Georgia, 'Times New Roman', serif; font-size:13px; line-height:1.25; font-style:italic; }}
    .pill {{ display:inline-block; border-top:5px solid #a97324; background:#eee8dc; color:#1d2430; padding:10px 16px; font-family:ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, monospace; font-size:13px; font-weight:900; text-transform:uppercase; }}
    .rule {{ border-top:1px solid #c9c0ad; margin-top:24px; padding-top:18px; }}
    .section-title {{ font-size:17px; font-weight:900; color:#1d2430; margin-bottom:2px; font-family:ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, monospace; text-transform:uppercase; letter-spacing:.01em; }}
    .section-sub {{ color:#6b675d; font-family:Georgia, 'Times New Roman', serif; font-style:italic; font-size:17px; font-weight:500; margin-bottom:18px; }}
    .helper {{ background:#eee8dc; border-left:5px solid #5c7284; padding:10px 14px; margin:0 0 14px 0; color:#3f3d38; font-size:14px; line-height:1.35; font-family:Georgia, 'Times New Roman', serif; }}
    .helper b {{ color:#1d2430; font-family:ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, monospace; font-size:12px; text-transform:uppercase; }}
    .grid2 {{ display:grid; grid-template-columns:1fr 1fr; gap:38px; }}
    .bar-row {{ display:grid; grid-template-columns:220px 1fr 72px; gap:14px; align-items:center; margin:8px 0; font-size:15px; font-weight:800; color:#343a3f; }}
    .bar-track {{ height:10px; background:#e1dacd; border-radius:0; overflow:hidden; }}
    .bar-fill {{ height:100%; border-radius:0; }}
    .bar-value {{ color:#343a3f; text-align:right; font-family:ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, monospace; font-size:13px; }}
    .legend {{ display:flex; gap:18px; justify-content:flex-end; color:#5f625c; font-size:14px; font-weight:800; font-family:ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, monospace; }}
    .legend-notes {{ display:grid; grid-template-columns:repeat(3, 1fr); gap:12px; margin:10px 0 14px 0; }}
    .legend-note {{ background:#fbf8ef; border:1px solid #d8d0bf; border-top:4px solid #5c7284; border-radius:4px; padding:10px 12px; }}
    .legend-note b {{ display:block; color:#1d2430; font-size:13px; font-family:ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, monospace; text-transform:uppercase; }}
    .legend-note span {{ display:block; margin-top:5px; color:#55524b; font-family:Georgia, 'Times New Roman', serif; font-size:14px; line-height:1.25; }}
    .sw {{ display:inline-block; width:12px; height:12px; border-radius:2px; margin-right:6px; vertical-align:-1px; }}
    svg.line-svg, svg.area-svg {{ width:100%; height:auto; display:block; background:#fbf8ef; border:1px solid #d8d0bf; border-top:5px solid #5c7284; border-radius:4px; }}
    svg line {{ stroke:#aca38f; stroke-width:1.2; }}
    svg line.grid {{ stroke:#ded6c8; stroke-width:1; }}
    svg text {{ fill:#5f625c; font-family:ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, monospace; font-size:13px; font-weight:800; }}
    .tiny-chart {{ display:grid; grid-template-columns:48px 1fr; align-items:stretch; }}
    .tiny-yaxis {{ height:150px; display:flex; flex-direction:column; justify-content:space-between; align-items:flex-end; padding:8px 8px 0 0; color:#5f625c; font-family:ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, monospace; font-size:12px; font-weight:800; }}
    .tiny-plot {{ position:relative; }}
    .tiny-bars {{ height:150px; display:flex; align-items:end; gap:8px; padding:8px 18px 0 18px; border-left:2px solid #aca38f; border-bottom:2px solid #aca38f; background:#fbf8ef; border-top:5px solid #5c7284; }}
    .tiny-bar {{ flex:1; min-width:8px; border-radius:0; z-index:2; }}
    .tiny-grid {{ position:absolute; left:0; right:0; height:1px; background:#ded6c8; z-index:1; }}
    .tiny-grid-mid {{ top:80px; }}
    .tiny-xaxis {{ display:flex; justify-content:space-between; color:#5f625c; font-family:ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, monospace; font-size:12px; font-weight:800; padding:4px 0 0 0; }}
    .funnel {{ margin-top:18px; }}
    .funnel-step {{ display:grid; grid-template-columns:240px 1fr 88px; gap:16px; align-items:center; margin:12px 0; }}
    .funnel-label {{ font-size:13px; line-height:1.15; font-weight:900; color:#1d2430; font-family:ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, monospace; text-transform:uppercase; }}
    .funnel-track {{ height:18px; background:#e1dacd; }}
    .funnel-bar {{ height:18px; background:#5c7284; border-left:6px solid #1d2430; }}
    .funnel-value {{ color:#343a3f; text-align:right; font-family:ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, monospace; font-size:14px; font-weight:900; }}
    .bucketgrid {{ display:grid; grid-template-columns:repeat(4, 1fr); gap:12px; margin-top:18px; }}
    .bucket-card {{ background:#fbf8ef; border:1px solid #d8d0bf; border-top:5px solid #5c7284; border-radius:4px; padding:12px; }}
    .bucket-card b {{ display:block; color:#1d2430; font-size:13px; line-height:1.2; font-family:ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, monospace; text-transform:uppercase; }}
    .bucket-card span {{ display:block; margin-top:9px; color:#1d2430; font-size:19px; font-weight:900; }}
    .bucket-card em {{ display:block; margin-top:4px; color:#6b675d; font-family:Georgia, 'Times New Roman', serif; font-size:13px; line-height:1.2; }}
    .cardgrid {{ display:grid; grid-template-columns:1fr 1fr; gap:12px; margin-top:28px; }}
    .card {{ background:#fbf8ef; color:#1d2430; border:1px solid #d8d0bf; border-top:5px solid #a97324; border-radius:4px; padding:14px 16px; font-size:15px; font-weight:800; }}
    .card b {{ display:block; font-size:25px; margin-top:4px; font-family:ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, monospace; }}
    .card em {{ display:block; margin-top:8px; color:#6b675d; font-family:Georgia, 'Times New Roman', serif; font-size:13px; line-height:1.25; font-weight:500; }}
    .method {{ display:grid; grid-template-columns:1fr 1fr 1fr; gap:22px; margin-top:18px; }}
    .method-card {{ background:#fbf8ef; border:1px solid #d8d0bf; border-top:5px solid #a97324; border-radius:4px; padding:18px; }}
    .method-card:nth-child(2) {{ border-top-color:#5c7284; }}
    .method-card:nth-child(3) {{ border-top-color:#3d806f; }}
    .method-card b {{ display:block; color:#1d2430; font-size:15px; margin-bottom:10px; font-family:ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, monospace; text-transform:uppercase; }}
    .method-card p {{ margin:0; color:#444641; font-family:Georgia, 'Times New Roman', serif; font-size:16px; line-height:1.35; font-weight:500; }}
    .formula {{ margin-top:16px; background:#eee8dc; border:1px solid #d8d0bf; border-left:6px solid #a97324; padding:14px 18px; color:#343230; font-family:ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, monospace; font-size:13px; line-height:1.45; font-weight:800; }}
    .persist {{ display:flex; align-items:center; gap:18px; margin-top:22px; color:#5f625c; font-size:14px; font-weight:800; font-family:ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, monospace; }}
    .mint {{ background:#e8efe8; color:#225f52; border:1px solid #9eb8ad; border-top:5px solid #3d806f; border-radius:4px; padding:12px 18px; }}
    </style>
    <div class='fc-wrap'>
      <div class='eyebrow'>Observation-layer cheat sheet · GDELT candidate corpus</div>
      <h1>Freedom Convoy in GDELT</h1>
      <div class='dek'>A profile of the media coverage we'll ask agents to reason from, before we give them context on what GDELT sees, misses, and distorts.</div>
      <div class='top-rule'></div>
      <div class='statstrip'>
        <div class='stat'><b>{fmt_int(totals['events'])}</b><span>candidate events</span><em>GDELT event rows attached to convoy-candidate article URLs; not all are protests.</em></div>
        <div class='stat'><b>{fmt_int(totals['mentions'])}</b><span>mentions</span><em>Event-mention traces: article-level observations of those event records.</em></div>
        <div class='stat'><b>{fmt_int(source_metrics['distinct_sources'])}</b><span>distinct sources</span><em>Unique mention domains/source names in the candidate corpus.</em></div>
        <div class='stat'><b>{fmt_pct(source_metrics['top10_share'])}</b><span>top-10 source share</span><em>Share of all mentions produced by the ten largest sources; a concentration signal.</em></div>
        <div class='stat'><b>{_start_date}<br/>→ {_end_date}</b><span>{_window_days} days</span><em>Event-date span covered by the GDELT records in this corpus.</em></div>
      </div>
      <div class='pill'>Measured from GDELT event, mention, and GKG records</div>

      <div class='rule'>
        <div class='section-title'>0 · From news coverage to candidate events</div>
        <div class='section-sub'>GDELT starts from news articles. Our corpus starts from articles that look convoy-related, then keeps the event records GDELT extracted from those articles.</div>
        <div class='method'>
          <div class='method-card'><b>1 · Find convoy-looking articles</b><p>We search GDELT's news metadata for terms like freedom convoy, trucker protest, Coutts, Ambassador Bridge, Emergencies Act, and named organizers.</p></div>
          <div class='method-card'><b>2 · Keep their event records</b><p>If GDELT extracted an event from one of those articles, it enters the candidate corpus. The event itself might be a protest, a government response, a court action, or a related political story.</p></div>
          <div class='method-card'><b>3 · Classify the corpus</b><p>Then we inspect the metadata: where GDELT placed the event, whether CAMEO coded it as protest, which source mentioned it, and how confident the trace looks.</p></div>
        </div>
        <div class='formula'>What this means: the topline count is not “the convoy.” It's the broad media-coverage surface around the convoy. The next step is to classify that surface before an agent reasons from it.</div>
      </div>

      <div class='rule'>
        <div class='section-title'>1 · First cut through the candidate corpus</div>
        <div class='section-sub'>The first metadata split asks two simple questions: did GDELT place the event in Canada, and did CAMEO code it as protest?</div>
        <div class='funnel'>{boundary_html}</div>
        <div class='bucketgrid'>{bucket_html}</div>
      </div>

      <div class='rule'>
        <div class='section-title'>A · Weekly coverage volume</div>
        <div class='section-sub'>volume of the coverage, not the protest. Mentions dwarf events.</div>
        <div class='helper'><b>How to read this:</b> this chart shows when GDELT coverage intensified. Peaks mean more records and article traces in the observation layer. They don't prove more protest activity on the ground.</div>
        <div class='legend'><span><i class='sw' style='background:#24ad8c'></i>mentions</span><span><i class='sw' style='background:#3d91e2'></i>events</span><span><i class='sw' style='background:#ef6536'></i>articles</span></div>
        <div class='legend-notes'>
          <div class='legend-note' style='border-top-color:#3d91e2'><b>Events</b><span>Structured GDELT records for things it thinks happened: actor, action code, date, place, tone, and source URL.</span></div>
          <div class='legend-note' style='border-top-color:#24ad8c'><b>Mentions</b><span>Article-level traces that mention an event. One event can have many mentions across sources and time.</span></div>
          <div class='legend-note' style='border-top-color:#ef6536'><b>Articles</b><span>GDELT's count of source articles attached to event records. This is coverage volume, not ground truth volume.</span></div>
        </div>
        {weekly_svg}
      </div>

      <div class='rule grid2'>
        <div><div class='section-title'>B · Mentions per event</div><div class='section-sub'>amplification, rising into the peak</div><div class='helper'><b>How to read this:</b> higher bars mean each coded event was mentioned by more articles. This points to media amplification, not necessarily more distinct events.</div>{mpe_html}</div>
        <div><div class='section-title'>C · Source concentration</div><div class='section-sub'>HHI {source_metrics['hhi']:.3f} · top-10 {fmt_pct(source_metrics['top10_share'])} · {fmt_int(source_metrics['distinct_sources'])} sources</div><div class='helper'><b>How to read this:</b> this shows whether a few outlets dominate the corpus. High concentration means an agent may inherit the framing choices of a small set of sources.</div>{source_html}<div class='section-sub'>long tail of one-off outlets below</div></div>
      </div>

      <div class='rule grid2'>
        <div><div class='section-title'>D · Location distribution</div><div class='section-sub'>where coverage says it happened</div><div class='helper'><b>How to read this:</b> these are GDELT-coded locations, not verified protest sites. They show the geography attached to the coverage.</div>{location_html}</div>
        <div><div class='section-title'>E · Ottawa vs border blockade</div><div class='section-sub'>two sub-stories, different peaks</div><div class='helper'><b>How to read this:</b> this separates two recurring location frames. If the shapes differ, an agent should avoid treating the convoy as one flat, single-location story.</div><div class='legend' style='justify-content:flex-start'><span><i class='sw' style='background:#3d91e2'></i>Ottawa</span><span><i class='sw' style='background:#c98925'></i>border</span></div>{place_svg}</div>
      </div>

      <div class='rule grid2'>
        <div><div class='section-title'>F · Actor amplification</div><div class='section-sub'>mentions per event, by actor</div><div class='helper'><b>How to read this:</b> actors with high values get more mentions per coded role. This can reveal who the media lens repeats most often.</div>{actor_html}</div>
        <div><div class='section-title'>G · Mention timing after event</div><div class='section-sub'>median {fmt_h(lead_lag_metrics['median_lag_h'])} · p90 {fmt_h(lead_lag_metrics['p90_lag_h'])} · {fmt_pct(lead_lag_metrics['within_24h'])} within 24h</div><div class='helper'><b>How to read this:</b> this shows how quickly article mentions appear after the event time GDELT assigned. In this corpus, almost all mentions land within the first day, so the useful view is 0 to 24 hours.</div>{lag_html}</div>
      </div>

      <div class='rule grid2'>
        <div><div class='section-title'>H · Gaps, ambiguities, low-confidence</div><div class='section-sub'>measured weaknesses of the lens, stated rather than interpreted</div><div class='helper'><b>How to read this:</b> GDELT assigns confidence to event mentions. Low-confidence mentions are weaker traces, so agents should avoid leaning too hard on them without other evidence.</div>{confidence_html}<div class='section-sub'>mention confidence groups</div></div>
        <div class='cardgrid'>
          <div class='card'>ungeocoded events <b>{fmt_pct(quality_flags['ungeocoded_event_share'])}</b><em>Event records where GDELT didn't attach a usable location. Low is good, but coding can still put events in the wrong place.</em></div>
          <div class='card'>null actor events <b>{fmt_pct(quality_flags['null_actor_event_share'])}</b><em>Event records missing both actor fields. Low is good, but named actors can still be broad labels like government or protesters.</em></div>
          <div class='card'>low-conf mentions <b>{fmt_pct(quality_flags['low_conf_mention_share'])}</b><em>Mentions with confidence below 50. These are weaker traces and shouldn't carry important claims on their own.</em></div>
          <div class='card'>distinct sources <b>{fmt_int(source_metrics['distinct_sources'])}</b><em>Unique sources in the mention layer. More sources doesn't mean balanced coverage, but it helps reveal concentration.</em></div>
        </div>
      </div>

    </div>
    """
    mo.Html(html)
    return


@app.cell
def _(
    EXPORT_DIR,
    actor_amplification,
    boundary_counts,
    confidence_hist,
    lead_lag,
    location_distribution,
    mo,
    place_lens,
    source_concentration,
    weekly_volume,
):
    def export_summaries():
        EXPORT_DIR.mkdir(parents=True, exist_ok=True)
        summaries = {
            "boundary_rule_counts": boundary_counts,
            "weekly_volume": weekly_volume,
            "source_concentration_top10": source_concentration,
            "location_distribution_top8": location_distribution,
            "ottawa_border_weekly": place_lens,
            "actor_amplification_top6": actor_amplification,
            "mention_lead_lag": lead_lag,
            "confidence_histogram": confidence_hist,
        }
        for name, frame in summaries.items():
            frame.to_csv(EXPORT_DIR / f"{name}.csv", index=False)
        return f"Exported {len(summaries)} summaries to {EXPORT_DIR}"

    export_button = mo.ui.run_button(label="Export summary CSVs")
    if export_button.value:
        status = export_summaries()
    else:
        status = f"Click to export measured summary tables to `{EXPORT_DIR}`."
    mo.vstack([export_button, mo.md(status)])
    return


if __name__ == "__main__":
    app.run()
