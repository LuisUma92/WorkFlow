"""workflow.bibliography — shared bibliography foundation module.

Peer of ``content``/``exercise``/``prisma``; owns bib-entry lookup helpers
that those consumers depend on. Import from the package so the public
surface stays stable across future submodule splits.
"""
from workflow.bibliography.service import BibKeyAmbiguous, get_bib_entry_by_bibkey

__all__ = ["BibKeyAmbiguous", "get_bib_entry_by_bibkey"]
