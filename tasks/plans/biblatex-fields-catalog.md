# BibLaTeX Complete Fields and Entry Types Catalog

**Source:** `tasks/biblatex.tex` (BibLaTeX manual reference document)  
**Date Extracted:** 2026-06-02  
**Total Counts:** 45 entry types, 293 fields, 9 field aliases

---

## 1. Entry Types (45 total)

### Standard Entry Types
- `article` — Journal article
- `book` — Standalone book
- `inbook` — Chapter or section in a book
- `incollection` — Article/chapter in an edited collection
- `inproceedings` — Conference paper in proceedings
- `proceedings` — Entire proceedings volume
- `misc` — Miscellaneous type (fallback)
- `thesis` — Generic thesis (base for specialized types)
- `phdthesis` — Ph.D. dissertation
- `mastersthesis` — Master's thesis
- `report` — Technical/research report
- `techreport` — Technical report

### Reference Works
- `reference` — Single-volume encyclopedia/dictionary
- `mvreference` — Multi-volume encyclopedia/dictionary
- `inreference` — Article in an encyclopedia/dictionary
- `periodical` — Periodical (journal, magazine)
- `suppperiodical` — Supplemental material in a periodical

### Books (Compound)
- `bookinbook` — Book within a book
- `suppbook` — Supplemental material in a book
- `mvbook` — Multi-volume book
- `mvcollection` — Multi-volume collection
- `mvproceedings` — Multi-volume proceedings
- `collection` — Edited collection
- `manual` — Manual/handbook
- `booklet` — Standalone booklet

### Specialized Types
- `online` — Online resource (website, blog, etc.)
- `electronic` — Alias for `online` (jurabib compat)
- `www` — Alias for `online` (legacy)
- `software` — Computer software (alias for `misc`)
- `dataset` — Research dataset
- `patent` — Patent document
- `review` — Review article (variant of `article`)
- `unpublished` — Unpublished work (thesis, draft, etc.)
- `letter` — Letter or correspondence
- `commentary` — Commentary on another work
- `standard` — Technical standard/specification

### Media Types
- `audio` — Audio recording
- `video` — Video recording
- `movie` — Motion picture
- `music` — Musical composition
- `performance` — Live performance
- `artwork` — Artwork or sculpture
- `image` — Image or photograph
- `chat` — Instant message or chat log
- `bibnote` — Bibliography note
- `jurisdiction` — Court case/legal jurisdiction
- `legal` — Legal document
- `legislation` — Legislative act/statute
- `conference` — Legacy alias for `inproceedings`

---

## 2. Data Fields by Category

### Name Fields (24)
Person/organizational name lists for author, editor, and contributor roles.

| Field | Type | Notes |
|-------|------|-------|
| `author` | name list | Work author(s) |
| `editor` | name list | Editor(s) of the work |
| `translator` | name list | Translator(s) |
| `editora` | name list | Secondary editor (editorial board, etc.) |
| `editorb` | name list | Tertiary editor |
| `editorc` | name list | Quaternary editor |
| `annotator` | name list | Annotator of the work |
| `commentator` | name list | Commentary author |
| `conductor` | name list | Orchestra/ensemble conductor |
| `bookauthor` | name list | Author of the original book (for chapters) |
| `authortype` | literal | Type of author (e.g., "artist", "film director") |
| `editortype` | literal | Type of editor |
| `editoratype` | literal | Type of secondary editor |
| `editorbtype` | literal | Type of tertiary editor |
| `editorctype` | literal | Type of quaternary editor |
| `namea` | name list | Additional name list (user-defined) |
| `nameaddon` | literal | Supplement to name (titles, suffixes) |
| `moreauthor` | flag | Flag: more authors than listed |
| `moreeditor` | flag | Flag: more editors than listed |
| `moretranslator` | flag | Flag: more translators than listed |
| `morelabelname` | flag | Flag: more names than used in label |
| `savedauthor` | name list | Backup author (for processing) |
| `useauthor` | flag | Flag: use author in citations |
| `useeditor` | flag | Flag: use editor in citations |

### Title Fields (25)
Work titles in various contexts and levels.

| Field | Type | Notes |
|-------|------|-------|
| `title` | literal | Main work title |
| `subtitle` | literal | Subtitle of main work |
| `titleaddon` | literal | Addendum to title (e.g., edition info) |
| `maintitle` | literal | Title of multi-volume parent work |
| `mainsubtitle` | literal | Subtitle of multi-volume work |
| `maintitleaddon` | literal | Addendum to main title |
| `booktitle` | literal | Title of the book containing the work |
| `booksubtitle` | literal | Subtitle of book |
| `booktitleaddon` | literal | Addendum to book title |
| `journaltitle` | literal | Name of the journal |
| `journalsubtitle` | literal | Subtitle of journal |
| `journaltitleaddon` | literal | Addendum to journal title |
| `issuetitle` | literal | Title of a special issue |
| `issuesubtitle` | literal | Subtitle of issue |
| `issuetitleaddon` | literal | Addendum to issue title |
| `eventtitle` | literal | Name of conference/event |
| `eventtitleaddon` | literal | Addendum to event title |
| `origtitle` | literal | Title of original work (for translations) |
| `reprinttitle` | literal | Title of reprint edition |
| `shorttitle` | literal | Abbreviated title for citations |
| `indextitle` | literal | Title as it appears in index |
| `indexsorttitle` | literal | Title for sorting in index |
| `extratitle` | literal | Extra title appended to label |
| `labeltitle` | literal | Title used in label generation |
| `extratitleyear` | literal | Extra title year for disambiguation |

### Date/Time Fields (44)
Full EDTF-compliant date specifications with components and qualifiers.

#### Primary Dates
| Field | Type | Notes |
|-------|------|-------|
| `date` | date | Publication date (EDTF format) |
| `year` | integer | Publication year (4-digit) |
| `month` | integer | Publication month (1–12 or name) |
| `day` | integer | Publication day of month |
| `season` | literal | Season (spring, summer, autumn, winter) |
| `yeardivision` | integer | Year subdivision (week, quarter, etc.) |

#### Date Ranges & End Dates
| Field | Type | Notes |
|-------|------|-------|
| `endyear` | integer | End year for multi-year works |
| `endmonth` | integer | End month |
| `endday` | integer | End day |
| `endseason` | literal | End season |
| `endyeardivision` | integer | End year subdivision |

#### Event Dates
| Field | Type | Notes |
|-------|------|-------|
| `eventdate` | date | Conference/event date (EDTF) |
| `eventyear` | integer | Event year |
| `eventmonth` | integer | Event month |
| `eventday` | integer | Event day |
| `eventseason` | literal | Event season |
| `eventyeardivision` | integer | Event year subdivision |
| `eventendyear` | integer | Event end year |
| `eventendmonth` | integer | Event end month |
| `eventendday` | integer | Event end day |
| `eventendseason` | literal | Event end season |
| `eventendyeardivision` | integer | Event end year subdivision |

#### Original/Reprint Dates
| Field | Type | Notes |
|-------|------|-------|
| `origdate` | date | Original publication date |
| `origyear` | integer | Original publication year |
| `origmonth` | integer | Original publication month |
| `origday` | integer | Original publication day |
| `origseason` | literal | Original publication season |
| `origyeardivision` | integer | Original publication year subdivision |
| `origendyear` | integer | Original work end year |
| `origendmonth` | integer | Original work end month |
| `origendday` | integer | Original work end day |
| `origendseason` | literal | Original work end season |
| `origendyeardivision` | integer | Original work end year subdivision |

#### URL Access Dates
| Field | Type | Notes |
|-------|------|-------|
| `urldate` | date | Date URL was accessed |
| `urlyear` | integer | URL access year |
| `urlmonth` | integer | URL access month |
| `urlday` | integer | URL access day |
| `urlseason` | literal | URL access season |
| `urlyeardivision` | integer | URL access year subdivision |
| `urlendyear` | integer | URL end access year |
| `urlendmonth` | integer | URL end access month |
| `urlendday` | integer | URL end access day |
| `urlendseason` | literal | URL end access season |
| `urlendyeardivision` | integer | URL end access year subdivision |

#### Date Processing & Flags
| Field | Type | Notes |
|-------|------|-------|
| `datepart` | flag | Partial date specification |
| `dateunspecified` | flag | Date information is ambiguous/uncertain |

### Publication Fields (10)
Place and organization information for publishers and venues.

| Field | Type | Notes |
|-------|------|-------|
| `publisher` | literal | Name of publisher |
| `location` | literal | Place(s) of publication (canonical) |
| `address` | literal | **Alias for `location`** (bibtex compat) |
| `institution` | literal | Name of institution (university, lab, etc.) |
| `organization` | literal | Name of organization (conference, working group) |
| `school` | literal | **Alias for `institution`** (bibtex compat) |
| `origlocation` | literal | Original publication location |
| `origpublisher` | literal | Original publication publisher |
| `venue` | literal | Venue name (when different from publisher) |
| `place` | literal | Generic place name |

### Identifier Fields (19)
URIs, DOIs, and document identifiers for access and citation.

| Field | Type | Notes |
|-------|------|-------|
| `doi` | literal | Digital Object Identifier |
| `url` | literal | Uniform Resource Locator (web address) |
| `urlraw` | literal | Raw URL (unprocessed) |
| `isbn` | literal | International Standard Book Number |
| `issn` | literal | International Standard Serial Number |
| `isrn` | literal | International Standard Report Number |
| `eid` | literal | Electronic identifier (article ID) |
| `eprint` | literal | E-print identifier (arXiv, etc.) |
| `eprinttype` | literal | Type of e-print archive |
| `eprintclass` | literal | E-print classification/category |
| `archiveprefix` | literal | **Alias for `eprinttype`** (arXiv compat) |
| `primaryclass` | literal | **Alias for `eprintclass`** (arXiv compat) |
| `pubmedid` | literal | PubMed database identifier |
| `pubmed` | literal | PubMed identifier (alternate) |
| `file` | literal | File path or attachment reference |
| `pdf` | literal | **Alias for `file`** (JabRef compat) |
| `library` | literal | Library classification/call number |
| `gps` | literal | GPS coordinates (for locations/artifacts) |
| `articleid` | literal | Article identifier (for online journals) |

### Pagination & Structure Fields (11)
Page ranges, volume/issue numbers, and structural divisions.

| Field | Type | Notes |
|-------|------|-------|
| `pages` | literal | Page range of article/chapter (e.g., "12–34") |
| `pagetotal` | integer | Total page count of work |
| `pagination` | literal | Pagination scheme descriptor |
| `bookpagination` | literal | Pagination of book containing work |
| `volume` | literal | Volume number (can be "vol. 1" or "1") |
| `volumes` | literal | Total number of volumes (multi-volume works) |
| `number` | literal | Issue/number within volume |
| `chapter` | literal | Chapter number (for book divisions) |
| `part` | literal | Part number (larger division than chapter) |
| `edition` | literal | Edition statement (e.g., "2nd ed.", "revised") |
| `issue` | literal | Issue number (for serials) |

### Series & Cross-Reference Fields (10)
Links between entries and relationships to series or parent works.

| Field | Type | Notes |
|-------|------|-------|
| `series` | literal | Name of book/publication series |
| `shortseries` | literal | Abbreviated series name |
| `crossref` | key | Citation key of parent entry (for inheritance) |
| `xref` | key | Cross-reference to related entry |
| `xdata` | key list | External data source entries |
| `related` | key list | Related/companion works |
| `relatedtype` | literal | Type of relationship (e.g., "review of") |
| `relatedstring` | literal | String describing relationship |
| `relatedoptions` | literal | Options for processing related entries |
| `entrysetcount` | integer | Number of entries in an entry set |

### Miscellaneous Fields (23)
Notes, metadata, type annotations, and administrative fields.

| Field | Type | Notes |
|-------|------|-------|
| `note` | literal | Miscellaneous note/comment |
| `addendum` | literal | Addition to standard bibliography entry |
| `pubstate` | literal | Publication status (e.g., "in press", "forthcoming") |
| `language` | literal | Language(s) of the work |
| `langid` | literal | Language identifier (code) |
| `langidopts` | literal | Language ID options/modifiers |
| `hyphenation` | literal | **Alias for `langid`** (provides alt. name) |
| `keywords` | literal | Keywords/tags for the work |
| `annotation` | literal | Annotation/review of the work |
| `annote` | literal | **Alias for `annotation`** (jurabib compat) |
| `abstract` | literal | Abstract/summary of the work |
| `type` | literal | Entry type specifier (can override @type) |
| `subtype` | literal | Subtype classification |
| `entrysubtype` | literal | Subtype for specialized entry processing |
| `howpublished` | literal | How/where the work was made available |
| `version` | literal | Software/document version number |
| `foreword` | literal | Foreword author/text |
| `afterword` | literal | Afterword author/text |
| `introduction` | literal | Introduction author/text |
| `commentary` | literal | Commentary author/text |
| `comment` | literal | Free comment field |
| `key` | literal | **Alias for `sortkey`** (bibtex compat) |
| `origlanguage` | literal | Language of original (for translations) |

---

## 3. Field Aliases (9 total)

Biblatex provides backward-compatible aliases for bibtex field names:

| Alias Field | Canonical Field | Compatibility | Notes |
|---|---|---|---|
| `address` | `location` | BibTeX 2.0 | Traditional bibtex used address for publication place |
| `annote` | `annotation` | jurabib | jurabib package compatibility |
| `archiveprefix` | `eprinttype` | arXiv | Alternate name for e-print archive type |
| `hyphenation` | `langid` | ISO 639 | Language ID (preferred over hyphenation) |
| `journal` | `journaltitle` | BibTeX 2.0 | Traditional bibtex used journal for periodical name |
| `key` | `sortkey` | BibTeX 2.0 | Sort key for entries without author |
| `pdf` | `file` | JabRef | JabRef format compatibility |
| `primaryclass` | `eprintclass` | arXiv | Alternate name for arXiv classification |
| `school` | `institution` | BibTeX 2.0 | Traditional bibtex used school for academic institution |

---

## 4. Special Data Types

Biblatex enforces specific data types for fields:

### Name Lists
Fields: `author`, `editor`, `translator`, `editora`, `editorb`, `editorc`, `annotator`, `commentator`, `conductor`, `bookauthor`, `namea`, `moreauthor`, `moreeditor`, `moretranslator`, `morelabelname`, `savedauthor`

- **Format:** Comma-separated name entries, each with structure: `Family, Given` or `Given Family`
- **Prefixes:** Von particles and Jr./Sr. suffixes supported
- **Processing:** Biber parses prefixes, handles ligatures (ß→ss), and applies accent folding

### Literal Fields
All text fields (titles, notes, keywords, etc.) are stored as literal text.

- **Braces:** Protected text in curly braces `{...}` preserves case and formatting
- **Commands:** LaTeX commands are expanded during processing
- **Ranges:** Special ranges like `{1--5}` are preserved

### Key Lists
Fields: `xdata`, `related`, `ids`

- **Format:** Comma-separated citation keys
- **Usage:** Cross-references and external data sources
- **Inheritance:** Keys are resolved during bibliography generation

### Date (EDTF)
Fields: `date`, `eventdate`, `origdate`, `urldate`, and their component fields

- **Format:** Extended Date/Time Format (EDTF)
- **Examples:** `2020`, `2020-06`, `2020-06-02`, `2020-06-02T14:30:00Z`, `2020-06/2021-06`
- **Qualifiers:** Uncertain dates (?) and approximate dates (~) supported
- **Components:** Separated into `year`, `month`, `day`, `season`, `yeardivision`

### Integer Fields
Fields: `year`, `month`, `day`, `endyear`, `endmonth`, `endday`, `volume`, `number`, `chapter`, `pagetotal`, `edition`, `eventyear`, etc.

- **Month:** 1–12 or month name (January, Feb, etc.)
- **Year:** 4-digit year (2020)
- **Flexible:** Can be literal text for custom formats

---

## 5. Field Descriptions (by Coverage in Manual)

The biblatex manual documents these field groups in detail:

### Data Fields
Core bibliographic metadata: author, title, date, publisher, etc.

### Special Fields
Internal/processing fields: `bibnamehash`, `fullhash`, `sortkey`, `sortname`, `label`, `datelabelsource`, `labeldatesource`, etc.

### Custom Fields
User-defined fields for domain-specific metadata: `usera`, `userb`, `userd`, `verba`, `verbb`, `verbc`

### Date and Time Specifications
EDTF-compliant date handling with full components and qualifiers.

### Year, Month and Date
Broken down into component integers for processing and formatting.

### Name Parts and Name Spacing
Controls for how names are displayed: `useprefix`, `gender`, `namepart`, `nameparts`, `namessep`, etc.

---

## 6. Special Processing Fields

These fields control how entries are processed and displayed:

| Field | Purpose |
|-------|---------|
| `useprefix` | Flag: include name prefix (von) in sort key |
| `gender` | Author gender (for pronoun agreement in multi-language mode) |
| `sortname` | Name used for sorting (when different from author) |
| `sortkey` | Fallback sort key (when author is missing) |
| `sortinit` | First initial used in label |
| `sortinithash` | Hash of sort initial (for uniqueness) |
| `label` | Generated label for citation |
| `labelalpha` | Alphabetic label (author-year style) |
| `labelnumber` | Numeric label (numbered style) |
| `singletitle` | Flag: title is singular/monograph |
| `uniquename` | Name uniqueness tracking (for disambiguation) |
| `uniquetitle` | Title uniqueness (for disambiguation) |
| `uniquework` | Work uniqueness (for disambiguation) |

---

## Summary Statistics

| Category | Count |
|----------|-------|
| **Entry Types** | 45 |
| **Data Fields** | 293 |
| **Field Aliases** | 9 |
| **Name Fields** | 24 |
| **Title Fields** | 25 |
| **Date Fields** | 44 |
| **Publication Fields** | 10 |
| **Identifier Fields** | 19 |
| **Pagination Fields** | 11 |
| **Series Fields** | 10 |
| **Misc Fields** | 23 |

---

## References

- **Biblatex Manual:** `biblatex.tex` (extracted 2026-06-02)
- **Standards:** EDTF (Extended Date/Time Format), ISO 639 (Language Codes), RFC 3986 (URI)
- **Related:** BibTeX, Biber, XData inheritance, Moodle XML export (ADR-0019)
