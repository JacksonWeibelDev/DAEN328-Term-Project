# NCVS Select – Personal Victimization: Codebook & Cleaning Decisions

Source: BJS, *Codebooks for NCVS Select – Personal Population and Personal Victimization, Legacy Version, 1993–2024*
https://bjs.ojp.gov/document/NCVS_Select_person_level_codebook.pdf

Every column except `idper`, `yearq`, `year` and the two weights is a numeric **code**. The API returns them as
strings (e.g. `"98"`). The labels below are copied from the codebook. A "Proposed handling" is a draft transform
decision for the team to confirm.

## Sentinel / "missing" codes

Three different kinds of non-answer are mixed into the same columns. They are **not** all the same thing, so they
should not all be collapsed into one NULL.

| Code | Codebook meaning | Kind | Proposed handling |
|------|------------------|------|-------------------|
| `-1` / `-2` | "Invalid until <date>" (question not asked yet) | Structural: variable didn't exist that year | NULL |
| `98` | "Residue" (respondent didn't answer / unusable) | Genuine missing | NULL (or an explicit `Unknown` label) |
| `3` / `4` / `5` in some cols | "Do not know" / "Unknown" | A real answer, not missing | **Keep** as its own category |
| `0` in `popsize` | "Not a place" | Real value | Keep |
| `-1` in `veteran` | "Under age 18" | **Real value, not missing** | Keep (or label `Under 18`) |
| `99` | "Out of universe" | Structural | Documented but does **not** occur in this victimization file |

Caution: `veteran = -1` means "Under age 18", but in every other column `-1` means "invalid until <date>". A blanket
`replace(-1, NULL)` would be wrong for `veteran`.

## Column reference

### Respondent columns (→ `respondents`)

| Column | Meaning | Codes |
|--------|---------|-------|
| `idper` | Unique person ID | text identifier (27 digits, do **not** convert to number) |
| `yearq` | Year and quarter collected | `YYYY.Q` (e.g. `1993.4`) |
| `year` | Collection year | 1993–2024 |
| `ager` | Age group | 1=12-17, 2=18-24, 3=25-34, 4=35-49, 5=50-64, 6=65+ |
| `sex` | Sex | 1=Male, 2=Female |
| `hispanic` | Hispanic origin | 1=Hispanic, 2=Non-Hispanic, 98=Residue |
| `race` | Race | 1=White, 2=Black, 3=Am. Indian/Alaska Native, 4=Asian/NH/Other Pacific Islander, 5=More than one |
| `race_ethnicity` | Race + Hispanic origin | 1=NH white, 2=NH black, 3=NH AI/AN, 4=NH Asian/NHPI, 5=NH more than one, 6=Hispanic |
| `hincome1` | Household income (bands) | 1=<$7.5k, 2=$7.5–15k, 3=$15–25k, 4=$25–35k, 5=$35–50k, 6=$50–75k, 7=$75k+, 98=Residue |
| `hincome2` | Imputed income (from 2017 Q1) | -1=Invalid until 2017 Q1, 1=<$25k, 2=$25–50k, 3=$50–100k, 4=$100–200k, 5=$200k+ |
| `marital` | Marital status | 1=Never married, 2=Married, 3=Widowed, 4=Divorced, 5=Separated, 98=Residue |
| `popsize` | Population size of place (from 1995 Q3) | -1=Invalid until 1995 Q3, 0=Not a place, 1=<100k, 2=100–249k, 3=250–499k, 4=500–999k, 5=1M+ |
| `region` | Census region (from 1995 Q3) | -1=Invalid until 1995 Q3, 1=Northeast, 2=Midwest, 3=South, 4=West |
| `msa` | Location of residence (MSA) | 1=Principal city within MSA, 2=Not principal city within MSA, 3=Outside MSA |
| `locality` | Locale (from 2020 Q1) | -1=Invalid until 2020 Q1, 1=Urban, 2=Suburban, 3=Rural |
| `educatn1` | Education | 1=None, 2=Grade school, 3=Middle school, 4=High school, 5=College, 98=Residue |
| `educatn2` | Education detail (from 2003 Q1) | -1=Invalid until 2003 Q1, 1=None, 2=Grade, 3=Middle, 4=Some HS, 5=HS grad, 6=Some college/assoc., 7=Bachelor's, 8=Advanced, 98=Residue |
| `veteran` | Veteran status (from 2017 Q1) | -2=Invalid until 2017 Q1, -1=Under 18, 0=Not a veteran, 1=Veteran, 98=Residue |
| `citizen` | Citizenship (from 2017 Q1) | -1=Invalid until 2017 Q1, 1=Born US citizen, 2=Naturalized, 3=Non-US citizen, 98=Residue |

### Offense columns (→ `offense_types`)

| Column | Meaning | Codes |
|--------|---------|-------|
| `newoff` | Type of crime | 1=Rape/sexual assault, 2=Robbery, 3=Aggravated assault, 4=Simple assault, 5=Personal theft/larceny |
| `newcrime` | Aggregate type | 1=Violent crime, 2=Personal theft/larceny |
| `seriousviolent` | Violent excl. simple assault | 1=Violent excl. simple assault, 2=Simple assault, 3=Personal theft/larceny |

`offense_name` for the Offense Types table is the `newoff` label above. There are only 5 rows. This is the hand-written lookup
the Phase 1 report referred to, and it now comes straight from the codebook. `newcrime` and `seriousviolent` are fully determined by
`newoff` (1–4→newcrime 1; 5→newcrime 2; seriousviolent is 1 for 1–3, 2 for 4, 3 for 5). Verified against the data: no exceptions,
so Offense Types is a clean 3NF table.

### Victimization columns (→ `victimizations`)

| Column | Meaning | Codes |
|--------|---------|-------|
| `notify` | **Reported to police** (key analysis variable) | 1=Yes, 2=No, 3=Do not know, 98=Residue |
| `vicservices` | Got help from victim services | 1=Yes, 2=No, 3=Do not know, 98=Residue |
| `locationr` | Where it happened | 1=Near victim's home, 2=Near friend/neighbor/relative's home, 3=Commercial/parking/public area, 4=School, 5=Other |
| `direl` | Victim–offender relationship | 1=Intimates, 2=Other relatives, 3=Well known/casual acquaintance, 4=Strangers, 5=Do not know relationship, 6=Do not know number of offenders |
| `weapon` | Weapon present | 1=Yes, 2=No, 3=Do not know |
| `weapcat` | Weapon type | 0=No weapon, 1=Firearm, 2=Knife, 3=Other, 4=Type unknown, 5=Do not know if offender had weapon |
| `injury` | Injured | 0=Not injured, 1=Injured (**98 also occurs, see below**) |
| `serious` | Type of injury | 1=No injury, 2=Serious injury, 3=Minor injury, 4=Rape w/o other injuries, 98=Residue |
| `treatment` | Medical treatment | 0=Not injured, 1=Not treated, 2=Treated, 3=Do not know, 98=Residue |
| `offenderage` | Offender age | 1=≤11, 2=12-17, 3=18-29, 4=30+, 5=Multiple of various ages, 98=Residue |
| `offendersex` | Offender sex | 1=Male, 2=Female, 3=Both, 4=Unknown, 98=Residue |
| `offtracenew` | Offender race/ethnicity (from 2012 Q1) | -1=Invalid until 2012 Q1, 1=NH white, 2=NH black, 3=NH AI/AN, 4=NH Asian/NHPI, 5=NH more than one, 6=Hispanic, 7=Unknown, 10=Mixed group, 11=Unknown number of offenders |
| `wgtviccy` | Annual victimization weight | numeric |
| `series` | Series crime | 1=Not a series crime, 2=Series crime |
| `newwgt` | Series-adjusted victimization weight | numeric |

Weights: use `newwgt` for national estimates, since it adjusts for series crimes. For the "reported vs. unreported" questions,
the dashboard should compute **weighted** percentages (`SUM(newwgt)`), not raw row counts. This is a major point for whoever builds the dashboard queries.

### Columns NOT in the codebook

`pseudostratum`, `secucode`: these are in the API data but undocumented in this codebook (they look like variance-estimation design variables).
`pseudostratum = 999` and `secucode = 9` both occur in the same 3,053 rows, which suggests a not-available marker.
They are not needed for the five dashboard questions. **Proposed: drop them** (and say so in the summary).
`:id`, `:created_at`, `:updated_at` are Socrata system fields. Keep `:id` (as `victimization_id`) and `:updated_at` for the incremental pull.

## Findings from checking the raw data (68,852 rows) against this codebook

1. **All values match the codebook, except `injury = 98`** (4 rows). The codebook lists only 0/1. Treat as Residue → NULL.
2. **True blanks (empty string): `weapcat` ×2, `treatment` ×4.** All are in 2022–2024, so likely a side effect of the 2023–24 instrument
   change. These are the only real gaps. Row context to guide a fill:
   - `weapon=2` rows with blank `weapcat` → can be inferred as `0` (No weapon). In the data, `weapon=2` is *always* paired with `weapcat=0` (0 exceptions).
   - `injury=0` is *always* paired with `treatment=0` (0 exceptions), so a blank `treatment` where `injury=0` can be inferred as `0` (Not injured).
   - Otherwise leave NULL. Don't guess.
   - **Update after implementing:** none of the 6 blank rows actually has `weapon=2` or `injury=0`, so the two fill rules change nothing on the
     current data (they report 0 filled). They stay in `transform.py` as safeguards for future pulls. All 6 stay NULL.
   - The API omits a key when a value is null, so these arrive as absent keys, not empty strings. `transform.py` handles both.
3. **Structural -1/-2 volume.** `hincome2` and `citizen` are -1 for 53,067 rows (all pre-2017); `locality` for 60,034 (pre-2020);
   `veteran` -2 for pre-2017 rows. They are structurally unavailable for old years, not bad data. Mapping to NULL is right,
   but a dashboard that uses these columns can only cover recent years. Use `hincome1` and `educatn1`, which span all years.
4. **`popsize` / `region` -1 are not purely year-bound.** They are -1 for 12,625 rows, but 349 rows from 1993–1995 have valid values. That matches "invalid until 1995 Q3":
   verified, valid values in 1993–1995 appear only in 1995.3 and 1995.4. Region is needed for dashboard Q5 (age group × region), so
   **~12.6k early rows will have NULL region.** The dashboard should exclude or label them.
5. **Respondent key is safe.** In this file, 57,806 distinct respondent attribute rows map to 57,806 distinct `(idper, yearq)` keys, so no conflicting
   attributes for the same key.
6. **Weights are clean.** All `wgtviccy` / `newwgt` are numeric and > 0.

## Open questions for the team

- **Exact duplicate rows (3,341 extra copies, in 5,823 rows):** identical in every column except the Socrata `:id`. I checked whether
  series crimes explain them: they don't. Only 20 of the 3,341 have `series = 2`. They are probably several separate, identical-looking
  incidents reported by one person in a quarter (the file has no incident ID to tell them apart), not API duplicates. The Socrata `:id`
  is unique for each, so the pipeline's UPSERT will never collapse them. **Decision needed:** drop them (the assignment rewards "duplicates removed",
  but we'd be deleting plausibly real records, which would bias counts slightly) or keep them and report 0 duplicates by `:id`.
- **NULL vs. labeled "Unknown" for Residue (98):** NULL keeps the types clean (SMALLINT), but a label keeps the row visible in charts. Choice affects the schema.
- **Store codes or labels?** Suggest storing SMALLINT codes in the tables, with lookup/dimension tables or a mapping in the dashboard for labels.
  This keeps the tables narrow and is easy to defend as normalized.
