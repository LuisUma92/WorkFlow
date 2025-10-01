from dataclasses import dataclass, field

"""
This is a general structure that every project file should implement this
to its specific needs
"""


@dataclass
class ProjectStructure:
    code: str = ""
    name: str = ""
    topics: list[str] = field(default_factory=list)
    books: list[str] = field(default_factory=list)
    descriptions: dict[str, str] = field(default_factory=dict)

    def get_description(self, var_name: str) -> str:
        msn = f"ERROR: {var_name} not in structure"
        return self.descriptions.get(var_name, msn)


def make_structure(struct_type="general") -> ProjectStructure:
    base_desc = {
        "code": "Alfanumeric code",
        "name": "Name of the project",
        "topics": "List of topics",
        "books": "List of books",
    }
    overrides = {
        "general": {
            "topics": "General theme areas shared across courses",
            "books": "Reference books used broadly",
        },
        "course": {
            "topics": "Course topics (mapped to T## files)",
            "books": "Course-specific textbooks",
        },
    }
    desc = {**base_desc, **overrides.get(struct_type, {})}
    return ProjectStructure(descriptions=desc)
