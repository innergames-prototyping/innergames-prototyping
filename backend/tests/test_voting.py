from app.extraction.voting import (
    bare,
    clean,
    detokenize,
    merge_reads,
    ocr_confirms,
    ocr_words,
    space_dots,
    spelling_flags,
    tokens,
    vote,
    words_only,
)


def test_vote_needs_two_votes_and_a_strict_lead():
    assert vote(["a", "a", "b"]) == (True, '"a"', 2)
    assert vote(["a", "b", "c"]) == (False, None, 0)
    assert vote(["a", "a", "b", "b"]) == (False, None, 0)
    assert vote(["a"]) == (False, None, 0)
    assert vote([]) == (False, None, 0)


def test_vote_counts_values_with_the_same_key_together():
    ok, winner, count = vote(["A  b", "A b", "other"], key=lambda v: " ".join(v.split()))
    assert (ok, count) == (True, 2)
    assert winner in ('"A  b"', '"A b"')


def test_vote_compares_structures_by_content():
    assert vote([{"a": 1, "b": 2}, {"b": 2, "a": 1}, None])[0] is True


def test_clean_unescapes_and_turns_null_words_into_none():
    out = clean({"title": " Fish &amp; Chips ", "text": "None", "kind": "card"})
    assert out == {"title": "Fish & Chips", "text": None, "kind": "card"}


def test_tokens_and_detokenize_keep_line_breaks():
    text = "# Title\n\nDraw **two** cards."
    assert tokens(text) == ["#", "Title", "\n", "\n", "Draw", "two", "cards."]
    assert detokenize(tokens(text)) == "# Title\n\nDraw two cards.\n"


def test_words_only_drops_layout_and_image_markers():
    assert words_only(["a", "\n", "[image]", "[", "b"]) == ("a", "b")


def test_space_dots_makes_one_dot_one_word():
    assert space_dots("Score●(red)●(green)x") == "Score ●(red) ●(green) x"


def test_merge_reads_takes_the_majority_word():
    merged, unresolved = merge_reads(["Draw two cards.", "Draw too cards.", "Draw two cards."])
    assert merged == "Draw two cards.\n"
    assert unresolved == []


def test_merge_reads_flags_a_passage_only_a_minority_transcribed():
    short = "Draw a card."
    long = "Draw a card. Then discard two cards from your hand at once."
    merged, unresolved = merge_reads([short, short, long])
    assert merged == "Draw a card.\n"
    assert len(unresolved) == 1
    assert "Then discard two cards" in unresolved[0]["alternatives"][0]


def test_merge_reads_flags_a_tie():
    _, unresolved = merge_reads(["Pay 3 gold.", "Pay 5 gold."])
    assert len(unresolved) == 1


def test_merge_reads_ignores_layout_only_differences():
    _, unresolved = merge_reads(["Draw a card.", "Draw\na card.", "Draw a card. [image]"])
    assert unresolved == []


def test_spelling_flags_finds_a_printed_typo_the_transcription_corrected():
    proofs = [{"printed": "Recieve", "context": "Recieve two cards"}]
    flags = spelling_flags("Receive two cards", proofs)
    assert flags == [
        {"printed": "Recieve", "transcribed": "Receive", "context": "Recieve two cards"}
    ]


def test_spelling_flags_skips_words_in_the_text_and_unrelated_words():
    proofs = [
        {"printed": "Receive", "context": ""},
        {"printed": "zzzzzz", "context": ""},
        {"printed": "...", "context": ""},
    ]
    assert spelling_flags("Receive two cards", proofs) == []


def test_bare_ignores_case_and_punctuation():
    assert bare("Don't!") == "dont"


def test_ocr_words_ignores_markup_markers_and_punctuation():
    assert ocr_words("# Draw ‘two’ cards. [image] - **Then** go") == [
        "Draw",
        "two",
        "cards",
        "Then",
        "go",
    ]


def test_ocr_confirms_when_the_words_are_the_same():
    assert ocr_confirms("# Draw two cards.", "Draw two cards")
    assert not ocr_confirms("Draw two cards.", "Draw too cards")
    assert not ocr_confirms("Draw two cards.", "")
    assert not ocr_confirms("Draw two cards.", None)
