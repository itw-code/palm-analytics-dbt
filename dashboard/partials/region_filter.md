```sql regions_list
select region_key, region_name from palm.region order by region_name
```

<Dropdown name=region data={regions_list} value=region_key label=region_name title="Kebun / Estate" defaultValue="%">
    <DropdownOption valueLabel="Semua kebun" value="%" />
</Dropdown>
