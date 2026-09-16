# hdb_data_engineer_test_202609
Data Engineer Test for HDB Sept 2026

Combines 5 raw HDB resale transaction CSVs (1990–present) into a single cleaned dataset, with duplication removal, a hashed row identifier, anomaly detection, categorical validation, and a remaining lease-consistency check.

Environment was created with the following packages and versions
| Component | Version |
|---|---|
| Python | 3.11 |
| setuptools | 80.10.2 |
| ydata-profiling | 4.18.0 |
| pandas | (as installed in the environment) |

The Input folder is created under "C:\Users\xxx" where "xxx" is the username (C:\Users\xxx\Input) and these files are unzipped from ResaleFlatPrices.zip:-

1) Resale Flat Prices (Based on Approval Date), 1990 - 1999.csv
2) Resale Flat Prices (Based on Approval Date), 2000 - Feb 2012.csv
3) Resale Flat Prices (Based on Registration Date), From Jan 2015 to Dec 2016.csv
4) Resale Flat Prices (Based on Registration Date), From Mar 2012 to Dec 2014.csv
5) Resale flat prices based on registration date from Jan-2017 onwards.csv

The Output folder is created under "C:\Users\xxx" where "xxx" is the username (C:\Users\xxx\Output) so that all the generated outputs are placed into it.

Data Pipeline Assumptions:-
1) flat_model is standardized as there are Case inconsistencies and punctuation drifts
2) resale_identifier is created with the combination in the document but it has also been added with the key columns that are used to remove duplicates to maintain uniqueness
3) Using Jan 2012 as a whitelist, the validation is only done on town, flat_type, and flat_model as these 3 are the ones that standardization will work on, month and storey_range would not be applicable as month is ever changing and storey_range will differ based on what year the HDB is built and might have different restrictions over the years

Output Files:-
1) Files that are prefixed with "Transformed" are transformed and cleaned-up data
2) Files that are prefixed with "Hashed" are the data with the resale_identifier hashed key
3) Files that are prefixed with "Quarantined" are the duplicates that were removed and anomaly records, each created into its own file so that the analysis can be performed separately 

To run, the following is required
### requirements.txt
```
pandas
setuptools==80.10.2
ydata-profiling==4.18.0
```
Installation steps
```bash
pip install -r requirements.txt
python3 hdb_resale_pipeline.py
```

The python file is then run by using "%run hdb_resale_data_pipeline.py"
