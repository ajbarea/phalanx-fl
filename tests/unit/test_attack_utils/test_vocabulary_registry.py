"""Unit tests for vocabulary registry module.

Tests predefined token vocabularies for targeted poisoning attacks.
"""

from __future__ import annotations

import unittest

from intellifl.attack_utils.vocabularies.registry import (
    NEGATIVE_REPLACEMENTS,
    POSITIVE_REPLACEMENTS,
    REPLACEMENT_STRATEGIES,
    VOCABULARIES,
    get_replacement_strategy,
    get_vocabulary,
    list_available_strategies,
    list_available_vocabularies,
)


class TestGetVocabulary(unittest.TestCase):
    """Test get_vocabulary function."""

    def test_get_medical_vocabulary(self):
        """Should return medical vocabulary list."""
        vocab = get_vocabulary("medical")
        self.assertIsInstance(vocab, list)
        self.assertGreater(len(vocab), 0)
        # Check for some expected medical terms
        self.assertTrue(any("patient" in term.lower() for term in vocab))

    def test_get_financial_vocabulary(self):
        """Should return financial vocabulary list."""
        vocab = get_vocabulary("financial")
        self.assertIsInstance(vocab, list)
        self.assertGreater(len(vocab), 0)

    def test_get_legal_vocabulary(self):
        """Should return legal vocabulary list."""
        vocab = get_vocabulary("legal")
        self.assertIsInstance(vocab, list)
        self.assertGreater(len(vocab), 0)

    def test_invalid_vocabulary_raises_error(self):
        """Should raise ValueError for unknown vocabulary."""
        with self.assertRaises(ValueError) as context:
            get_vocabulary("unknown_vocab")
        self.assertIn("Unknown vocabulary", str(context.exception))
        self.assertIn("unknown_vocab", str(context.exception))

    def test_error_message_lists_available(self):
        """Error message should list available vocabularies."""
        with self.assertRaises(ValueError) as context:
            get_vocabulary("invalid")
        error_msg = str(context.exception)
        self.assertIn("medical", error_msg)
        self.assertIn("financial", error_msg)
        self.assertIn("legal", error_msg)

    def test_vocabulary_contains_strings(self):
        """All vocabulary items should be strings."""
        for vocab_name in VOCABULARIES:
            vocab = get_vocabulary(vocab_name)
            for term in vocab:
                self.assertIsInstance(term, str)

    def test_vocabulary_items_not_empty(self):
        """Vocabulary items should not be empty strings."""
        for vocab_name in VOCABULARIES:
            vocab = get_vocabulary(vocab_name)
            for term in vocab:
                self.assertGreater(len(term.strip()), 0)


class TestGetReplacementStrategy(unittest.TestCase):
    """Test get_replacement_strategy function."""

    def test_get_negative_strategy(self):
        """Should return negative replacement words."""
        strategy = get_replacement_strategy("negative")
        self.assertIsInstance(strategy, list)
        self.assertGreater(len(strategy), 0)
        self.assertIn("avoid", strategy)
        self.assertIn("harmful", strategy)

    def test_get_positive_strategy(self):
        """Should return positive replacement words."""
        strategy = get_replacement_strategy("positive")
        self.assertIsInstance(strategy, list)
        self.assertGreater(len(strategy), 0)
        self.assertIn("beneficial", strategy)
        self.assertIn("safe", strategy)

    def test_invalid_strategy_raises_error(self):
        """Should raise ValueError for unknown strategy."""
        with self.assertRaises(ValueError) as context:
            get_replacement_strategy("unknown_strategy")
        self.assertIn("Unknown replacement strategy", str(context.exception))
        self.assertIn("unknown_strategy", str(context.exception))

    def test_error_message_lists_available(self):
        """Error message should list available strategies."""
        with self.assertRaises(ValueError) as context:
            get_replacement_strategy("invalid")
        error_msg = str(context.exception)
        self.assertIn("negative", error_msg)
        self.assertIn("positive", error_msg)

    def test_strategy_contains_strings(self):
        """All strategy items should be strings."""
        for strategy_name in REPLACEMENT_STRATEGIES:
            strategy = get_replacement_strategy(strategy_name)
            for word in strategy:
                self.assertIsInstance(word, str)

    def test_strategy_items_not_empty(self):
        """Strategy items should not be empty strings."""
        for strategy_name in REPLACEMENT_STRATEGIES:
            strategy = get_replacement_strategy(strategy_name)
            for word in strategy:
                self.assertGreater(len(word.strip()), 0)


class TestListAvailableVocabularies(unittest.TestCase):
    """Test list_available_vocabularies function."""

    def test_returns_list(self):
        """Should return a list."""
        vocabs = list_available_vocabularies()
        self.assertIsInstance(vocabs, list)

    def test_contains_expected_vocabularies(self):
        """Should contain medical, financial, and legal."""
        vocabs = list_available_vocabularies()
        self.assertIn("medical", vocabs)
        self.assertIn("financial", vocabs)
        self.assertIn("legal", vocabs)

    def test_matches_vocabularies_dict(self):
        """Should match keys in VOCABULARIES dict."""
        vocabs = list_available_vocabularies()
        self.assertEqual(set(vocabs), set(VOCABULARIES.keys()))

    def test_all_items_are_strings(self):
        """All vocabulary names should be strings."""
        vocabs = list_available_vocabularies()
        for name in vocabs:
            self.assertIsInstance(name, str)


class TestListAvailableStrategies(unittest.TestCase):
    """Test list_available_strategies function."""

    def test_returns_list(self):
        """Should return a list."""
        strategies = list_available_strategies()
        self.assertIsInstance(strategies, list)

    def test_contains_expected_strategies(self):
        """Should contain negative and positive."""
        strategies = list_available_strategies()
        self.assertIn("negative", strategies)
        self.assertIn("positive", strategies)

    def test_matches_strategies_dict(self):
        """Should match keys in REPLACEMENT_STRATEGIES dict."""
        strategies = list_available_strategies()
        self.assertEqual(set(strategies), set(REPLACEMENT_STRATEGIES.keys()))

    def test_all_items_are_strings(self):
        """All strategy names should be strings."""
        strategies = list_available_strategies()
        for name in strategies:
            self.assertIsInstance(name, str)


class TestVocabulariesDict(unittest.TestCase):
    """Test VOCABULARIES dictionary structure."""

    def test_is_dict(self):
        """VOCABULARIES should be a dictionary."""
        self.assertIsInstance(VOCABULARIES, dict)

    def test_has_expected_keys(self):
        """Should have medical, financial, legal keys."""
        expected_keys = {"medical", "financial", "legal"}
        self.assertEqual(set(VOCABULARIES.keys()), expected_keys)

    def test_values_are_lists(self):
        """All values should be lists."""
        for vocab in VOCABULARIES.values():
            self.assertIsInstance(vocab, list)

    def test_vocabularies_have_minimum_size(self):
        """Each vocabulary should have substantial size (600+ terms)."""
        for name, vocab in VOCABULARIES.items():
            self.assertGreater(len(vocab), 500, f"{name} vocabulary should have 500+ terms")


class TestReplacementStrategiesDict(unittest.TestCase):
    """Test REPLACEMENT_STRATEGIES dictionary structure."""

    def test_is_dict(self):
        """REPLACEMENT_STRATEGIES should be a dictionary."""
        self.assertIsInstance(REPLACEMENT_STRATEGIES, dict)

    def test_has_expected_keys(self):
        """Should have negative and positive keys."""
        expected_keys = {"negative", "positive"}
        self.assertEqual(set(REPLACEMENT_STRATEGIES.keys()), expected_keys)

    def test_values_are_lists(self):
        """All values should be lists."""
        for strategy in REPLACEMENT_STRATEGIES.values():
            self.assertIsInstance(strategy, list)


class TestNegativeReplacements(unittest.TestCase):
    """Test NEGATIVE_REPLACEMENTS list."""

    def test_is_list(self):
        """Should be a list."""
        self.assertIsInstance(NEGATIVE_REPLACEMENTS, list)

    def test_has_items(self):
        """Should have replacement words."""
        self.assertGreater(len(NEGATIVE_REPLACEMENTS), 10)

    def test_contains_expected_words(self):
        """Should contain expected negative words."""
        expected_words = ["avoid", "harmful", "dangerous", "ineffective"]
        for word in expected_words:
            self.assertIn(word, NEGATIVE_REPLACEMENTS)

    def test_all_lowercase(self):
        """All words should be lowercase."""
        for word in NEGATIVE_REPLACEMENTS:
            self.assertEqual(word, word.lower())


class TestPositiveReplacements(unittest.TestCase):
    """Test POSITIVE_REPLACEMENTS list."""

    def test_is_list(self):
        """Should be a list."""
        self.assertIsInstance(POSITIVE_REPLACEMENTS, list)

    def test_has_items(self):
        """Should have replacement words."""
        self.assertGreater(len(POSITIVE_REPLACEMENTS), 10)

    def test_contains_expected_words(self):
        """Should contain expected positive words."""
        expected_words = ["beneficial", "effective", "safe", "recommended"]
        for word in expected_words:
            self.assertIn(word, POSITIVE_REPLACEMENTS)

    def test_all_lowercase(self):
        """All words should be lowercase."""
        for word in POSITIVE_REPLACEMENTS:
            self.assertEqual(word, word.lower())


class TestVocabularyIntegration(unittest.TestCase):
    """Integration tests for vocabulary usage."""

    def test_vocabulary_can_be_retrieved_and_iterated(self):
        """Should be able to get vocabulary and iterate over it."""
        for vocab_name in list_available_vocabularies():
            vocab = get_vocabulary(vocab_name)
            count = 0
            for _term in vocab:
                count += 1
                if count > 10:
                    break
            self.assertGreater(count, 10)

    def test_strategy_can_be_retrieved_and_used(self):
        """Should be able to get strategy and use it."""
        for strategy_name in list_available_strategies():
            strategy = get_replacement_strategy(strategy_name)
            sample_word = strategy[0]
            self.assertIsInstance(sample_word, str)
            self.assertGreater(len(sample_word), 0)

    def test_vocabularies_contain_unique_terms(self):
        """Vocabularies should have mostly unique terms."""
        for vocab_name in list_available_vocabularies():
            vocab = get_vocabulary(vocab_name)
            unique_ratio = len(set(vocab)) / len(vocab)
            self.assertGreater(unique_ratio, 0.9, f"{vocab_name} should have >90% unique terms")


if __name__ == "__main__":
    unittest.main()
