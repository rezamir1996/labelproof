# Design

## The problem, stated precisely

A label is a pair `(text, declared)`. The text is free prose. `declared` is a set of
allergen codes the pack claims to carry. Compliance means:

> every allergen reachable from the ingredients named in `text` is present in `declared`.

Both halves are hard in different ways. Reading `text` into ingredients is semantic.
Reaching allergens from ingredients is bookkeeping — but bookkeeping that must be the
same on every node, hence on chain rather than in anyone's head.

The contract splits the work along that line: the model is confined to the semantic
half, and the deterministic half is graph arithmetic the model cannot touch.

## State

    owner               Address
    site_label          str

    allergen_label      code -> display name
    allergen_index      comma separated code list          (ordered read)
    ingredient_label    code -> display name
    ingredient_index    comma separated code list
    ingredient_implies  code -> "target|target"            (targets: allergens or ingredients)
    ingredient_synonyms code -> "folded phrase|folded phrase"
    allergens           u256
    ingredients         u256

    product_declared    product id -> "CODE|CODE"          (sorted)
    product_text        product id -> raw label text
    product_verdict     product id -> COVERED | GAP | UNUSABLE
    product_missing     product id -> "CODE,CODE"          (sorted, the gap)
    product_extra       product id -> "CODE,CODE"          (sorted, surplus declarations)
    product_derived     product id -> "code,code"          (sorted, the inventory)
    product_counts      product id -> "<deterministic>,<model>"
    products            u256

Two fields exist only because a tree map cannot be iterated in a deterministic order:
`allergen_index` and `ingredient_index` are the ordered register of registered codes.
Everything that needs to enumerate the vocabulary reads those, never the map keys. This
matters because the model prompt and the closure both need a stable list, and iterating a
`TreeMap` would give each node a different prompt for the same state.

## Why the graph is on chain

`ingredient_implies` is the only place an allergen can come from. Any ingredient code the
model is allowed to report must already be a node, and its outgoing edges were written by
the contract owner in a transaction. Therefore:

- the model's output vocabulary is closed and auditable;
- the mapping from ingredient to allergen is public and immutable once written;
- a disagreement between two nodes can only be about *which ingredients the text names*,
  never about *what those ingredients contain*.

That last point is the whole design. It reduces the nondeterministic surface from "is this
label compliant" to "does this text mention this word", which is a question a quote check
can referee.

## The four layers

**1. Folding.** `_normalize` lowercases, maps four Arabic/Persian letter variants to one
form (yeh, alef maksura, kaf, teh marbuta), drops tatweel, zero-width joiners and
bidi marks, strips diacritics, replaces every non-alphanumeric character with a space and
collapses runs of spaces. The same function produces both the stored synonyms and the
text that is searched, so a synonym registered in one spelling matches a label typed in
another.

Punctuation becomes a space rather than being deleted, so `milk,egg` folds to
`milk egg` and the words stay separable.

**2. Deterministic floor.** For every registered ingredient, each of its folded synonyms
is looked up in the folded text with `_padded`, which requires the phrase to sit on token
boundaries. `soy` therefore cannot match inside `soybean oil` by accident. A hit commits
the ingredient before any model call. The floor is identical on every node by
construction, so it needs no consensus — it is recomputed after the block, from storage
that no node can vary.

**3. Model layer.** One `exec_prompt` with `response_format="json"` over the closed
ingredient vocabulary. The model returns `{"ingredients": [{"code", "quote"}]}`. The
prompt states the label text is untrusted data between `<<<LABEL>>>` markers, so an
injection attempt inside an ingredient list is data, not an instruction.

**4. Verification and derivation.** `_read_item` accepts an item only if the code is in
scope, the folded quote has at least three tokens, and `_padded` finds it in the folded
text. Any rejected item makes the whole answer `UNUSABLE` rather than being dropped
quietly: a model that invents one item has shown its answer is not a reading of this
label, and discarding only the bad item would let a fabricated list pass as a partial
one. The deterministic floor is unaffected — it is recomputed from storage.

Then `_closure` walks the implication graph out from the merged inventory, collecting
allergen endpoints. `_closure` is cycle-agnostic (a `seen` set and a 512-step guard), so
even a graph that somehow acquired a cycle terminates instead of hanging a node.

## Rejected designs

**A model that returns the verdict.** The simplest design, and the one the validator
cannot honestly referee: two nodes that both read "clarified butter" as milk still
disagree about whether the label is fine, and no local comparison distinguishes a
disagreement from a mistake.

**Embedding similarity against an ingredient table.** Deterministic on paper, but it needs
a numeric threshold, and a threshold turns every borderline synonym into an arbitrary
pass/fail with no explanation a human can audit. It also cannot be tuned after deployment.

**Letting the model report allergens directly.** Then allergens no longer come from the
on-chain graph, and the model can invent a gap on a label that is fine, or — worse —
declare one absent by staying silent.

**Comparing quotes inside the validator.** Two correct readings of the same label quote
different spans. Requiring quote agreement rejects honest nodes and buys nothing: quotes
are re-checked against the text deterministically after consensus, which is stricter than
agreement between models.

## Failure modes and what happens

| Situation | Behaviour |
| --- | --- |
| no ingredients registered | `audit` reverts with `NO_INGREDIENTS`; there is nothing to close over |
| model times out or throws | leader returns the `UNUSABLE` signal; `audit` stores `UNUSABLE` |
| model output is prose | same |
| every product audited unusably | gate returns `false` everywhere: the safe direction |
| an ingredient implies an ingredient that implies an allergen | handled; closure is transitive to any depth |
| a cycle reaches the graph | cannot be created through `add_ingredient` (targets must exist, so a new node has no incoming edge), and the walk terminates anyway |
| label text is 19 characters | `BAD_TEXT`; the shortest real ingredient list is far longer |

## The gate

`is_covered` returns `true` only for a stored `COVERED`. Not audited, `GAP`, `UNUSABLE`,
and unknown product ids all return `false`. A consumer contract cannot accidentally
publish an unproven product, which is the only property a downstream integration needs to
know.
