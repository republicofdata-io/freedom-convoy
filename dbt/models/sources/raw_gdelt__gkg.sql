{{ config(materialized='view') }}

select *
from read_parquet(
    '{{ var("raw_parquet_root") }}/gdelt_gkg/**/*.parquet',
    hive_partitioning = true,
    union_by_name = true
)
