import os
import sys

import pandas as pd

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import transform as t  # noqa: E402


def make_df(**cols):
    return pd.DataFrame(cols)


def test_rename_system_fields():
    df = make_df(**{":id": ["a"], ":updated_at": ["2026-01-01T00:00:00.000Z"]})
    out = t.rename_system_fields(df)
    assert list(out.columns) == ["victimization_id", "updated_at"]


def test_drop_unused_columns_removes_system_and_undocumented():
    df = make_df(idper=["1"], pseudostratum=["9"], secucode=["1"],
                 **{":created_at": ["x"], ":version": ["y"]})
    assert list(t.drop_unused_columns(df).columns) == ["idper"]


def test_drop_unused_columns_ignores_missing_columns():
    df = make_df(idper=["1"])
    assert list(t.drop_unused_columns(df).columns) == ["idper"]


def test_blank_strings_to_null_strips_and_counts():
    df = make_df(weapcat=["1", "", "  "], treatment=[" 2 ", "3", "4"])
    stats = {}
    out = t.blank_strings_to_null(df, stats)
    assert out["weapcat"].isna().tolist() == [False, True, True]
    assert out["treatment"].tolist() == ["2", "3", "4"]
    assert stats["missing_found"]["weapcat"] == 2


def test_blank_strings_to_null_counts_absent_api_keys():
    # Socrata omits null fields, so they show up as NaN in the DataFrame
    df = pd.DataFrame([{"idper": "1", "weapcat": "2"}, {"idper": "2"}])
    stats = {}
    out = t.blank_strings_to_null(df, stats)
    assert out["weapcat"].isna().tolist() == [False, True]
    assert stats["missing_found"]["weapcat"] == 1


def test_convert_types_codes_weights_and_timestamp():
    df = make_df(idper=["150043609151999999999914603"], yearq=["1993.4"],
                 year=["1993"], notify=["98"], wgtviccy=["2070.5"],
                 updated_at=["2026-10-21T20:26:26.774Z"])
    out = t.convert_types(df)
    assert str(out["year"].dtype) == "Int16"
    assert out["year"][0] == 1993
    assert out["wgtviccy"][0] == 2070.5
    assert out["idper"][0] == "150043609151999999999914603"  # not mangled
    assert out["yearq"][0] == "1993.4"
    assert out["updated_at"][0] == pd.Timestamp("2026-10-21T20:26:26.774Z")


def test_convert_types_keeps_missing_as_null():
    df = make_df(weapcat=pd.array([pd.NA, "3"], dtype="string"))
    out = t.convert_types(df)
    assert out["weapcat"].isna().tolist() == [True, False]


def test_remove_duplicate_records_keeps_latest_update():
    df = make_df(
        victimization_id=["a", "a", "b"],
        updated_at=pd.to_datetime(
            ["2026-01-01", "2026-02-01", "2026-01-01"], utc=True),
        notify=[2, 1, 2],
    )
    stats = {}
    out = t.remove_duplicate_records(df, stats)
    assert sorted(out["victimization_id"]) == ["a", "b"]
    assert out[out["victimization_id"] == "a"]["notify"].iloc[0] == 1
    assert stats["duplicates_removed"]["victimizations"] == 1


def test_remove_duplicate_records_keeps_identical_looking_rows_with_different_ids():
    df = make_df(
        victimization_id=["a", "b"],
        updated_at=pd.to_datetime(["2026-01-01", "2026-01-01"], utc=True),
        notify=[2, 2],
    )
    assert len(t.remove_duplicate_records(df)) == 2


def test_fill_weapcat_from_weapon():
    df = make_df(weapon=pd.array([2, 1, 2], dtype="Int16"),
                 weapcat=pd.array([pd.NA, pd.NA, 0], dtype="Int16"))
    stats = {}
    out = t.fill_weapcat_from_weapon(df, stats)
    # filled only where weapon == 2; weapon == 1 stays NULL
    assert out["weapcat"].tolist()[0] == 0
    assert pd.isna(out["weapcat"].tolist()[1])
    assert stats["filled"]["weapcat"] == 1


def test_fill_treatment_from_injury():
    df = make_df(injury=pd.array([0, 1, 0], dtype="Int16"),
                 treatment=pd.array([pd.NA, pd.NA, 0], dtype="Int16"))
    stats = {}
    out = t.fill_treatment_from_injury(df, stats)
    assert out["treatment"].tolist()[0] == 0
    assert pd.isna(out["treatment"].tolist()[1])
    assert stats["filled"]["treatment"] == 1


def test_replace_sentinel_codes_nulls_residue_and_invalid():
    df = make_df(marital=pd.array([98, 2], dtype="Int16"),
                 region=pd.array([-1, 3], dtype="Int16"),
                 notify=pd.array([98, 3], dtype="Int16"))
    stats = {}
    out = t.replace_sentinel_codes(df, stats)
    assert out["marital"].isna().tolist() == [True, False]
    assert out["region"].isna().tolist() == [True, False]
    assert out["notify"].tolist()[1] == 3  # "Do not know" is a real answer
    assert stats["sentinel_to_null"]["marital"] == 1


def test_replace_sentinel_codes_keeps_veteran_under_18():
    df = make_df(veteran=pd.array([-2, -1, 0, 98], dtype="Int16"))
    out = t.replace_sentinel_codes(df)
    assert out["veteran"].isna().tolist() == [True, False, False, True]
    assert out["veteran"].tolist()[1] == -1


def test_build_offense_types():
    out = t.build_offense_types()
    assert out["newoff"].tolist() == [1, 2, 3, 4, 5]
    assert out["newoff"].is_unique
    assert out.loc[out["newoff"] == 5, "offense_name"].iloc[0] == "Personal theft/larceny"


def test_build_respondents_one_row_per_person_quarter():
    rows = {c: [None] * 3 for c in t.RESPONDENT_COLUMNS}
    rows["idper"] = ["p1", "p1", "p2"]
    rows["yearq"] = ["2020.1", "2020.1", "2020.1"]
    rows["updated_at"] = pd.to_datetime(["2026-01-01"] * 3, utc=True)
    stats = {}
    out = t.build_respondents(pd.DataFrame(rows), stats)
    assert len(out) == 2
    assert list(out.columns) == t.RESPONDENT_COLUMNS
    assert stats["duplicates_removed"]["respondents"] == 1


def test_build_victimizations_selects_columns():
    rows = {c: [1] for c in t.VICTIMIZATION_COLUMNS + ["pseudostratum_extra"]}
    out = t.build_victimizations(pd.DataFrame(rows))
    assert list(out.columns) == t.VICTIMIZATION_COLUMNS


def _raw_record(i, **over):
    rec = {
        ":id": f"row-{i}", ":created_at": "2026-10-21T20:26:26.774Z",
        ":updated_at": "2026-10-21T20:26:26.774Z", ":version": "v",
        "idper": "111", "yearq": "2023.1", "year": "2023", "ager": "3",
        "sex": "1", "hispanic": "2", "race": "1", "race_ethnicity": "1",
        "hincome1": "98", "hincome2": "2", "marital": "1", "popsize": "3",
        "region": "2", "msa": "1", "locality": "1", "educatn1": "5",
        "educatn2": "6", "veteran": "-1", "citizen": "1", "newcrime": "1",
        "newoff": "4", "seriousviolent": "2", "notify": "2",
        "vicservices": "2", "locationr": "1", "direl": "4", "weapon": "2",
        "weapcat": "", "injury": "0", "serious": "1", "treatment": "",
        "offenderage": "3", "offendersex": "1", "offtracenew": "1",
        "wgtviccy": "100.5", "series": "1", "newwgt": "100.5",
        "pseudostratum": "5", "secucode": "1",
    }
    rec.update(over)
    return rec


def test_transform_end_to_end():
    records = [_raw_record(1), _raw_record(2), _raw_record(1)]  # id 1 repeated
    tables, stats = t.transform(records)
    assert stats["received"] == 3
    assert stats["after_cleaning"] == 2
    assert stats["duplicates_removed"]["victimizations"] == 1
    assert len(tables["victimizations"]) == 2
    assert len(tables["respondents"]) == 1  # same person+quarter
    assert tables["victimizations"]["weapcat"].tolist() == [0, 0]
    assert tables["victimizations"]["treatment"].tolist() == [0, 0]
    assert tables["respondents"]["hincome1"].isna().all()  # 98 -> NULL
    assert tables["respondents"]["veteran"].iloc[0] == -1  # kept
    assert "pseudostratum" not in tables["respondents"].columns
    assert any("received from API" in line for line in t.format_summary(stats))


def test_transform_empty_input():
    tables, stats = t.transform([])
    assert stats["after_cleaning"] == 0
    assert len(tables["offense_types"]) == 5
