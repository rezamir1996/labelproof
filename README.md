# LabelProof

An on-chain audit that proves a product label declares every allergen its ingredients
imply — and fails closed when it cannot prove it.

    ingredient text  ->  [ model reads, code verifies ]  ->  inventory
    inventory        ->  transitive closure over an on-chain graph  ->  implied allergens
    implied allergens  minus  declared allergens  ->  gap

If the gap is empty the label is `COVERED`. If it is not, the contract returns the exact
missing allergen codes. If the reading cannot be trusted, the verdict is `UNUSABLE` and
the gate returns `false`.

## Live on Studio

    contract       0x927488Ac4A2124D713Df57942bD76a29f32b89E4
    explorer       https://explorer-studio.genlayer.com/address/0x927488Ac4A2124D713Df57942bD76a29f32b89E4
    deploy tx      0x5aec60d13daab9a4d6caedfe8617a78518987c3772dbae515149d22b88863960
    site_label     allergen-audit-v1

Two products are registered and audited. Both branches of the decision are live:

| product | label says | conclusion | verdict | gate |
| --- | --- | --- | --- | --- |
| `snack-001` | `MILK\|EGG` declared | ingredients `butter,eggwhite`, implying `MILK,EGG` | `COVERED` | `true` |
| `snack-002` | `MILK` declared | ingredients `wheatflour`, implying `GLUTEN` | `GAP` missing `GLUTEN` | `false` |

On `snack-001` the word "milk" never appears in the text: `MILK` is reached two hops from
`clarified butter` (`butter -> milk -> MILK`) through the published graph. On `snack-002`
the label declares `MILK` and its ingredients imply `GLUTEN`, so `missing_of` is `GLUTEN`
and `extra_of` is `MILK`.

`counts_of` reports `<from code>,<from model>`. `snack-001` is `1,1` and `snack-002` is
`0,1`: in both cases at least one ingredient is only reachable by the reading step, which
is why the model is in the loop at all.

Addresses, every transaction hash and the validator votes behind both audits are in
[`EVIDENCE.md`](EVIDENCE.md).

## Why this needs an Intelligent Contract

An ingredient list is prose. `clarified butter`, `whey powder` and `casein` are three
spellings of milk, and no regular expression turns them into the allergen codes a label
must legally carry. The reading step is genuinely semantic, so it needs a language model
— and a model deciding whether a product is safe to sell is exactly the decision that
must not be taken by one party in private.

So the model is given one narrow job: report which registered ingredients the text
mentions. It does not decide compliance. The judgement is arithmetic on a graph the
contract owner publishes on chain, and every node it reports is checked against the text
before it can change anything.

## What the contract stores

| Group | What it is |
| --- | --- |
| vocabulary | allergen codes, ingredient codes, each ingredient's implications and literal synonyms |
| product | declared allergen codes and the label text, keyed by product id |
| verdict | `COVERED` / `GAP` / `UNUSABLE`, the missing codes, the surplus codes, the derived inventory |
| counters | allergen, ingredient and audited product counts |

`audit()` is write-once per product: the first verdict stands, so the record is a
statement about a specific label at a specific time rather than a value anyone can
refresh.

## The consumer surface

    is_covered(product_id)   # bool  -- fails closed: false when unaudited or unusable
    verdict_of(product_id)   # str   -- COVERED | GAP | UNUSABLE | "" before audit
    missing_of(product_id)   # str   -- e.g. "EGG,MILK"
    extra_of(product_id)     # str   -- declared but not implied by any ingredient
    inventory_of(product_id) # str   -- ingredients the contract concluded are present
    counts_of(product_id)    # str   -- "<from code>,<from model>"

A marketplace, a listing contract or a distributor's intake check only needs the first
one. The rest exist so a human can see why the gate said no.

## Quickstart

    python3 -m venv .venv && . .venv/bin/activate
    pip install -r requirements-dev.txt
    python scripts/prepare_test_sdk.py        # fetches the GenVM binary used by direct mode
    pytest tests/direct -q                     # 37 passed
    genvm-lint check contracts/label_proof.py  # 3 checks, 21 methods
    genvm-lint typecheck contracts/label_proof.py

Direct mode runs the real GenVM in memory: no network, no validator set, no keys.

## A worked example

Vocabulary: `MILK` (allergen), `butter -> milk`, `whey -> MILK`.

Label: `Ingredients: sugar, clarified butter, salt` with declared allergens: *(none)*.

1. Deterministic floor: the synonym `clarified butter` is in the text, so `butter` is in
   the inventory without any model call.
2. Closure: `butter -> milk -> MILK`.
3. Declared set is empty, so the gap is `MILK`. Verdict `GAP`.

Declare `MILK` and the same label becomes `COVERED`. Nothing about the model's opinion
changed; only the graph and the declaration did.

## Where the model can and cannot move the outcome

| The model does this | Result |
| --- | --- |
| reports a registered ingredient with a quote that is in the text | the ingredient joins the inventory |
| reports an ingredient whose quote is not in the text | whole reading `UNUSABLE` |
| reports a code outside the vocabulary | whole reading `UNUSABLE` |
| reports a quote shorter than three words | whole reading `UNUSABLE` |
| returns prose, or no `ingredients` key | whole reading `UNUSABLE` |
| reports nothing | the deterministic floor still decides |

A model cannot invent an allergen: only registered ingredients can be reported, and
allergens appear only as the endpoints of on-chain edges. A model cannot see the
declaration at all, so it cannot aim at a verdict.

## Documentation

- [`docs/DESIGN.md`](docs/DESIGN.md) — state model, invariants, rejection surface.
- [`docs/CONSENSUS.md`](docs/CONSENSUS.md) — the nondeterministic block, the signal, and
  why a forged leader cannot change a stored value.
- [`EVIDENCE.md`](EVIDENCE.md) — deployment address, transaction hashes, live results.

## Licence

MIT.
