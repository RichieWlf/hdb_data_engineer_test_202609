import pandas as pd
import re
import hashlib
from ydata_profiling import ProfileReport

# =========================================================
# Global Variables and Configuration
# =========================================================

input_path = "C:\\Users\\xxx\\Input\\"
output_path = "C:\\Users\\xxx\\Output\\"

files = {
    "1990_1999": "Resale Flat Prices (Based on Approval Date), 1990 - 1999.csv",
    "2000_2012": "Resale Flat Prices (Based on Approval Date), 2000 - Feb 2012.csv",
    "2012_2014": "Resale Flat Prices (Based on Registration Date), From Jan 2015 to Dec 2016.csv",
    "2015_2016": "Resale Flat Prices (Based on Registration Date), From Mar 2012 to Dec 2014.csv",
    "2017_onwards": "Resale flat prices based on registration date from Jan-2017 onwards.csv",
}

# data dictionary for the columns common to every file
ddict = {
    "town": "str",
    "flat_type": "str",
    "block": "str",
    "street_name": "str",
    "storey_range": "str",
    "floor_area_sqm": "float64",
    "flat_model": "str",
    "lease_commence_date": "int64",
    "resale_price": "float64",
}

# =========================================================
# Remaining lease calculation
# =========================================================
# standardize HDB lease term
LEASE_TERM_YEARS = 99 

def parse_remaining_lease_text(value):
    """Parse '61 years 04 months' / '61 years' / '1 month' -> (years, months)."""
    if pd.isna(value):
        return (pd.NA, pd.NA)
    if isinstance(value, (int, float)):
        return (int(value), 0)
    years_match = re.search(r"(\d+)\s*year", str(value))
    months_match = re.search(r"(\d+)\s*month", str(value))
    years = int(years_match.group(1)) if years_match else 0
    months = int(months_match.group(1)) if months_match else 0
    return (years, months)


def calculate_remaining_lease(resale_month: pd.Series, lease_commence_date: pd.Series):
    """99 years - (resale date - lease commence date), rounded to the nearest month.
    Assumes each lease commences on 1 Jan of lease_commence_date."""
    elapsed_months = (resale_month.dt.year - lease_commence_date) * 12 + (resale_month.dt.month - 1)
    remaining_total_months = LEASE_TERM_YEARS * 12 - elapsed_months
    years = remaining_total_months // 12
    months = remaining_total_months % 12
    return years, months

# =========================================================
# Function to format month for output
# =========================================================
def format_month_for_output(df: pd.DataFrame) -> pd.DataFrame:
    df = df.copy()
    df["month"] = df["month"].dt.strftime("%Y-%m")
    return df

# =========================================================
# Load all 5 files, and standardize the columns
# =========================================================
def load_all_files() -> dict:
    dataframes = {}
    
    for label, filename in files.items():
        hdb_resale_df = pd.read_csv(
            input_path + filename,
            dtype=ddict,
            parse_dates=["month"],
        )
    
        if "remaining_lease" in hdb_resale_df.columns:
            # Files that already have it (2015-2016 as whole years, 2017+ as text)
            parsed_lease = hdb_resale_df["remaining_lease"].apply(parse_remaining_lease_text)
            hdb_resale_df["remaining_lease_years"] = parsed_lease.apply(lambda x: x[0]).astype("Int64")
            hdb_resale_df["remaining_lease_months"] = parsed_lease.apply(lambda x: x[1]).astype("Int64")
            hdb_resale_df = hdb_resale_df.drop(columns=["remaining_lease"])
        else:
            # Files missing it entirely -> calculate from lease_commence_date
            years, months = calculate_remaining_lease(hdb_resale_df["month"], hdb_resale_df["lease_commence_date"])
            hdb_resale_df["remaining_lease_years"] = years.astype("Int64")
            hdb_resale_df["remaining_lease_months"] = months.astype("Int64")
    
        # Format as per "x years y months"
        hdb_resale_df["remaining_lease"] = (
            hdb_resale_df["remaining_lease_years"].astype(str) + " years " +
            hdb_resale_df["remaining_lease_months"].astype(str) + " months"
        )
            
        dataframes[label] = hdb_resale_df

    return dataframes

# =========================================================
# Combine all 5 dataframes
# Remove duplicated records by using all columns besides the resale_price and then taking only the record with the highest resale price
# Data profiling is done on the combined data as well
# =========================================================
def data_cleaning(dataframes: dict):
    
    final_hdb_resale_df = pd.concat(dataframes.values(), ignore_index=True, sort=False)
    
    #Data Profiling on sample records, sample size is 1/3 of the full record count so that the sample is large enough to be profilled correctly and also it 
    #doesn't take a longer time to profile the entire dataset
    sample_size = final_hdb_resale_df.sample(n=300_000, random_state=42)
    profile = ProfileReport(sample_size, title="HDB Resale Prices — Data Profiling Report", minimal=False)
    profile.to_file(output_path+"combined_hdb_resale_data_profiling_report.html")
    
    # Duplicate removal
    # Identify duplicates based on all columns except resale_price
    key_cols = [c for c in final_hdb_resale_df.columns if c != "resale_price"]
    
    final_hdb_resale_sorted_df = final_hdb_resale_df.sort_values("resale_price", ascending=False)
    kept_index = final_hdb_resale_sorted_df.drop_duplicates(subset=key_cols, keep="first").index
    
    final_hdb_resale_dups_rem_df = (
            final_hdb_resale_sorted_df.loc[kept_index]
            .sort_values(key_cols)
            .reset_index(drop=True)
        )
    final_hdb_resale_dropped_dups_df = (
            final_hdb_resale_df.drop(index=kept_index)
            .sort_values(key_cols + ["resale_price"])
            .reset_index(drop=True)
        )
    
    return final_hdb_resale_dups_rem_df, final_hdb_resale_dropped_dups_df, key_cols


# =========================================================
# Standardization of flat_model
# =========================================================
def normalize_categorical(series: pd.Series) -> pd.Series:
    return (
        series.astype(str).str.strip().str.upper()
        .str.replace("-", " ", regex=False)
        .str.replace(r"\s+", " ", regex=True)
    )
    
def standardize_flat_model(df: pd.DataFrame) -> pd.DataFrame:
    df = df.copy()
    #To find the most frequent original spelling per normalized key
    canonical_map = (
        df.groupby(normalize_categorical(df["flat_model"]))["flat_model"]
        .agg(lambda x: x.value_counts().idxmax())
    )
    df["flat_model"] = normalize_categorical(df["flat_model"]).map(canonical_map)
    return df


# =========================================================
# Derive Resale_Identifier which will be hashed using sha256
# =========================================================
def derive_resale_identifier(df: pd.DataFrame, key_cols: list) -> pd.DataFrame:
    #To add in resale identifier
    final_hdb_resale_identifier_df = df.copy()  
    
    #To derieve average resale price grouped by yearmonth, town, flat_type
    final_hdb_resale_identifier_df["month"] = pd.to_datetime(final_hdb_resale_identifier_df["month"], errors="coerce")
    final_hdb_resale_identifier_df["yearmonth"] = final_hdb_resale_identifier_df["month"].dt.strftime("%Y-%m")
    final_hdb_resale_identifier_df["avg_price_group"] = final_hdb_resale_identifier_df.groupby(["yearmonth", "town", "flat_type"])["resale_price"].transform("mean")
    
    #2nd Point requirement
    def block_digits(block_val):
        digits_only = re.sub(r"\D", "", str(block_val))
        return digits_only[:3].zfill(3)
    
    final_hdb_resale_identifier_df["block_code"] = final_hdb_resale_identifier_df["block"].apply(block_digits)
        
    #3rd Point requirement
    def first_two_digits(avg_val):
        digits = str(int(round(avg_val)))
        return digits[:2].zfill(2)
    
    final_hdb_resale_identifier_df["avg_price_first2digits"] = final_hdb_resale_identifier_df["avg_price_group"].apply(first_two_digits)
    
    #4th Point requirement
    final_hdb_resale_identifier_df["month_code"] = final_hdb_resale_identifier_df["month"].dt.strftime("%m")
    
    #5th Point requirement
    final_hdb_resale_identifier_df["town_code"] = final_hdb_resale_identifier_df["town"].str[0].str.upper()
    
    #Final Identifier Value = S + block(3) + avgprice(2) + month(2) + town(1)
    final_hdb_resale_identifier_df["resale_code"] = (
        "S" + final_hdb_resale_identifier_df["block_code"] + final_hdb_resale_identifier_df["avg_price_first2digits"] + 
        final_hdb_resale_identifier_df["month_code"] + final_hdb_resale_identifier_df["town_code"]
    )
    identifier_key_cols = key_cols.copy()
    for col in ("remaining_lease_years", "remaining_lease_months"):
        if col in identifier_key_cols:
            identifier_key_cols.remove(col)
    
    #To create the unique identifier based on the columns used for removing duplicates and the Raw Resale Identifier
    final_hdb_resale_identifier_df["resale_identifier_raw"] = (
        final_hdb_resale_identifier_df["resale_code"] + "|" +
        final_hdb_resale_identifier_df[identifier_key_cols].astype(str).agg("|".join, axis=1)
    )
    
    #Hashing using sha256 on the raw Resale Identifier
    final_hdb_resale_identifier_df["Resale_Identifier"] = final_hdb_resale_identifier_df["resale_identifier_raw"].apply(
        lambda x: hashlib.sha256(x.encode("utf-8")).hexdigest()
    )
    
    final_hdb_resale_identifier_df = final_hdb_resale_identifier_df.drop(columns=["yearmonth","avg_price_group","block_code","avg_price_first2digits","month_code","town_code","resale_code","resale_identifier_raw"])
    
    return final_hdb_resale_identifier_df

# =========================================================
# To find any resale price that are anomalous and flag then using IQR on price_per_sqm
# =========================================================
def flag_iqr(group: pd.Series) -> pd.Series:
    q1, q3 = group.quantile([0.25, 0.75])
    iqr = q3 - q1
    lower, upper = q1 - 1.5 * iqr, q3 + 1.5 * iqr
    return (group < lower) | (group > upper)


def add_anomaly_flags(df: pd.DataFrame) -> pd.DataFrame:
    df = df.copy()
    df["price_per_sqm"] = df["resale_price"] / df["floor_area_sqm"]
    df["year"] = df["month"].dt.year

    # Flag anomalies within each town + flat_type + year group
    df["resale_price_is_anomaly"] = df.groupby(["town", "flat_type", "year"])["price_per_sqm"].transform(flag_iqr)
    
    return df

# =========================================================
# Check if the remaining lease is as per HDB lease term years (99) - (lease_commence_date - month)
# =========================================================
def add_remaining_lease_inconsistency_flag(df: pd.DataFrame, mismatch_threshold_months: int = 12) -> pd.DataFrame:
    df = df.copy()
    computed_months = LEASE_TERM_YEARS * 12 - ((df["month"].dt.year - df["lease_commence_date"]) * 12 + (df["month"].dt.month - 1))
    stated_months = df["remaining_lease_years"] * 12 + df["remaining_lease_months"]
    df["lease_diff_months"] = (computed_months - stated_months).abs()
    df["lease_mismatch_flag"] = df["lease_diff_months"] > mismatch_threshold_months

    return df

# =========================================================
# Using Jan 2012 as a whitelist, validating town, flat_type, flat_model
# =========================================================
def flag_not_in_reference(series: pd.Series, ref_set: set) -> pd.Series:
    normalized = normalize_categorical(series)
    ref_normalized = normalize_categorical(pd.Series(list(ref_set)))
    return ~normalized.isin(set(ref_normalized))


def add_validation_flags(df: pd.DataFrame) -> pd.DataFrame:
    df = df.copy()

    jan2012_whitelist = df[(df["month"].dt.year == 2012) & (df["month"].dt.month == 1)]
    ref_towns_whitelist = set(jan2012_whitelist["town"].unique())
    ref_flat_types_whitelist = set(jan2012_whitelist["flat_type"].unique())
    ref_flat_models_whitelist = set(jan2012_whitelist["flat_model"].unique())  

    df["town_not_in_jan2012_whitelist"] = flag_not_in_reference(df["town"], ref_towns_whitelist)
    df["flat_type_not_in_jan2012_whitelist"] = flag_not_in_reference(df["flat_type"], ref_flat_types_whitelist)
    df["flat_model_not_in_jan2012_whitelist"] = flag_not_in_reference(df["flat_model"], ref_flat_models_whitelist) 
    return df
    
# =========================================================
# Main process
# =========================================================
if __name__ == "__main__":
    print("Data process Begins:-")
    print("(1) Loading Files...")
    dataframes = load_all_files()
    
    print("(2) Data Cleansing and Data Profiling...")
    final_hdb_resale_dups_rem_df, final_hdb_resale_dropped_dups_df, key_cols = data_cleaning(dataframes)
    final_hdb_resale_dups_rem_df = standardize_flat_model(final_hdb_resale_dups_rem_df)

    print("(3) Creating Output files...")
    final_hdb_resale_dups_rem_output_df = final_hdb_resale_dups_rem_df.copy()
    final_hdb_resale_dups_rem_output_df = final_hdb_resale_dups_rem_output_df.drop(columns=["remaining_lease_years","remaining_lease_months"])
    format_month_for_output(final_hdb_resale_dups_rem_output_df).to_csv(output_path+"Transformed-combined_hdb_resale.csv", index=False)
    format_month_for_output(final_hdb_resale_dropped_dups_df).to_csv(output_path+"Quarantined-dropped_duplicates_hdb_resale.csv", index=False)

    print("(4) Deriving Resale Identifier and creating output file...")
    final_hdb_resale_identifier_df = derive_resale_identifier(final_hdb_resale_dups_rem_output_df, key_cols)
    format_month_for_output(final_hdb_resale_identifier_df).to_csv(output_path+"Hashed-combined_hdb_resale_with_identifier.csv", index=False)

    print("(5) To check if there are any anomalies in the resale price and creating output file...")
    final_hdb_resale_with_anomalies_flag_df = add_anomaly_flags(final_hdb_resale_dups_rem_df)
    final_hdb_resale_anomalies_df = final_hdb_resale_with_anomalies_flag_df[final_hdb_resale_with_anomalies_flag_df["resale_price_is_anomaly"]].sort_values("price_per_sqm")
    format_month_for_output(final_hdb_resale_anomalies_df).to_csv(output_path + "Quarantined-hdb_resale_price_anomalies.csv", index=False)

    print("(6) To check if there are any anomalies in the remaining lease and creating output file...")
    final_hdb_resale_remaining_lease_checked_df = add_remaining_lease_inconsistency_flag(final_hdb_resale_dups_rem_df)
    final_hdb_resale_remaining_lease_mismatched_df = final_hdb_resale_remaining_lease_checked_df[final_hdb_resale_remaining_lease_checked_df["lease_mismatch_flag"]].sort_values(
        "lease_diff_months", ascending=False
    )
    format_month_for_output(final_hdb_resale_remaining_lease_mismatched_df).to_csv(output_path + "Quarantined-hdb_remaining_lease_anomalies.csv", index=False)

    
    print("(7) To validate town, flat_type, flat_model by using Jan 2012 dataset as a whitelist and creating output file...")
    validated_hdb_resale_df = add_validation_flags(final_hdb_resale_dups_rem_df)

    flagged_hdb_resale_rows_df = validated_hdb_resale_df[
        (validated_hdb_resale_df["town_not_in_jan2012_whitelist"]) |
        (validated_hdb_resale_df["flat_type_not_in_jan2012_whitelist"]) |
        (validated_hdb_resale_df["flat_model_not_in_jan2012_whitelist"])
    ]
    format_month_for_output(flagged_hdb_resale_rows_df).to_csv(output_path + "Quarantined-hdb_resale_validation_flagged_rows.csv", index=False)
    
    print("Data process Ends")

