# Known Limitations

State these BEFORE an interviewer finds them. Naming your data weaknesses
unprompted is a senior signal; being caught hiding them is fatal.

## Lending Club
- Accepted file is a SNAPSHOT (one row per loan), not a monthly panel. Duration
  is reconstructed from issue_d -> last_pymnt_d and is therefore approximate.
- `Risk_Score` is FICO before 2013-11-05 and VantageScore after. Two scales in one column.
- Only ~5-6 features are shared between accepted and rejected files, which caps
  how good reject inference can be here.
- Platform-specific selection: these are LC applicants, not the general credit population.

## Freddie Mac
- Agency-conforming universe only. NOT representative of subprime.
- Actual Loss populated only for zero balance codes 02, 03, 09, 15.
- Modification costs excluded from the published loss field.
- Loss null for loans disposed within three months.
- Sample dataset means thin coverage in rare segments.

## Modelling
- (fill in as you go - do not leave this until the last week)