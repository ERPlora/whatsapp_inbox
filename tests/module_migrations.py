"""The hub's migration guard, in miniature — shared by this module's Postgres batteries.

Every battery here builds a scratch database from `module.json`'s own migrations. Two things about
that list are NOT obvious, and getting either wrong makes a battery answer about a database the
fleet never has:

  1. **An entry has two shapes** (`MigrationEntry`, hub#542). The bare path —
     `"migrations/postgres/001_init.sql"`, which means `expand`— or the object
     `{file, kind, since}`, the ONLY way to declare a `contract` and therefore the only legitimate
     way to write a `DROP`. A loop that assumes the string shape crashes on the object one.

  2. **A `contract` is REWRITTEN before it reaches the database.**
     `migration_guard::set_aside_instead_of_dropping` turns `DROP COLUMN c` into
     `RENAME COLUMN c TO _deprecated_c` (and `DROP TABLE t` into `RENAME TO _deprecated_t`), so the
     data is set aside, not destroyed. A battery that applies the file raw DESTROYS what the hub
     only sets aside.

Ported from `hub/crates/runtime/src/migration_guard.rs` as it stands after hub#1137: the decision is
taken on the SQL with its comments stripped, so prose above a `DROP` no longer makes the translation
miss. Batteries import `declared_migrations()` and apply what it yields — never the raw file.

This file is not a battery: it runs inside the ones that import it.
"""

import json
import pathlib

MODULE_DIR = pathlib.Path(__file__).resolve().parent.parent
MANIFEST = json.loads((MODULE_DIR / "module.json").read_text(encoding="utf-8"))


def migration_entries(manifest: dict | None = None) -> list[tuple[str, str]]:
    """The manifest's Postgres migrations as `(file, kind)`, both shapes of `MigrationEntry`."""
    out: list[tuple[str, str]] = []
    for entry in (manifest or MANIFEST)["migrations"]["postgres"]:
        if isinstance(entry, str):
            out.append((entry, "expand"))
        else:
            out.append((entry["file"], entry.get("kind", "expand")))
    return out


def strip_comments(sql: str) -> str:
    """Drop SQL comments before anything is decided. A string literal is data, not a comment."""
    out: list[str] = []
    in_string = False
    i, n = 0, len(sql)
    while i < n:
        ch = sql[i]
        if in_string:
            out.append(ch)
            in_string = ch != "'"
            i += 1
            continue
        if ch == "'":
            in_string = True
            out.append(ch)
        elif sql.startswith("--", i):
            j = sql.find("\n", i)
            i = n if j < 0 else j
            continue
        elif sql.startswith("/*", i):
            j = sql.find("*/", i + 2)
            i = n if j < 0 else j + 2
            out.append(" ")
            continue
        else:
            out.append(ch)
        i += 1
    return "".join(out)


def split_statements(sql: str) -> list[str]:
    """Split on `;` respecting literals and comments (a `;` inside `-- …` is prose, not SQL)."""
    out: list[str] = []
    current: list[str] = []
    in_string = False
    i, n = 0, len(sql)
    while i < n:
        ch = sql[i]
        if in_string:
            current.append(ch)
            in_string = ch != "'"
        elif ch == "'":
            in_string = True
            current.append(ch)
        elif sql.startswith("--", i):
            j = sql.find("\n", i)
            j = n if j < 0 else j
            current.append(sql[i:j])
            i = j
            continue
        elif sql.startswith("/*", i):
            j = sql.find("*/", i + 2)
            j = n if j < 0 else j + 2
            current.append(sql[i:j])
            i = j
            continue
        elif ch == ";":
            if "".join(current).strip():
                out.append("".join(current).strip())
            current = []
        else:
            current.append(ch)
        i += 1
    if "".join(current).strip():
        out.append("".join(current).strip())
    return out


def _strip_if_exists(rest: str) -> tuple[str, str]:
    if rest.upper().startswith("IF EXISTS "):
        return "IF EXISTS ", rest[len("IF EXISTS ") :].strip()
    return "", rest


def set_aside_instead_of_dropping(statement: str) -> str:
    """`DROP COLUMN c` → `RENAME COLUMN c TO _deprecated_c`; `DROP TABLE t` → `RENAME TO …`."""
    sql = strip_comments(statement).strip()
    upper = sql.upper()

    at = upper.find(" DROP COLUMN ")
    if at != -1:
        if "," in sql.rstrip(";"):
            # The runtime refuses it (`DropsMoreThanOne`): the rename is one-to-one.
            raise ValueError(
                f"a contract drops more than one column in one statement: {sql}"
            )
        head = sql[:at].rstrip()
        guard, column = _strip_if_exists(sql[at + len(" DROP COLUMN ") :].strip())
        column = (column.split() or [column])[0].rstrip(";")
        return f"{head} RENAME COLUMN {guard}{column} TO _deprecated_{column}"

    if upper.startswith("DROP TABLE "):
        guard, table = _strip_if_exists(sql[len("DROP TABLE ") :].strip())
        if "," in table.rstrip(";"):
            raise ValueError(
                f"a contract drops more than one table in one statement: {sql}"
            )
        table = (table.split() or [table])[0].rstrip(";")
        return f"ALTER TABLE {guard}{table} RENAME TO _deprecated_{table}"

    return statement


def as_the_runtime_applies(sql: str, kind: str) -> str:
    """The SQL the hub really executes. Only a `contract` is rewritten; the rest runs as written."""
    if kind != "contract":
        return sql
    return (
        ";\n".join(set_aside_instead_of_dropping(s) for s in split_statements(sql))
        + ";\n"
    )


def declared_migrations(manifest: dict | None = None) -> list[tuple[str, str]]:
    """`(file, sql)` for every declared migration, in order, translated like the runtime does."""
    return [
        (
            rel,
            as_the_runtime_applies(
                (MODULE_DIR / rel).read_text(encoding="utf-8"), kind
            ),
        )
        for rel, kind in migration_entries(manifest)
    ]
