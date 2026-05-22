"""
ORM model exports for workflow.db.
"""

from __future__ import annotations

from workflow.db.models.bibliography import (
    Author,
    AuthorType,
    BibAuthor,
    BibEntry,
    BibEntryTag,
    BibKeyword,
    BibTag,
    BibUrl,
    IsnType,
    ReferencedDatabase,
)
from workflow.db.models.academic import (
    Institution,
    MainTopic,
    Topic,
    Content,
    BibContent,
    Course,
    CourseContent,
    EvaluationTemplate,
    Item,
    EvaluationItem,
    CourseEvaluation,
)
from workflow.db.models.project import (
    LectureInstance,
    GeneralProject,
    GeneralProjectBib,
    GeneralProjectTopic,
)
from workflow.db.models.notes import (
    Citation,
    Concept,
    Label,
    Link,
    Note,
    NoteConcept,
    NoteTag,
    Tag,
)
from workflow.db.models.exercises import (
    Exercise,
    ExerciseOption,
)
from workflow.db.models.project_layer import (
    ProjectNote,
    PrismaDecision,
)

__all__ = [
    # bibliography
    "Author",
    "AuthorType",
    "BibAuthor",
    "BibEntry",
    "BibEntryTag",
    "BibKeyword",
    "BibTag",
    "BibUrl",
    "IsnType",
    "ReferencedDatabase",
    # academic
    "Institution",
    "MainTopic",
    "Topic",
    "Content",
    "BibContent",
    "Course",
    "CourseContent",
    "EvaluationTemplate",
    "Item",
    "EvaluationItem",
    "CourseEvaluation",
    # project
    "LectureInstance",
    "GeneralProject",
    "GeneralProjectBib",
    "GeneralProjectTopic",
    # notes (LocalBase / slipbox.db)
    "Citation",
    "Label",
    "Link",
    "Concept",
    "Note",
    "NoteConcept",
    "NoteTag",
    "Tag",
    # exercises
    "Exercise",
    "ExerciseOption",
    # project layer (LocalBase)
    "ProjectNote",
    "PrismaDecision",
]
