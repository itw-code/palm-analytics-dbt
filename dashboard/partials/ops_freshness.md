```sql freshness
select max(operation_date) as as_of, datediff('day', max(operation_date), current_date) as days_stale from palm.operations_daily
```

{#if freshness[0].days_stale > 3}
<Alert status="warning">Data is <Value data={freshness} column=days_stale/> days stale (last refresh <Value data={freshness} column=as_of fmt="yyyy-mm-dd"/>). Treat recommendations with caution.</Alert>
{/if}
