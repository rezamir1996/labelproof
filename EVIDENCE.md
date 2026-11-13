# Evidence

Everything in this file was read back from the chain or from the public GitHub repo.
Nothing here is copied from a UI screenshot, and no number is estimated.

## 1. The deployed contract

Network: GenLayer Studio (studionet).

    contract address   0x927488Ac4A2124D713Df57942bD76a29f32b89E4
    owner / deployer   0x74b60694EfBBCF6B5F78240Ed61139282b4C17A9
    constructor arg    allergen-audit-v1
    deploy tx          0x5aec60d13daab9a4d6caedfe8617a78518987c3772dbae515149d22b88863960
    output             FINALIZED

Explorer page:
https://explorer-studio.genlayer.com/address/0x927488Ac4A2124D713Df57942bD76a29f32b89E4

### The deployed code is the repo code

The explorer API exposes the executed source (`data.contract_code`, base64) for the deploy
transaction. Decoding it gives 21,413 bytes. Converting its CRLF line endings to LF gives a
byte-identical file to `contracts/label_proof.py` in this repo:

    deployed, LF-normalized, sha256   e6cc6d497f491bf42da1617890ed1b6133690a29c279c9bc4367a08b4816817f
    contracts/label_proof.py, sha256  932805baed7800b0565079fa00a775226941a679b958ecf2fca790f517206f22
    equality test                     True  (deployed.replace(CRLF, LF) == repo file)

The only differences between the raw bytes are the line ending and a trailing newline that
the deploy pipeline strips. There is no hidden code on chain and no local-only code.

## 2. Every transaction

Twelve transactions, all FINALIZED. `#` is `0x927488Ac4A2124D713Df57942bD76a29f32b89E4`.

    deploy            0x5aec60d13daab9a4d6caedfe8617a78518987c3772dbae515149d22b88863960
    add_allergen      MILK "milk and milk products"
                      0x6f0d3841601e41fc19344da9db6ce32d3be99011848373a5807518128e9ce240
    add_allergen      EGG "egg and egg products"
                      0x249fcb8648e88e3465b08df7614fab9e925205a928e1edaea91c8d7937e25c86
    add_allergen      GLUTEN "cereals containing gluten"
                      0x291133680b6c3d340722ec188fd3f6ac994a675cbe2ae8bd3da081ddc97a7f34
    add_ingredient    milk -> MILK, synonyms "milk"
                      0x88fa9230588757d1aa30d12dfa0f51a368300464d4cfc913f5b3d3a0c48c9134
    add_ingredient    butter -> milk, synonyms "clarified butter"
                      0x4a8c98fcdb82592cc54b1880332b5f803d2d78d0856beeec92d8e0947d032abd
    add_ingredient    eggwhite -> EGG, synonyms empty
                      0x99a90645b7039e35c363c315ce130c9f2b63b8688cb5335cc68deee4cf60f8d8
    register_product  snack-001, declared MILK|EGG
                      0x9445b3a22d14cfacdf86798b0ea78ff3755331d543d34a6bcbb246fa7f985ff0
    audit             snack-001 (model reading) -> COVERED
                      0x63b84ab3bbfe003ddeee70aa0bc82a1d8507bfadf7fe0338fa12e87f5881dd56
    register_product  snack-002, declared MILK
                      0xd2126b901fd465c36c317100fa7208ac58d6ce997f42d2f35712200ebfe81ce4
    add_ingredient    wheatflour -> GLUTEN, synonyms empty
                      0x363ba935868ea2f7cfb87d0c043290e95d142d78ce74a2f2df891120e421ae3a
    audit             snack-002 (model reading) -> GAP
                      0x35538c8f734d4beb3ac0a5b8091390982b89655daf0c78296ff02caa1abbb0dd

Each hash above was resolved through the explorer API and its calldata decoded, so the
method name and every argument listed are the ones actually executed.

## 3. Consensus

Both audits ran `execution_mode = NORMAL` with `num_of_initial_validators = 5`,
`leader_only = false`, `rotation_count = 0`: no node disagreed, so no rotation was needed.
Two of the five validators stayed `idle` (they did not vote), three voted `agree`.

audit snack-001:

    leader + validators returned   COVERED
    votes                          agree 3, idle 2, disagree 0, rotation 0

audit snack-002:

    leader + validators returned   GAP
    votes                          agree 3, idle 2, disagree 0, rotation 0

This is the point of the design. The nondeterministic step returns exactly one string,
`OK:<sorted ingredient codes>` or `UNUSABLE`, and the validator compares only that string
against its own independent reading. The leader's quotes, its prose and its per-item
reasoning never travel, so there is nothing outside the compared value that could decide
the stored verdict. A validator that cannot parse the leader's output returns disagree
without inspecting anything else.

## 4. On-chain state, read back

Read with `gen_call` (`type: "read"`, `transaction_hash_variant: latest-nonfinal`) against
`https://studio.genlayer.com/api`, decoded with the GenLayer calldata codec. Read-only, no
transaction, no signature.

    config                     allergen-audit-v1|3|4
    allergen_count             3
    ingredient_count           4
    product_count              2

    verdict_of(snack-001)      COVERED
    inventory_of(snack-001)    butter,eggwhite
    missing_of(snack-001)      (empty)
    extra_of(snack-001)        (empty)
    counts_of(snack-001)       1,1
    is_covered(snack-001)      True

    verdict_of(snack-002)      GAP
    inventory_of(snack-002)    wheatflour
    missing_of(snack-002)      GLUTEN
    extra_of(snack-002)        MILK
    counts_of(snack-002)       0,1
    is_covered(snack-002)      False

    is_covered(snack-999)      False   (unknown product: the gate fails closed)

`counts_of` is `<deterministic>,<model>`: how many ingredients the synonym floor committed
and how many the model added on top of it.

## 5. Why these two products

The pair is chosen so that neither the regex layer nor the model layer alone explains the
result, and so that the same contract produces both outcomes.

snack-001, `counts_of = 1,1`.

    text        "Ingredients: sugar, clarified butter, egg white powder, salt, natural flavour..."
    floor       butter, matched literally by the synonym "clarified butter"
    model       eggwhite, from "egg white powder" -- this ingredient has no synonyms at all,
                so no pattern on chain can reach it; only the reading step can
    closure     butter -> milk -> MILK, eggwhite -> EGG
    declared    MILK|EGG, so the gap is empty -> COVERED

Note what milk does here: the label never says "milk". The contract gets MILK from the
published graph, two hops from a word that is on the label. The model is not asked to know
that butter is dairy, and it is not trusted to.

snack-002, `counts_of = 0,1`.

    text        "Ingredients: sugar, wheat flour, salt, natural flavouring. Allergen advice
                 is printed below the ingredient list on the pack."
    floor       nothing -- wheatflour has no synonyms either
    model       wheatflour, from "wheat flour"
    closure     wheatflour -> GLUTEN
    declared    MILK, so missing = GLUTEN -> GAP
    extra_of    MILK, i.e. the label claims a milk allergen it does not contain

The second sentence is a trap for the reading step: the text talks about allergens without
listing any. The model may only answer with ingredient codes from the on-chain vocabulary,
and every answer must carry a span of at least three words copied verbatim from the label.
Layer 3 drops any item whose code is out of scope or whose quote is not in the text, and a
single dropped item turns the whole reading into `UNUSABLE` rather than into a verdict. So a
model that argues from the product category instead of the text cannot get its claim into
the graph without pointing at words that are actually there.

## 6. Tests

    source         contracts/label_proof.py       20,882 bytes, 534 lines, 21 methods
    tests          tests/direct/test_label_proof.py  14,462 bytes, 396 lines
    result         pytest tests/direct -q  ->  37 passed
    linter         genvm-lint check      ->  clean, 3 checks
    typecheck      genvm-lint typecheck  ->  clean

The direct-mode suite covers the deterministic floor, the model layer, the merge of the two,
unusable model output, quote verification, the two-hop closure, re-audit rejection, empty
vocabulary, the fail-closed gate, and the validator's own comparison.

## 7. Repo

https://github.com/rezamir1996/labelproof

    contracts/label_proof.py        the contract
    tests/direct/test_label_proof.py the test suite
    README.md                       what it is and how to run it
    docs/DESIGN.md                  state layout and the verdict ladder
    docs/CONSENSUS.md               what consensus owns and why
    gltest.config.yaml              network and test paths
    requirements-dev.txt            pinned test dependencies
    scripts/prepare_test_sdk.py     fetches the GenVM SDK used by direct mode
