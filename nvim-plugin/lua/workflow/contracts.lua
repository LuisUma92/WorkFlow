-- lua/workflow/contracts.lua
-- EmmyLua type annotations for all `workflow` CLI `--json` response shapes.
-- No runtime behaviour — import for type checking / documentation only.
-- Source of truth: src/workflow/notes/formatters.py, notes/sync.py, notes/cli.py

---@class WorkflowNoteJSON
---@field id string              NanoID zettel identifier
---@field title string|nil       Human-readable title from frontmatter
---@field type string|nil        Note type (fleeting | permanent | structure | …)
---@field tags string[]          Tag list (may be empty)
---@field concepts string[]      Concept code slugs (may be empty)
---@field path string            Absolute filesystem path to the .md file

---@class WorkflowEdgeJSON
---@field id integer             DB primary key of NoteEdge row
---@field source_id integer      DB id of source Note row
---@field source_zettel_id string|nil  zettel_id of source note (if resolved)
---@field target_zettel_id string|nil  zettel_id of target note
---@field edge_class string      "structural" | "semantic" | …
---@field relation_type string   e.g. "supports", "refutes", "elaborates"
---@field weight number          Float edge weight (default 1.0)
---@field rationale string|nil   Free-text explanation

---@class WorkflowSyncReportJSON
---@field notes_scanned integer
---@field labels_registered integer
---@field links_created integer
---@field citations_registered integer
---@field edges_created integer
---@field orphans_dropped integer
---@field concept_links_created integer
---@field concept_issues table[]   Array of {note_id, code, reason} dicts
---@field dry_run boolean

---@class WorkflowEdgesCycleJSON
---@field cycles string[][]   Array of cycle paths, each path is a list of zettel_id strings

---@class WorkflowTopicJSON
---@field id integer                 DB primary key
---@field discipline_area_code string  Code of the parent DisciplineArea
---@field name string                Topic name
---@field serial_number integer      Topic serial number within the discipline area

---@class WorkflowContentJSON
---@field id integer       DB primary key
---@field topic_id integer  FK to parent Topic
---@field name string       Content name

---@class WorkflowConceptJSON
---@field id integer              DB primary key
---@field code string             Unique slug identifier
---@field label string            Human-readable label
---@field content_id integer      FK to parent Content
---@field domain string           Taxonomy domain (Información | Procedimiento Mental | Procedimiento Psicomotor | Metacognitivo)
---@field parent_id integer|nil   FK to parent Concept (nil if root)
---@field description string|nil  Optional free-text description

---@class WorkflowBibLinkJSON
---@field content_id integer          FK to parent Content
---@field bib_entry_id integer        FK to BibEntry row
---@field bib_entry_bibkey string     BibTeX cite key (e.g. "Smith2020")
---@field chapter_number integer|nil  Chapter locus (nil if unset)
---@field section_number integer|nil  Section locus (nil if unset)
---@field first_page integer|nil      First page of the referenced locus
---@field last_page integer|nil       Last page of the referenced locus
---@field first_exercise integer|nil  Optional exercise range start
---@field last_exercise integer|nil   Optional exercise range end

local M = {}

return M
