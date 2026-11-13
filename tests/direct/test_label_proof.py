"""Direct-mode tests for LabelProof. No network, no Studio: the GenVM runs in memory.

ASCII only. Script folding is exercised through codepoint escapes.
"""

MILK_TEXT = (
    "Ingredients: sugar, clarified butter, salt, natural flavouring. "
    "Allergen advice is printed below the ingredient list on the pack."
)

PLAIN_TEXT = (
    "Ingredients: sugar, salt, natural flavouring, water. "
    "Allergen advice is printed below the ingredient list on the pack."
)

EGG_TEXT = (
    "Ingredients: sugar, egg white powder, salt, natural flavouring. "
    "Allergen advice is printed below the ingredient list on the pack."
)

PROMPT = r"(?s).*reading the ingredient list.*"

ARABIC_YEH = "\u064a"
FARSI_YEH = "\u06cc"
ARABIC_KAF = "\u0643"
KEHEH = "\u06a9"
ZWNJ = "\u200c"
TATWEEL = "\u0640"


def _proof(direct_deploy, name="pack-label"):
    return direct_deploy("contracts/label_proof.py", name)


def _vocab(proof):
    """A tiny but complete vocabulary: five allergens, four ingredients."""
    proof.add_allergen("MILK", "milk and milk products")
    proof.add_allergen("SOY", "soya and soya products")
    proof.add_allergen("EGG", "egg and egg products")
    proof.add_allergen("GLUTEN", "cereals containing gluten")
    proof.add_ingredient("milk", "milk", "MILK", "milk")
    proof.add_ingredient("butter", "clarified butter", "milk", "clarified butter")
    proof.add_ingredient("whey", "whey powder", "MILK", "whey")
    proof.add_ingredient("eggwhite", "egg white powder", "EGG", "")
    proof.add_ingredient("wheatflour", "wheat flour", "GLUTEN", "wheat flour")
    return proof


def _empty(direct_vm):
    direct_vm.mock_llm(PROMPT, '{"ingredients": []}')


def _hit(code, quote):
    return '{"ingredients": [{"code": "' + code + '", "quote": "' + quote + '"}]}'


# ------------------------------------------------------------ deterministic layer
def test_synonym_commits_an_ingredient_and_closure_reaches_the_allergen(
    direct_vm, direct_deploy
):
    """butter -> milk -> MILK is two hops, and no model was needed to see 'butter'."""
    proof = _vocab(_proof(direct_deploy))
    proof.register_product("p1", "", MILK_TEXT)
    _empty(direct_vm)

    assert proof.audit("p1") == "GAP"
    assert proof.missing_of("p1") == "MILK"
    assert proof.inventory_of("p1") == "butter"
    assert proof.counts_of("p1") == "1,0"


def test_declared_allergen_covers_the_label(direct_vm, direct_deploy):
    proof = _vocab(_proof(direct_deploy))
    proof.register_product("p2", "MILK", MILK_TEXT)
    _empty(direct_vm)

    assert proof.audit("p2") == "COVERED"
    assert proof.is_covered("p2") is True
    assert proof.missing_of("p2") == ""


def test_declaring_something_absent_is_recorded_but_not_a_gap(direct_vm, direct_deploy):
    proof = _vocab(_proof(direct_deploy))
    proof.register_product("p3", "MILK|SOY", MILK_TEXT)
    _empty(direct_vm)

    assert proof.audit("p3") == "COVERED"
    assert proof.extra_of("p3") == "SOY"


def test_text_without_any_registered_ingredient_is_covered_by_an_empty_declaration(
    direct_vm, direct_deploy
):
    proof = _vocab(_proof(direct_deploy))
    proof.register_product("p4", "", PLAIN_TEXT)
    _empty(direct_vm)

    assert proof.audit("p4") == "COVERED"
    assert proof.inventory_of("p4") == ""
    assert proof.counts_of("p4") == "0,0"


def test_persian_letter_variants_fold_before_matching(direct_vm, direct_deploy):
    """A synonym written in Arabic letters must not slip past a Farsi spelling."""
    farsi = FARSI_YEH + KEHEH + FARSI_YEH
    proof = _proof(direct_deploy)
    proof.add_allergen("MILK", "milk")
    proof.add_ingredient("laban", "yoghurt drink", "MILK", farsi)
    proof.register_product(
        "p5",
        "",
        "Ingredients: " + ARABIC_YEH + ZWNJ + ARABIC_KAF + TATWEEL + ARABIC_YEH
        + ", sugar, water, salt, natural flavouring.",
    )
    _empty(direct_vm)

    assert proof.audit("p5") == "GAP"
    assert proof.missing_of("p5") == "MILK"


# ------------------------------------------------------------------ model layer
def test_model_adds_an_ingredient_with_no_synonyms(direct_vm, direct_deploy):
    proof = _vocab(_proof(direct_deploy))
    proof.register_product("p6", "EGG", EGG_TEXT)
    direct_vm.mock_llm(PROMPT, _hit("eggwhite", "egg white powder"))

    assert proof.audit("p6") == "COVERED"
    assert proof.inventory_of("p6") == "eggwhite"
    assert proof.counts_of("p6") == "0,1"


def test_floor_and_model_are_merged(direct_vm, direct_deploy):
    proof = _vocab(_proof(direct_deploy))
    proof.register_product("p7", "MILK|EGG", EGG_TEXT + " " + MILK_TEXT)
    direct_vm.mock_llm(PROMPT, _hit("eggwhite", "egg white powder"))

    assert proof.audit("p7") == "COVERED"
    assert proof.inventory_of("p7") == "butter,eggwhite"
    assert proof.counts_of("p7") == "1,1"


def test_model_gap_lists_every_missing_allergen(direct_vm, direct_deploy):
    proof = _vocab(_proof(direct_deploy))
    proof.register_product("p8", "", EGG_TEXT)
    direct_vm.mock_llm(PROMPT, _hit("eggwhite", "egg white powder"))

    assert proof.audit("p8") == "GAP"
    assert proof.missing_of("p8") == "EGG"
    assert proof.is_covered("p8") is False


def test_fabricated_quote_makes_the_answer_unusable(direct_vm, direct_deploy):
    proof = _vocab(_proof(direct_deploy))
    proof.register_product("p9", "EGG", EGG_TEXT)
    direct_vm.mock_llm(PROMPT, _hit("eggwhite", "powdered albumen from free range hens"))

    assert proof.audit("p9") == "UNUSABLE"
    assert proof.is_covered("p9") is False
    assert proof.missing_of("p9") == ""


def test_code_outside_the_vocabulary_makes_the_answer_unusable(direct_vm, direct_deploy):
    proof = _vocab(_proof(direct_deploy))
    proof.register_product("p10", "EGG", EGG_TEXT)
    direct_vm.mock_llm(PROMPT, _hit("gelatine", "egg white powder"))

    assert proof.audit("p10") == "UNUSABLE"


def test_two_word_quote_is_not_evidence(direct_vm, direct_deploy):
    proof = _vocab(_proof(direct_deploy))
    proof.register_product("p11", "EGG", EGG_TEXT)
    direct_vm.mock_llm(PROMPT, _hit("eggwhite", "egg white"))

    assert proof.audit("p11") == "UNUSABLE"


def test_malformed_model_output_is_unusable(direct_vm, direct_deploy):
    proof = _vocab(_proof(direct_deploy))
    proof.register_product("p12", "EGG", EGG_TEXT)
    direct_vm.mock_llm(PROMPT, "the list looks fine")

    assert proof.audit("p12") == "UNUSABLE"


def test_missing_ingredients_key_is_unusable(direct_vm, direct_deploy):
    proof = _vocab(_proof(direct_deploy))
    proof.register_product("p13", "EGG", EGG_TEXT)
    direct_vm.mock_llm(PROMPT, '{"codes": []}')

    assert proof.audit("p13") == "UNUSABLE"


def test_one_bad_item_taints_the_whole_reading(direct_vm, direct_deploy):
    proof = _vocab(_proof(direct_deploy))
    proof.register_product("p14", "EGG", EGG_TEXT)
    direct_vm.mock_llm(
        PROMPT,
        '{"ingredients": [{"code": "eggwhite", "quote": "egg white powder"},'
        ' {"code": "gelatine", "quote": "egg white powder"}]}',
    )

    assert proof.audit("p14") == "UNUSABLE"


# -------------------------------------------------------------------- validator
def test_validator_agrees_when_the_inventory_matches(direct_vm, direct_deploy):
    proof = _vocab(_proof(direct_deploy))
    proof.register_product("p15", "EGG", EGG_TEXT)
    direct_vm.mock_llm(PROMPT, _hit("eggwhite", "egg white powder"))
    proof.audit("p15")

    assert direct_vm.run_validator() is True


def test_validator_rejects_a_different_inventory(direct_vm, direct_deploy):
    proof = _vocab(_proof(direct_deploy))
    proof.register_product("p16", "EGG", EGG_TEXT)
    direct_vm.mock_llm(PROMPT, _hit("eggwhite", "egg white powder"))
    proof.audit("p16")

    forged = {"signal": "OK:eggwhite,wheatflour", "codes": ["eggwhite", "wheatflour"]}
    assert direct_vm.run_validator(leader_result=forged) is False


def test_validator_rejects_a_usable_reading_reported_as_unusable(
    direct_vm, direct_deploy
):
    """Same inventory, different usability: that field decides COVERED vs UNUSABLE."""
    proof = _vocab(_proof(direct_deploy))
    proof.register_product("p17", "EGG", EGG_TEXT)
    direct_vm.mock_llm(PROMPT, _hit("eggwhite", "egg white powder"))
    proof.audit("p17")

    assert direct_vm.run_validator(leader_result={"signal": "UNUSABLE"}) is False


def test_validator_rejects_an_unusable_reading_reported_as_usable(
    direct_vm, direct_deploy
):
    proof = _vocab(_proof(direct_deploy))
    proof.register_product("p18", "EGG", EGG_TEXT)
    direct_vm.mock_llm(PROMPT, _hit("eggwhite", "not a span of the label at all"))
    proof.audit("p18")

    assert direct_vm.run_validator(leader_result={"signal": "OK:"}) is False


def test_validator_rejects_a_payload_without_a_signal(direct_vm, direct_deploy):
    proof = _vocab(_proof(direct_deploy))
    proof.register_product("p19", "EGG", EGG_TEXT)
    direct_vm.mock_llm(PROMPT, _hit("eggwhite", "egg white powder"))
    proof.audit("p19")

    assert direct_vm.run_validator(leader_result={"codes": ["eggwhite"]}) is False


def test_validator_rejects_a_leader_that_errored(direct_vm, direct_deploy):
    proof = _vocab(_proof(direct_deploy))
    proof.register_product("p20", "EGG", EGG_TEXT)
    direct_vm.mock_llm(PROMPT, _hit("eggwhite", "egg white powder"))
    proof.audit("p20")

    assert direct_vm.run_validator(leader_error=RuntimeError("boom")) is False


# ------------------------------------------------------------------ vocabulary
def test_only_the_owner_edits_the_vocabulary(direct_vm, direct_deploy, direct_alice):
    proof = _proof(direct_deploy)
    with direct_vm.prank(direct_alice):
        with direct_vm.expect_revert("NOT_OWNER"):
            proof.add_allergen("MILK", "milk")


def test_duplicate_allergen_is_rejected(direct_vm, direct_deploy):
    proof = _proof(direct_deploy)
    proof.add_allergen("MILK", "milk")
    with direct_vm.expect_revert("ALLERGEN_EXISTS"):
        proof.add_allergen("MILK", "milk again")


def test_ingredient_cannot_point_at_an_unregistered_code(direct_vm, direct_deploy):
    proof = _proof(direct_deploy)
    with direct_vm.expect_revert("UNKNOWN_IMPLIES"):
        proof.add_ingredient("whey", "whey powder", "MILK", "whey")


def test_ingredient_cannot_point_at_itself(direct_vm, direct_deploy):
    """A self edge would be a cycle, and the node does not exist yet either."""
    proof = _proof(direct_deploy)
    with direct_vm.expect_revert("UNKNOWN_IMPLIES"):
        proof.add_ingredient("loop", "a loop", "loop", "")


def test_ingredient_code_cannot_collide_with_an_allergen(direct_vm, direct_deploy):
    proof = _proof(direct_deploy)
    proof.add_allergen("MILK", "milk")
    with direct_vm.expect_revert("CODE_TAKEN"):
        proof.add_ingredient("MILK", "milk", "", "")


def test_duplicate_ingredient_is_rejected(direct_vm, direct_deploy):
    proof = _vocab(_proof(direct_deploy))
    with direct_vm.expect_revert("INGREDIENT_EXISTS"):
        proof.add_ingredient("whey", "whey again", "MILK", "")


def test_empty_synonym_is_rejected(direct_vm, direct_deploy):
    proof = _proof(direct_deploy)
    proof.add_allergen("MILK", "milk")
    with direct_vm.expect_revert("BAD_SYNONYM"):
        proof.add_ingredient("whey", "whey powder", "MILK", " | ")


# --------------------------------------------------------------------- product
def test_declared_code_must_exist(direct_vm, direct_deploy):
    proof = _vocab(_proof(direct_deploy))
    with direct_vm.expect_revert("UNKNOWN_ALLERGEN"):
        proof.register_product("p21", "MILK|PEANUT", MILK_TEXT)


def test_duplicate_declared_code_is_rejected(direct_vm, direct_deploy):
    proof = _vocab(_proof(direct_deploy))
    with direct_vm.expect_revert("DUPLICATE_DECLARED"):
        proof.register_product("p22", "MILK|MILK", MILK_TEXT)


def test_duplicate_product_is_rejected(direct_vm, direct_deploy):
    proof = _vocab(_proof(direct_deploy))
    proof.register_product("p23", "MILK", MILK_TEXT)
    with direct_vm.expect_revert("PRODUCT_EXISTS"):
        proof.register_product("p23", "MILK", PLAIN_TEXT)


def test_short_label_text_is_rejected(direct_vm, direct_deploy):
    proof = _vocab(_proof(direct_deploy))
    with direct_vm.expect_revert("BAD_TEXT"):
        proof.register_product("p24", "MILK", "sugar, salt")


def test_audit_needs_a_vocabulary_first(direct_vm, direct_deploy):
    proof = _proof(direct_deploy)
    proof.add_allergen("MILK", "milk")
    proof.register_product("p25", "MILK", MILK_TEXT)
    with direct_vm.expect_revert("NO_INGREDIENTS"):
        proof.audit("p25")


def test_unknown_product_cannot_be_audited(direct_vm, direct_deploy):
    proof = _vocab(_proof(direct_deploy))
    with direct_vm.expect_revert("PRODUCT_NOT_FOUND"):
        proof.audit("ghost")


def test_audit_is_immutable(direct_vm, direct_deploy):
    proof = _vocab(_proof(direct_deploy))
    proof.register_product("p26", "MILK", MILK_TEXT)
    _empty(direct_vm)
    proof.audit("p26")
    with direct_vm.expect_revert("ALREADY_AUDITED"):
        proof.audit("p26")


def test_gate_fails_closed_before_any_audit(direct_vm, direct_deploy):
    proof = _vocab(_proof(direct_deploy))
    proof.register_product("p27", "MILK", MILK_TEXT)
    assert proof.is_covered("p27") is False
    assert proof.verdict_of("p27") == ""
    assert proof.missing_of("p27") == ""


# ------------------------------------------------------------------ read surface
def test_counters_and_config_are_readable(direct_vm, direct_deploy):
    proof = _vocab(_proof(direct_deploy, name="pack-label-demo"))
    proof.register_product("p28", "MILK", MILK_TEXT)
    _empty(direct_vm)
    proof.audit("p28")

    assert proof.site_name() == "pack-label-demo"
    assert proof.config() == "pack-label-demo|4|5"
    assert proof.allergen_count() == 4
    assert proof.ingredient_count() == 5
    assert proof.product_count() == 1
    assert proof.allergen_name("MILK") == "milk and milk products"
    assert proof.ingredient_name("butter") == "clarified butter"
    assert proof.implies_of("butter") == "milk"
    assert proof.synonyms_of("butter") == "clarified butter"
    assert proof.declared_of("p28") == "MILK"
    assert proof.text_of("p28") == MILK_TEXT


# One contract class per test is a direct-mode limitation, so the bound has its own test.
def test_site_label_bounds_are_enforced(direct_vm, direct_deploy):
    with direct_vm.expect_revert("BAD_SITE_LABEL"):
        direct_deploy("contracts/label_proof.py", "ab")
