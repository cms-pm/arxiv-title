# arxiv-title

Renames arXiv PDFs from opaque identifiers to descriptive, title-based filenames.

```
2101.05536v1.pdf
  -> 2101.05536v1_scaling_equilibrium_propagation_to_deep_convnets_by_drastically_reducing_its_gradient_estimator_bias.pdf
```

## Install

```sh
python -m venv .venv
.venv/bin/pip install -e ".[dev]"
```

## Use

```sh
arxiv-title artifacts/                 # rename every arXiv-named PDF in a directory
arxiv-title -n artifacts/              # --dry-run: preview, touch nothing
arxiv-title --offline artifacts/       # no network; use the PDFs alone
arxiv-title 2101.05536v1.pdf           # a single file
```

| Flag | Effect |
|---|---|
| `-n`, `--dry-run` | Print the rename table and exit without changing anything |
| `--offline` | Skip the arXiv API layer |
| `-r`, `--recursive` | Descend into subdirectories |
| `--force` | Accept titles that were only guessed from page layout |
| `--no-id-prefix` | Emit `how_frogs_croak.pdf` instead of `2101.05536v1_how_frogs_croak.pdf` |
| `-v`, `--verbose` | Show which source supplied each title |

Only files whose name *starts* with an arXiv identifier are considered when scanning a
directory; anything else is left alone. Because the ID is kept as a prefix by default, a
second run over an already-renamed directory is a clean no-op.

## How the title is found

Three sources, tried in order and reported by `--verbose`:

1. **`api`** — the arXiv Atom API, looked up by the identifier in the filename. Exact
   canonical titles, one batched HTTP request for the whole directory.
2. **`metadata`** — the PDF's own `/Title` entry.
3. **`layout`** — typography on page one: the first contiguous block of
   larger-than-body-text lines near the top of the page.

Layout results are treated as low-confidence and held back from renaming unless you pass
`--force`.

### Why the layout heuristic is not just "the largest text"

The obvious rule — take the biggest text on page one — gets 4 of the 10 sample papers
right. Two problems dominate, both artifacts of how LaTeX sets titles:

- **Small caps and enlarged leading capitals.** `\textsc{}` titles set the full capitals
  several points larger than the small capitals. A largest-glyph rule selects that one
  letter and reports a title of `"M"`. Fixed by taking each line's *character-count
  weighted* dominant size, so twenty body letters outvote one oversized capital.
- **Split lines.** Those same enlarged capitals sit higher on the page than the rest of
  the line, so grouping words by their `top` coordinate tears one visual line in two —
  yielding `T D H : T M L` followed by `HE RAGON ATCHLING …`. Fixed by clustering on the
  *baseline*, which the two sizes share to within a point.

Two smaller details matter as well: `extract_words` splits a run wherever the font size
changes, so adjacent fragments must be rejoined without a space (otherwise `The` becomes
`T he`), and titles routinely wrap across two or three lines that need rejoining.

With those in place the layout heuristic alone gets all 10 of the sample papers right.

## Tests

```sh
.venv/bin/python -m pytest
```

The suite is self-contained: extraction runs against three small PDFs committed under
`tests/pdf/`, and the API tests use a mocked transport. No network and no local corpus
required.
