"""ITEP-0012 — service layer tests (TDD RED → GREEN).

All tests use real ORM types; no monkey-patching of domain types (lessons row 17).
"""

from __future__ import annotations

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from workflow.db.base import GlobalBase
from workflow.db.models.knowledge import DisciplineArea, MainTopic, Topic, Content
from workflow.db.models.knowledge import Concept
from workflow.db.models.notes import NoteConcept, Note
from workflow.concept.service import (
    ConceptError,
    ContentNotFound,
    DuplicateCode,
    HasReferences,
    MainTopicNotFound,
    ParentNotFound,
    UnknownCode,
    _get_concept_or_raise,
    add_concept,
    build_concept_tree,
    concept_discipline_area,
    concept_main_topic,
    get_concept,
    list_concepts,
    remove_concept,
    rename_concept,
    resolve_concepts,
)


# ── Fixtures ──────────────────────────────────────────────────────────────


@pytest.fixture()
def engine():
    """In-memory SQLite engine with all GlobalBase tables."""
    import workflow.db.models.bibliography  # noqa: F401
    import workflow.db.models.academic  # noqa: F401
    import workflow.db.models.project  # noqa: F401
    import workflow.db.models.notes  # noqa: F401
    import workflow.db.models.exercises  # noqa: F401

    eng = create_engine("sqlite:///:memory:")
    GlobalBase.metadata.create_all(eng)
    return eng


@pytest.fixture()
def session(engine):
    with Session(engine) as s:
        yield s


def _seed_concept_chain(
    session: Session,
    *,
    da_code: str = "FI0000",
    mt_code: str = "FI0006",
    domain: str = "Información",
) -> tuple[DisciplineArea, MainTopic, Topic, Content]:
    """Create DisciplineArea → MainTopic + Topic (rooted at DA) → Content chain.

    Post-Phase-4B: Topic is rooted at DisciplineArea via discipline_area_id FK.
    MainTopic is still created for tests that exercise MT-based queries, but
    Topic no longer carries main_topic_id.
    """
    da = DisciplineArea(
        code=da_code, name="Fisica", discipline_num=10, topic_num=0, area_initials="FI"
    )
    session.add(da)
    session.flush()
    mt = MainTopic(code=mt_code, name="Mecanica", discipline_area_id=da.id)
    session.add(mt)
    session.flush()
    # Topic is now rooted at DisciplineArea, not MainTopic (Phase 4B)
    tp = Topic(discipline_area_id=da.id, name="Cinematica", serial_number=1)
    session.add(tp)
    session.flush()
    ct = Content(topic_id=tp.id, name="Movimiento rectilineo")
    session.add(ct)
    session.flush()
    return da, mt, tp, ct


@pytest.fixture()
def seeded(session):
    """Seed chain + two MainTopics + one Concept.

    Post-Phase-4B: both Topics are rooted at DisciplineArea via discipline_area_id.
    """
    da, mt1, tp1, ct1 = _seed_concept_chain(
        session, da_code="FI0000", mt_code="FI0006"
    )
    # Second DisciplineArea + MainTopic for ct2 (different DA to allow filter tests)
    da2 = DisciplineArea(code="QU0000", name="Quimica", discipline_num=20, topic_num=0, area_initials="QU")
    session.add(da2)
    session.flush()
    mt2 = MainTopic(code="FI0007", name="Termodinamica", discipline_area_id=da2.id)
    session.add(mt2)
    session.flush()
    tp2 = Topic(discipline_area_id=da2.id, name="Calor", serial_number=1)
    session.add(tp2)
    session.flush()
    ct2 = Content(topic_id=tp2.id, name="Calor especifico")
    session.add(ct2)
    session.flush()

    c = Concept(code="forces", label="Forces", content_id=ct1.id, domain="Información")
    session.add(c)
    session.commit()
    return {
        "da": da, "da2": da2,
        "mt1": mt1, "tp1": tp1, "ct1": ct1,
        "mt2": mt2, "tp2": tp2, "ct2": ct2,
        "concept": c,
    }


# ── resolve_concepts ──────────────────────────────────────────────────────


def test_resolve_concepts_empty_input_returns_empty(session):
    result, issues = resolve_concepts([], session, strict=False)
    assert result == []
    assert issues == []


def test_resolve_concepts_known_returns_objects(session, seeded):
    result, issues = resolve_concepts(["forces"], session, strict=False)
    assert len(result) == 1
    assert result[0].code == "forces"
    assert issues == []


def test_resolve_concepts_lenient_unknown_returns_warning(session, seeded):
    result, issues = resolve_concepts(["nonexistent"], session, strict=False)
    assert result == []
    assert len(issues) == 1
    assert issues[0]["severity"] == "warning"
    assert "nonexistent" in issues[0]["message"]


def test_resolve_concepts_strict_unknown_returns_error(session, seeded):
    result, issues = resolve_concepts(["nonexistent"], session, strict=True)
    assert result == []
    assert len(issues) == 1
    assert issues[0]["severity"] == "error"
    assert "nonexistent" in issues[0]["message"]


# ── add_concept ───────────────────────────────────────────────────────────


def test_add_concept_duplicate_code_raises(session, seeded):
    with pytest.raises(DuplicateCode):
        add_concept(
            session,
            code="forces",
            label="Forces Again",
            content_id=seeded["ct1"].id,
            domain="Información",
        )


def test_add_concept_unknown_content_raises(session, seeded):
    with pytest.raises(ContentNotFound):
        add_concept(
            session,
            code="new-concept",
            label="New",
            content_id=99999,
            domain="Información",
        )


def test_add_concept_invalid_domain_raises(session, seeded):
    with pytest.raises(ConceptError):
        add_concept(
            session,
            code="bad-domain",
            label="Bad Domain",
            content_id=seeded["ct1"].id,
            domain="InvalidDomain",
        )


def test_add_concept_unknown_parent_raises(session, seeded):
    with pytest.raises(ParentNotFound):
        add_concept(
            session,
            code="child",
            label="Child",
            content_id=seeded["ct1"].id,
            domain="Información",
            parent_code="does-not-exist",
        )


def test_add_concept_parent_in_different_content_raises(session, seeded):
    """Parent must belong to same content as child."""
    # Add concept under ct2 (different chain)
    ct2_concept = Concept(
        code="heat",
        label="Heat",
        content_id=seeded["ct2"].id,
        domain="Información",
    )
    session.add(ct2_concept)
    session.commit()

    with pytest.raises(ConceptError):
        add_concept(
            session,
            code="child-of-heat",
            label="Child of heat",
            content_id=seeded["ct1"].id,  # different content than parent
            domain="Información",
            parent_code="heat",
        )


def test_add_concept_invalid_code_raises(session, seeded):
    """Code must match slug pattern."""
    with pytest.raises(ConceptError):
        add_concept(
            session,
            code="INVALID CODE/bad",
            label="Bad",
            content_id=seeded["ct1"].id,
            domain="Información",
        )


def test_add_concept_happy_path(session, seeded):
    concept = add_concept(
        session,
        code="newton-2nd",
        label="Newton 2nd Law",
        content_id=seeded["ct1"].id,
        domain="Información",
        parent_code="forces",
    )
    session.commit()
    assert concept.id is not None
    assert concept.code == "newton-2nd"
    assert concept.parent_id == seeded["concept"].id


# ── get_concept / list_concepts ───────────────────────────────────────────


def test_get_concept_returns_none_for_unknown(session):
    assert get_concept(session, "nonexistent") is None


def test_list_concepts_all(session, seeded):
    results = list_concepts(session)
    assert len(results) == 1
    assert results[0].code == "forces"


def test_list_concepts_filtered_by_main_topic(session, seeded):
    # Add concept under ct2 (different main topic chain)
    session.add(Concept(code="heat", label="Heat", content_id=seeded["ct2"].id, domain="Información"))
    session.commit()

    results = list_concepts(session, main_topic_code="FI0006")
    assert len(results) == 1
    assert results[0].code == "forces"


# ── build_concept_tree ────────────────────────────────────────────────────


def test_build_concept_tree_filters_by_main_topic(session, seeded):
    # Add child concept under ct1 (same MT chain)
    child = Concept(
        code="gravity",
        label="Gravity",
        content_id=seeded["ct1"].id,
        domain="Información",
        parent_id=seeded["concept"].id,
    )
    # Add concept under ct2 (different MT)
    other = Concept(code="heat", label="Heat", content_id=seeded["ct2"].id, domain="Información")
    session.add_all([child, other])
    session.commit()

    tree = build_concept_tree(session, main_topic_code="FI0006")
    codes = {n["code"] for n in tree}
    assert "forces" in codes
    assert "heat" not in codes


def test_build_concept_tree_orphan_parent_outside_filter(session, seeded):
    """Child whose parent is filtered out becomes a root node."""
    ct2_concept = Concept(code="heat", label="Heat", content_id=seeded["ct2"].id, domain="Información")
    session.add(ct2_concept)
    session.flush()

    # Child belonging to ct1 chain but whose parent belongs to ct2 chain
    # (this shouldn't happen via add_concept but test robustness)
    orphan = Concept(
        code="orphan-node",
        label="Orphan",
        content_id=seeded["ct1"].id,
        domain="Información",
        parent_id=ct2_concept.id,
    )
    session.add(orphan)
    session.commit()

    tree = build_concept_tree(session, main_topic_code="FI0006")
    all_codes = _collect_tree_codes(tree)
    assert "orphan-node" in all_codes


def _collect_tree_codes(nodes: list[dict]) -> set[str]:
    codes: set[str] = set()
    for n in nodes:
        codes.add(n["code"])
        codes.update(_collect_tree_codes(n.get("children", [])))
    return codes


# ── remove_concept ────────────────────────────────────────────────────────


def test_remove_concept_refuses_when_note_concept_rows(session, seeded):
    """HasReferences raised when NoteConcept rows reference the concept."""
    note = Note(
        zettel_id="note-001",
        filename="note-001.md",
        reference="note-001",
        title="Test Note",
        note_type="permanent",
    )
    session.add(note)
    session.flush()

    nc = NoteConcept(note_id=note.id, concept_id=seeded["concept"].id)
    session.add(nc)
    session.commit()

    with pytest.raises(HasReferences):
        remove_concept(session, "forces", force=False)


def test_remove_concept_force_cascades_note_concept(session, seeded):
    """Force=True removes NoteConcept rows."""
    note = Note(
        zettel_id="note-002",
        filename="note-002.md",
        reference="note-002",
        title="Test Note 2",
        note_type="permanent",
    )
    session.add(note)
    session.flush()

    nc = NoteConcept(note_id=note.id, concept_id=seeded["concept"].id)
    session.add(nc)
    session.commit()

    remove_concept(session, "forces", force=True)
    session.commit()

    remaining = (
        session.query(NoteConcept).filter_by(concept_id=seeded["concept"].id).all()
    )
    assert remaining == []


def test_remove_concept_force_reparents_children_to_grandparent(session, seeded):
    """Children's parent_id set to removed concept's parent_id (may be None)."""
    parent = seeded["concept"]  # parent_id=None (root)
    child = Concept(
        code="gravity",
        label="Gravity",
        content_id=seeded["ct1"].id,
        domain="Información",
        parent_id=parent.id,
    )
    session.add(child)
    session.commit()

    remove_concept(session, "forces", force=True)
    session.commit()

    session.expire_all()
    updated_child = session.query(Concept).filter_by(code="gravity").first()
    # grandparent of child = parent's parent_id = None
    assert updated_child.parent_id is None


# ── rename_concept ────────────────────────────────────────────────────────


def test_rename_concept_atomic(session, seeded):
    rename_concept(session, "forces", "forces-v2")
    session.commit()

    assert get_concept(session, "forces") is None
    updated = get_concept(session, "forces-v2")
    assert updated is not None
    assert updated.id == seeded["concept"].id


def test_rename_concept_collides_with_existing_raises(session, seeded):
    session.add(
        Concept(code="gravity", label="Gravity", content_id=seeded["ct1"].id, domain="Información")
    )
    session.commit()

    with pytest.raises(DuplicateCode):
        rename_concept(session, "forces", "gravity")


# ── concept_main_topic (deprecated) ──────────────────────────────────────


def test_concept_main_topic_returns_none_post_reroot(session, seeded):
    """concept_main_topic() returns None post-Phase-4B (Topic no longer carries main_topic_id).

    The function is deprecated; concept.main_topic always returns None now.
    This test documents the expected (changed) behaviour.
    """
    c = seeded["concept"]
    mt = concept_main_topic(c)
    assert mt is None


# ── concept_discipline_area ───────────────────────────────────────────────


def test_concept_discipline_area_traversal(session, seeded):
    """concept_discipline_area() resolves content→topic→discipline_area."""
    c = seeded["concept"]
    da = concept_discipline_area(c)
    assert da is not None
    assert da.code == "FI0000"


def test_concept_discipline_area_returns_none_for_detached(session):
    """concept_discipline_area() returns None when concept has no content."""
    orphan = Concept(code="orphan", label="Orphan", content_id=None, domain="Información")
    # Don't persist; test pure chain traversal guard
    result = concept_discipline_area(orphan)
    assert result is None


# ── _get_concept_or_raise ─────────────────────────────────────────────────


def test_get_concept_or_raise_raises_unknown_code_for_missing_slug(session):
    """_get_concept_or_raise raises UnknownCode when slug not in DB."""
    with pytest.raises(UnknownCode):
        _get_concept_or_raise(session, "no-such-slug")


# ── list_concepts error path ──────────────────────────────────────────────


def test_list_concepts_raises_main_topic_not_found_for_unknown_code(session):
    """list_concepts raises MainTopicNotFound for unknown main_topic_code."""
    with pytest.raises(MainTopicNotFound):
        list_concepts(session, main_topic_code="ghost")
