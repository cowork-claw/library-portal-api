# Removed Scripts Archive Log

This document preserves the implementation logic of scripts that were removed after the data organization was complete.

## Summary of Removed Files

| File | Purpose | Status |
|------|---------|--------|
| `organize_papers_hierarchical.py` | Organize raw papers into hierarchical folders | Data organized ✅ |
| `merge_unclassified.py` | Move unclassified papers to correct branches | Merged ✅ |
| `cleanup_migration.py` | Migrate misclassified papers, normalize codes | Migrated ✅ |
| `fix_semesters.py` | Fix semester data based on course code patterns | Fixed ✅ |

---

## 1. organize_papers_hierarchical.py (336 lines)

### Purpose

Organize papers from raw JSON into hierarchical folder structure.

### Key Implementation Logic

#### Branch Normalization Map

```python
BRANCH_NORMALIZATION = {
    "Aeronautical": "Aeronautical",
    "Biomedical": "Biomedical", 
    "Biotechnology": "Biotechnology",
    "Chemical": "Chemical",
    "Civil": "Civil",
    "Computer Science": "CSE",
    "DataScience": "CSE",  # Merged into CSE
    "ECE": "ECE",
    "EEE": "EEE",
    ...
}
```

#### CS vs Non-CS First Year Detection

```python
# CS Stream: Course codes ending in 02 (e.g., MAT1102, PHY1002)
CS_FIRST_YEAR_CODE_PATTERN = re.compile(r'^[A-Z]{2,3}1[0-2]02$')

# Non-CS Stream: Codes ending in 71/72 (e.g., MAT1171, PHY1071)
NON_CS_FIRST_YEAR_CODE_PATTERN = re.compile(r'^[A-Z]{2,3}1[0-7]7[12]$')
```

#### Output Structure Created

```
organized/
├── btech/
│   ├── branches/{BRANCH}.json
│   ├── first_year/cs_stream.json
│   ├── first_year/non_cs_stream.json
│   └── common_electives.json
├── masters/{mtech,me,mca}.json
├── bsc/icas.json
└── other.json
```

---

## 2. merge_unclassified.py (164 lines)

### Purpose

Move papers from unclassified.json to correct branch files based on course code prefixes.

### Key Implementation Logic

#### Prefix to Branch Mapping

```python
PREFIX_TO_BRANCH = {
    'AAE': 'Aeronautical',
    'BIO': 'Biotechnology',
    'BME': 'Biomedical',
    'CHE': 'Chemical',
    'CSE': 'CSE',
    'DSE': 'CSE',
    'ECE': 'ECE',
    'ELE': 'EEE',
    'ICE': 'EIE',
    'ICT': 'CSE',
    'MED': 'MediaPrint',
    'MTE': 'Mechatronics',
}

FIRST_YEAR_PREFIXES = {'MAT', 'PHY', 'CHM', 'HUM', 'CIE', 'MIE'}
```

#### Year Extraction from Code

```python
def get_year_from_code(code: str) -> int:
    prefix = ''.join(c for c in code if c.isalpha())
    if len(code) > len(prefix):
        return int(code[len(prefix)])
    return 0
```

---

## 3. cleanup_migration.py (369 lines)

### Purpose

Three-phase cleanup: migrate misclassified papers, normalize duplicates, remove junk.

### Key Implementation Logic

#### Phase 1: Move First-Year Papers with Semester > 2

```python
# If year digit > 1 in course code, move to common_electives
match = re.match(r'^([A-Z]{2,4})(\d+)$', code_clean)
if match:
    year_digit = int(num_part[0])
    if year_digit > 1:
        should_move = True
```

#### Phase 2: Normalize Duplicate Course Codes

```python
normalization_map = {
    "MAT2251": ("MAT22XX", "Engineering Mathematics IV"),
    "MAT2252": ("MAT22XX", "Engineering Mathematics IV"),
    # ... all MAT22XX variants
    "HUM305": ("HUM3051", "Engineering Economics and Financial Management"),
}
```

#### Phase 3: ICAS Semester Logic

```python
# ICAS codes follow I + PREFIX pattern
# ICS111 -> Year 1, ICS233 -> Year 2
# Semester = (year_digit - 1) * 2 + (1 or 2)
```

---

## 4. fix_semesters.py (206 lines)

### Purpose

Correct semester assignments based on course code pattern from curriculum.

### Key Implementation Logic

#### Course Code Pattern

```
PREFIX + XYZW
Where:
- X = Year (1-5)
- Y = Semester type (1=odd, 2=even, 0/7=first year variants)

Mapping:
- 1X71/72 → Sem 1/2 (First Year Non-CS)
- 21XX → Sem 3
- 22XX → Sem 4
- 31XX → Sem 5
- 32XX → Sem 6
- 40/41XX → Sem 7
- 42XX → Sem 8
```

#### Core Function

```python
def get_semester_from_code(code: str) -> int:
    match = re.match(r'^([A-Z]{2,4})(\d+)$', code)
    year_digit = int(num_part[0])
    sem_type_digit = int(num_part[1])
    
    if year_digit == 2:
        return 3 if sem_type_digit == 1 else 4
    elif year_digit == 3:
        return 5 if sem_type_digit == 1 else 6
    elif year_digit == 4:
        return 7 if sem_type_digit < 2 else 8
```

---

## Removed JSON Files (Archive)

| File | Size | Purpose |
|------|------|---------|
| `question_papers.json` | 1.5MB | Original raw scraped data |
| `mapped_papers_2022_plus.json` | 742KB | Filtered 2022+ papers |
| `btech_by_branch.json` | 846KB | B.Tech papers grouped by branch |
| `icas_papers_mapped.json` | 496KB | B.Sc ICAS papers |

**Total Removed: ~3.6MB**

---

## Final Data Location

All processed data now resides in:

```
data/classified/organized/
├── btech/branches/*.json
├── btech/first_year/*.json
├── btech/common_electives.json
├── masters/*.json
├── bsc/icas.json
└── other.json
```

**Total: 337 courses, 783 papers**
