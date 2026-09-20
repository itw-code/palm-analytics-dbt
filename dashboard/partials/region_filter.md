```sql regions_list
select region_key, region_name from palm.region order by region_name
```

<Dropdown name=region data={regions_list} value=region_key label=region_name title="Region · Wilayah" defaultValue="%">
    <DropdownOption valueLabel="All regions · Semua wilayah" value="%" />
</Dropdown>
