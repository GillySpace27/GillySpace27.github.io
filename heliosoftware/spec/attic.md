# Attic convention

Version 1, 2026-10-01. Canonical copy: `heliosoftware/spec/attic.md` in the gilly.space repository, served at https://gilly.space/heliosoftware/spec/attic.md. Producer: suite initiative SU-16. Consumers: every HelioSoftware repository.

## The rule

Nothing is deleted. A file, branch, tag, release, worktree, backup, data folder or cache that leaves use is recorded in a ledger and kept. Retiring is a move or a note, never a removal. This page fixes where the note goes and what it says, so one row format works in every repository.

## Four cases

| Case | What to do | Where it is recorded |
|---|---|---|
| A tracked file or folder nothing uses | `git mv` it under `attic/`, keeping its relative path below `attic/`; commit the move on its own | a row in `attic/README.md` |
| A tracked file that has to stay where it is | leave it; optionally add a first-line comment `Retired (see ATTIC.md)` | a row in the root `ATTIC.md` |
| A superseded branch | tag its tip with an annotated tag (see "Archive tags"); the branch stays | a row in the root `ATTIC.md` |
| A worktree, backup, data folder, cache or untracked file | nothing; list it so the next agent does not "clean" it | a row in the root `ATTIC.md`, or the section `## Left in place (listed only)` of `attic/README.md` |

An agent never removes anything in the last row, and never deletes a branch, a tag or a release in any row.

## Row format

One table with this exact header, in this order:

| What | Where it is now | Why | Restore command | Date |
|---|---|---|---|---|

- What: the thing, with its original path or branch name in backticks.
- Where it is now: its path under `attic/`, or "same path", or, for a branch, the branch name in backticks and the tag with `at tip <sha7>` (seven hex digits).
- Why: one sentence, and what replaced it if anything did.
- Restore command: one command in backticks, run from the repository root, that puts the item back or reaches it without changing a branch, and holds none of `rm`, `git rm`, `--force`, `--clobber`, `push`, `branch -D`, `tag -d`, `reset --hard`, `clean -f`, `filter-repo`. Or `none: <reason>` when nothing can or should be restored.
- Date: `YYYY-MM-DD`, the day the row was written.
- No `|` inside a cell and no em dash. Rows are appended. An existing row is never rewritten or removed; a correction is a new row that says what it corrects.

| Case | Restore command |
|---|---|
| moved file | `git mv attic/old/path old/path` |
| archived branch | `git switch --detach archive/<branch>` |
| still at its path | `none: still at its path` |
| worktree, backup, data folder | `none: listed only; do not remove` |

## Archive tags

- Name: `archive/<branch>`, the full branch name including slashes. Annotated: `git tag -a archive/<branch> <tip-sha> -m "Archive: <branch> at <sha7>; <reason>; branch left in place"`.
- Tag the tip as it is now: read it with `git rev-parse <branch>` and write the same seven digits in the row. A tag on the wrong commit misleads.
- An existing tag is never moved, renamed or deleted. Tags made before this page keep their names and are listed as they are: HelioFITS Studio uses `archive/branch/<branch>`, the My Heliograph store uses `archive/2026-10/<branch>`, the Website uses short names such as `archive/heliofits-sibling-link`. A repository never gets a second scheme.
- Tags stay local until Gilly says push. Push named tags only: never `--tags`, never `--force`.
- The prefix `attic/` is for moved files only. No `attic/<branch>` tag is made.

## Never tag

A branch whose history holds a secret gets no tag, and is never pushed: a tag or branch on a remote publishes that history. The My Heliograph store has 16 local branches with `.env` commits from before the 2026-07-15 purge; they are listed, bundled outside the repository, and left in place.

## Listed only

Worktrees, folders such as `.git-backup/`, large data folders (a render folder of tens of gigabytes), `.venv/` and untracked scripts are listed with the restore cell `none: listed only; do not remove`. Listing is the whole action.

## Checking a ledger

1. Tag row: `git rev-parse --short=7 <tag>^{commit}` equals the digits after `at tip`; if the branch still exists, `git merge-base --is-ancestor <tag> <branch>` exits 0 (the branch may have moved on).
2. Restore command: in a scratch clone (`git clone --no-hardlinks . /tmp/x`), run it there; it exits 0. `none:` rows run nothing.
3. On a branch that only records things, `git diff --diff-filter=D --name-only <base>..HEAD` prints nothing.

## Ledgers in each repository

| Repository | Moved items | Everything else | Notes |
|---|---|---|---|
| gilly.space (Website) | none yet; `attic/` when first needed | `ATTIC.md`: two older tables (`Path / What it was / Why retired / Replacement / Date` and `Ref / What it was / Why retired / Archive tag / Date`) plus the section `## Canonical rows` | Tags `archive/heliofits-sibling-link`, `archive/whichclaude-worktree-ff91b7f`. |
| HelioFITS | none yet | `ATTIC.md`, canonical rows from the start | `build-attic/` is git-ignored build output, not a ledger. Tags `archive/<branch>`. |
| HelioFITS Studio | `archive/` with `archive/README.md` (`Folder / Contents / Why it is here`) | `ATTIC.md`, canonical rows, an index to `archive/` | Tags `archive/branch/<branch>`, `archive/origin/<branch>`, `archive/stash/<name>`. |
| Heliogram | `attic/README.md`, one line per move: date, path, what, old path, why, `git mv` back | `ATTIC.md` when the first non-move item appears | Line format is kept. |
| sunback | `attic/README.md` (`Original path / Moved to / LOC / Reason / Date / Restore`) | section `## Left in place (listed only)` in the same file, canonical rows | Restore is `git mv <moved to> <original path>`. |
| My Heliograph store (sunback_webapp) | `attic/README.md` (`Path / Original path / Moved / Reason / Replacement`) | `ATTIC.md`, canonical rows; branch decisions in `BRANCHES.md` | Tags `archive/2026-10/<branch>`; none on the pre-purge branches. |
| fastRHEF | none | `ATTIC.md` when first needed | `tools/archive/` holds old scripts that were never a ledger. |

A repository whose ledger predates this page keeps its columns and gains canonical rows beside them; old rows are not rewritten.
