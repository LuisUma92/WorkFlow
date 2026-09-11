# Todo

Previous content (PRISMA P2 plan, all `[x]`) archived to `tasks/archive/2026-05-27-prisma-p2-todo.md`.

## 2026-09-10 — Docs + tasks/ drift fix

Plan: `tasks/plans/2026-09-10-docs-tasks-drift-fix-plan.md` · Audit: `tasks/audit/2026-09-10-tasks-and-primer-audit.md`

- [x] A. Close 2 shipped requests (bib-dialect, prisma-to-literature-note) with `closed_by`
- [x] A. Add `status: closed` frontmatter to 8 pre-template requests
- [x] B. Status headers on wave0/1/3 + tex-gf plans; post-freeze roadmap status line
- [x] C. Security 2026-06-03: #1–#3 fixed w/ evidence; #4 TOCTOU + #5 LOW remain open
- [x] D. Archive `todo.md` + `WIKI-UPDATE-BRIEF.md` → `tasks/archive/`
- [x] E. CLAUDE.md (line 104, `share/latex`, bibliography + ucimed bullets, nvim `gf`); ADR-0021 → Accepted
- [x] F. Audit summary table updated; primer rewritten
- [ ] Push 20+ commits to `public` (network check first) — not docs scope
- [ ] ★ Luis: flake8 123 non-CI findings — accept as baseline or clean?
- [x] Security #4 TOCTOU in `accept_to_note.py` → filed `tasks/requests/2026-09-10-accept-to-note-atomic-create.md`

## Results

Verified 2026-09-10: `grep -L '^status:' tasks/requests/*.md` leaves only pre-template
body-RESOLVED files; `grep 'soon to move\|shared/latex' CLAUDE.md` empty. No code touched.
