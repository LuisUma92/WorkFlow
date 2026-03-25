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
    Label,
    Link,
    Note,
    NoteTag,
    Tag,
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
    "Note",
    "NoteTag",
    "Tag",
]
