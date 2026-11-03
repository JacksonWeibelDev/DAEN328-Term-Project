# NCVS Data Transformation

import pandas as pd

# SECTION 1: Convert Raw API Data into a Pandas DataFrame
# -------------------------------------------------------

def to_dataframe(raw_data):
    """
    Convert the list of dictionaries returned by extract.py
    into a pandas DataFrame.
    """

    df = pd.DataFrame(raw_data)

    return df

# SECTION 2: Standardize Missing Values
# -------------------------------------

def clean_missing_values(df):
    """
    Standardize empty strings and whitespace as missing values.
    Preserve existing survey codes and missing information.
    """

    # Create a copy to avoid modifying the original DataFrame
    cleaned_df = df.copy()

    # Identify columns containing text
    text_columns = cleaned_df.select_dtypes(
        include=["object", "string"]
    ).columns

    # Replace empty strings and whitespace with pandas NA
    for col in text_columns:
        cleaned_df[col] = cleaned_df[col].replace(
            r"^\s*$", pd.NA, regex=True
        )

    return cleaned_df


# SECTION 3: Convert Numeric Data Types
# -------------------------------------

def convert_numeric_columns(df):
    """
    Convert numeric survey fields from strings into numbers.
    Preserve missing values and original survey codes.
    """

    cleaned_df = df.copy()

    # Columns containing integer values or survey category codes
    integer_columns = [
        # Survey information
        "year",

        # Respondent demographics
        "ager",
        "sex",
        "hispanic",
        "race",
        "race_ethnicity",
        "hincome1",
        "hincome2",
        "marital",
        "popsize",
        "region",
        "msa",
        "locality",
        "educatn1",
        "educatn2",
        "veteran",
        "citizen",

        # Crime classifications
        "newcrime",
        "newoff",
        "seriousviolent",

        # Police reporting and victim services
        "notify",
        "vicservices",

        # Crime circumstances
        "locationr",
        "direl",
        "weapon",
        "weapcat",
        "injury",
        "serious",
        "treatment",

        # Offender characteristics
        "offenderage",
        "offendersex",
        "offtracenew",

        # Additional survey information
        "series"
    ]

    # Columns containing decimal survey weights
    decimal_columns = [
        "wgtviccy",
        "newwgt"
    ]

    # Convert integer columns
    for col in integer_columns:
        converted = pd.to_numeric(cleaned_df[col], errors="coerce")

        # Identify values that could not be converted
        invalid = cleaned_df[col].notna() & converted.isna()

        if invalid.any():
            raise ValueError(f"Invalid numeric values in {col}")

        # Nullable integers preserve missing values
        cleaned_df[col] = converted.astype("Int64")

    # Convert decimal columns
    for col in decimal_columns:
        converted = pd.to_numeric(cleaned_df[col], errors="coerce")

        invalid = cleaned_df[col].notna() & converted.isna()

        if invalid.any():
            raise ValueError(f"Invalid numeric values in {col}")

        cleaned_df[col] = converted.astype("Float64")

    return cleaned_df

# SECTION 4: Convert API Timestamps
# ---------------------------------

def convert_timestamps(df):
    """
    Convert the API creation and update timestamps
    from strings into datetime values.
    """

    # Create a copy of the DataFrame
    cleaned_df = df.copy()

    # Columns containing API timestamps
    timestamp_columns = [
        ":created_at",
        ":updated_at"
    ]

    # Convert each timestamp column
    for col in timestamp_columns:

        converted = pd.to_datetime(
            cleaned_df[col],
            errors="coerce",
            utc=True
        )

        # Check whether any timestamps are missing or invalid
        if converted.isna().any():
            raise ValueError(
                f"Missing or invalid timestamps in {col}"
            )

        cleaned_df[col] = converted

    return cleaned_df

# SECTION 5: Remove Duplicate Victimization Records
# -------------------------------------------------

def remove_duplicate_victimizations(df):
    """
    Remove exact duplicate records.

    Each victimization should have a unique API :id.
    Repeated respondent IDs are allowed because one respondent
    may have multiple victimizations.
    """

    # Create a copy of the DataFrame
    cleaned_df = df.copy()

    # Check for missing victimization identifiers
    if cleaned_df[":id"].isna().any():
        raise ValueError("Missing victimization IDs detected")

    # Count records before cleaning
    original_count = len(cleaned_df)

    # Remove completely identical records
    cleaned_df = cleaned_df.drop_duplicates()

    # Check whether the same ID identifies different records
    if cleaned_df[":id"].duplicated().any():
        raise ValueError(
            "Conflicting records found with the same victimization ID"
        )

    # Calculate how many duplicates were removed
    duplicates_removed = original_count - len(cleaned_df)

    print("Duplicate records removed:", duplicates_removed)

    return cleaned_df

# SECTION 6: Main Transformation Function
# ---------------------------------------

def transform_data(raw_data):
    """
    Run all transformation steps on the raw NCVS data.

    Accepts raw records from extract.py and returns
    a cleaned pandas DataFrame.
    """

    # Step 1: Convert API records into a DataFrame
    df = to_dataframe(raw_data)

    print("Records received:", len(df))

    if df.empty:
        print("No new or updated records to transform.")
        print("Duplicate records removed: 0")
        print("Records after cleaning: 0")
        return df

    # Step 2: Standardize missing values
    df = clean_missing_values(df)

    # Step 3: Convert numeric columns
    df = convert_numeric_columns(df)

    # Step 4: Convert API timestamps
    df = convert_timestamps(df)

    # Step 5: Remove duplicate victimization records
    df = remove_duplicate_victimizations(df)

    # Display the final record count
    print("Records after cleaning:", len(df))

    # Report remaining missing values
    missing_values = df.isna().sum()
    missing_values = missing_values[missing_values > 0]

    print("\nMissing values preserved:")
    print(missing_values if not missing_values.empty else "None")

    # Return the cleaned DataFrame
    return df