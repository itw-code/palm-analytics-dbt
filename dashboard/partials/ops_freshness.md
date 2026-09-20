```sql freshness
select max(operation_date) as as_of, datediff('day', max(operation_date), current_date) as days_stale from palm.operations_daily
```

{#if freshness[0].days_stale > 3}
<Alert status="warning">Data sudah <Value data={freshness} column=days_stale/> hari nggak update (terakhir <Value data={freshness} column=as_of fmt="yyyy-mm-dd"/>). Keputusan di bawah dibaca hati-hati ya.</Alert>
{/if}
