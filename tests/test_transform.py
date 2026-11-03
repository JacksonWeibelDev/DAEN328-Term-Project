# DAEN 328 Term Project
# NCVS Transformation Tests

import pandas as pd

from transform import (
    clean_missing_values,
    convert_numeric_columns,
    convert_timestamps,
    remove_duplicate_victimizations
)

# TEST 1: Standardize Missing Values
# ----------------------------------

def test_clean_missing_values():

    # Create a small DataFrame containing missing values
    test_data = pd.DataFrame({
        "weapcat": ["", "  ", None, "5"],
        "treatment": ["2", "1", "", "0"]
    })

    # Run the cleaning function
    cleaned_df = clean_missing_values(test_data)

    # Verify missing values were standardized
    assert cleaned_df["weapcat"].isna().sum() == 3
    assert cleaned_df["treatment"].isna().sum() == 1

    # Verify existing valid values were preserved
    assert cleaned_df.loc[3, "weapcat"] == "5"
    assert cleaned_df.loc[0, "treatment"] == "2"

    # Verify no records were removed
    assert len(cleaned_df) == 4

# TEST 2: Convert Numeric Columns
# -------------------------------

def test_convert_numeric_columns():

    # Define the integer columns used by the transformation
    integer_columns = [
        "year", "ager", "sex", "hispanic", "race",
        "race_ethnicity", "hincome1", "hincome2",
        "marital", "popsize", "region", "msa",
        "locality", "educatn1", "educatn2",
        "veteran", "citizen", "newcrime", "newoff",
        "seriousviolent", "notify", "vicservices",
        "locationr", "direl", "weapon", "weapcat",
        "injury", "serious", "treatment",
        "offenderage", "offendersex", "offtracenew",
        "series"
    ]

    # Create two sample records containing numeric strings
    test_data = pd.DataFrame({
        col: ["1", "2"] for col in integer_columns
    })

    # Add missing values and special survey codes
    test_data["weapcat"] = [None, "5"]
    test_data["treatment"] = [None, "2"]
    test_data["injury"] = ["98", "0"]

    # Add decimal survey weights
    test_data["wgtviccy"] = ["1.25", "2.50"]
    test_data["newwgt"] = ["3.75", "4.50"]

    # Run the numeric conversion function
    cleaned_df = convert_numeric_columns(test_data)

    # Verify numeric data types
    assert cleaned_df["year"].dtype == "Int64"
    assert cleaned_df["newoff"].dtype == "Int64"
    assert cleaned_df["newwgt"].dtype == "Float64"

    # Verify missing values were preserved
    assert cleaned_df["weapcat"].isna().sum() == 1
    assert cleaned_df["treatment"].isna().sum() == 1

    # Verify original survey codes were preserved
    assert cleaned_df.loc[0, "injury"] == 98
    assert cleaned_df.loc[1, "weapcat"] == 5

    # Verify decimal values
    assert cleaned_df.loc[0, "newwgt"] == 3.75

    # Verify no records were removed
    assert len(cleaned_df) == 2

# TEST 3: Convert API Timestamps
# ------------------------------

def test_convert_timestamps():

    # Create sample records with timestamps stored as strings
    test_data = pd.DataFrame({
        ":created_at": [
            "2025-09-29T13:14:01.763Z",
            "2026-10-21T20:26:26.774Z"
        ],
        ":updated_at": [
            "2026-10-21T20:26:26.774Z",
            "2026-10-21T20:26:26.774Z"
        ]
    })

    # Run the timestamp conversion function
    cleaned_df = convert_timestamps(test_data)

    # Verify timestamps were converted to datetime values
    assert pd.api.types.is_datetime64_any_dtype(
        cleaned_df[":created_at"]
    )

    assert pd.api.types.is_datetime64_any_dtype(
        cleaned_df[":updated_at"]
    )

    # Verify timestamps use UTC
    assert str(cleaned_df[":updated_at"].dt.tz) == "UTC"

    # Verify the original timestamp was preserved
    assert cleaned_df.loc[0, ":updated_at"] == pd.Timestamp(
        "2026-10-21T20:26:26.774Z"
    )

    # Verify no records were removed
    assert len(cleaned_df) == 2

# TEST 4: Remove Duplicate Victimization Records
# ----------------------------------------------

def test_remove_duplicate_victimizations():

    # Create sample records with one exact duplicate
    # Records 1 and 2 belong to the same respondent,
    # but represent different victimizations.
    test_data = pd.DataFrame({
        ":id": ["row1", "row1", "row2"],
        "idper": ["123", "123", "123"],
        "yearq": ["2023", "2023", "2023"],
        "newoff": [1, 1, 2]
    })

    # Run the duplicate removal function
    cleaned_df = remove_duplicate_victimizations(test_data)

    # Verify the exact duplicate was removed
    assert len(cleaned_df) == 2

    # Verify each victimization has a unique ID
    assert cleaned_df[":id"].duplicated().sum() == 0

    # Verify both legitimate victimizations were preserved
    assert set(cleaned_df[":id"]) == {"row1", "row2"}

    # Verify repeated respondent identifiers are allowed
    assert cleaned_df["idper"].nunique() == 1