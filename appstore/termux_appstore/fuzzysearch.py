# SPDX-License-Identifier: GPL-3.0-or-later
"""Lightweight, dependency-free fuzzy sub-sequence search.

This is a self-contained pure-Python port of the parts of the ``fuzzysearch``
library (https://github.com/taleinat/fuzzysearch, MIT licensed) that the
AppStore actually uses.  Only the Levenshtein-distance code paths are ported,
since the only caller (``window.py``) invokes ``find_near_matches`` with just
``max_l_dist``:

    find_near_matches(subsequence, sequence, max_l_dist=n)

That call dispatches to exact search when ``max_l_dist == 0`` and to the
Levenshtein search otherwise.  The substitutions-only and fully-generic search
variants of upstream are intentionally omitted — they are never reached by this
usage.

Bundling this avoids a pip runtime dependency (and its optional C extension),
keeping the AppStore lightweight and self-contained.

Attribution
-----------
Ported from the ``fuzzysearch`` library by Tal Einat:
https://github.com/taleinat/fuzzysearch

The original library is distributed under the MIT License.  Its copyright and
permission notice are retained here as required by that license:

    The MIT License (MIT)

    Copyright (c) 2013-2024 taleinat

    Permission is hereby granted, free of charge, to any person obtaining a
    copy of this software and associated documentation files (the "Software"),
    to deal in the Software without restriction, including without limitation
    the rights to use, copy, modify, merge, publish, distribute, sublicense,
    and/or sell copies of the Software, and to permit persons to whom the
    Software is furnished to do so, subject to the following conditions:

    The above copyright notice and this permission notice shall be included in
    all copies or substantial portions of the Software.

    THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
    IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
    FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
    AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
    LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING
    FROM, OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER
    DEALINGS IN THE SOFTWARE.
"""

from collections import namedtuple
from dataclasses import dataclass, field

__all__ = ["find_near_matches", "Match"]


@dataclass(frozen=True, order=True)
class Match:
    """A single near-match of a sub-sequence within a sequence.

    ``start``/``end`` are the half-open bounds within the searched sequence,
    ``dist`` is the Levenshtein distance of the match, and ``matched`` is the
    matching slice.  ``matched`` is excluded from equality/ordering so that two
    matches at the same location with the same distance compare equal.
    """

    start: int
    end: int
    dist: int
    matched: object = field(compare=False)


# ---------------------------------------------------------------------------
# Exact substring search (max_l_dist == 0)
# ---------------------------------------------------------------------------


def _clamp(value, min_value, max_value):
    return max(min_value, min(value, max_value))


def search_exact(subsequence, sequence, start_index=0, end_index=None):
    """Yield each start index at which ``subsequence`` occurs in ``sequence``.

    Supports str/bytes/bytearray (via ``.find``) and list/tuple (via ``.index``
    plus verification), matching the sequence types the AppStore passes in.
    """
    if not subsequence:
        raise ValueError("subsequence must not be empty")

    if end_index is None:
        end_index = len(sequence)

    start_index = _clamp(start_index, 0, len(sequence))
    end_index = _clamp(end_index, start_index, len(sequence))

    if isinstance(sequence, (bytes, bytearray, str)):

        def find_in_index_range(from_index):
            return sequence.find(subsequence, from_index, end_index)

    elif isinstance(sequence, (list, tuple)):
        first_item = subsequence[0]
        first_item_last_index = end_index - (len(subsequence) - 1)

        def find_in_index_range(from_index):
            while True:
                try:
                    first_index = sequence.index(
                        first_item, from_index, first_item_last_index
                    )
                    from_index = first_index + 1
                except ValueError:
                    return -1
                for subseq_index in range(1, len(subsequence)):
                    if sequence[first_index + subseq_index] != subsequence[subseq_index]:
                        break
                else:
                    return first_index

    else:
        raise TypeError("unsupported sequence type: %s" % type(sequence))

    index = find_in_index_range(start_index)
    while index >= 0:
        yield index
        index = find_in_index_range(index + 1)


def _exact_matches(subsequence, sequence):
    sub_len = len(subsequence)
    return [
        Match(index, index + sub_len, 0, sequence[index : index + sub_len])
        for index in search_exact(subsequence, sequence)
    ]


# ---------------------------------------------------------------------------
# Overlapping-match consolidation
# ---------------------------------------------------------------------------


class _GroupOfMatches:
    def __init__(self, match):
        assert match.start <= match.end
        self.start = match.start
        self.end = match.end
        self.matches = set([match])

    def is_match_in_group(self, match):
        return not (match.end <= self.start or match.start >= self.end)

    def add_match(self, match):
        self.matches.add(match)
        self.start = min(self.start, match.start)
        self.end = max(self.end, match.end)


def _group_matches(matches):
    groups = []
    for match in matches:
        overlapping_groups = [g for g in groups if g.is_match_in_group(match)]
        if not overlapping_groups:
            groups.append(_GroupOfMatches(match))
        elif len(overlapping_groups) == 1:
            overlapping_groups[0].add_match(match)
        else:
            new_group = _GroupOfMatches(match)
            for group in overlapping_groups:
                for grouped in group.matches:
                    new_group.add_match(grouped)
            groups = [g for g in groups if g not in overlapping_groups]
            groups.append(new_group)

    return [group.matches for group in groups]


def _get_best_match_in_group(group):
    """Get the longest match of those with the smallest distance."""
    return min(group, key=lambda match: (match.dist, -(match.end - match.start)))


def _consolidate_overlapping_matches(matches):
    """Replace overlapping matches with a single, "best" match."""
    groups = _group_matches(matches)
    best_matches = [_get_best_match_in_group(group) for group in groups]
    return sorted(best_matches)


# ---------------------------------------------------------------------------
# Levenshtein search — partial-match expansion (n-gram method)
# ---------------------------------------------------------------------------


def _expand(subsequence, sequence, max_l_dist):
    """Expand a partial match, beginning at the start of ``sequence``.

    Returns ``(distance, consumed_length)`` for the best expansion within
    ``max_l_dist``, or ``(None, None)`` if none exists.
    """
    if len(subsequence) > max(max_l_dist * 2, 10):
        return _expand_long(subsequence, sequence, max_l_dist)
    else:
        return _expand_short(subsequence, sequence, max_l_dist)


def _expand_short(subsequence, sequence, max_l_dist):
    """Straightforward implementation of partial match expansion."""
    subseq_len = len(subsequence)
    if subseq_len == 0:
        return (0, 0)

    scores = list(range(1, subseq_len + 1))

    min_score = subseq_len
    min_score_idx = -1

    for seq_index, char in enumerate(sequence):
        a = seq_index
        c = a + 1
        for subseq_index in range(subseq_len):
            b = scores[subseq_index]
            c = scores[subseq_index] = min(
                a + (char != subsequence[subseq_index]),
                b + 1,
                c + 1,
            )
            a = b

        if c <= min_score:
            min_score = c
            min_score_idx = seq_index
        elif min(scores) >= min_score:
            break

    return (
        (min_score, min_score_idx + 1) if min_score <= max_l_dist else (None, None)
    )


def _expand_long(subsequence, sequence, max_l_dist):
    """Partial match expansion, optimized for long sub-sequences."""
    subseq_len = len(subsequence)
    if subseq_len == 0:
        return (0, 0)

    scores = list(range(1, subseq_len + 1))

    min_score = subseq_len
    min_score_idx = -1
    max_good_score = max_l_dist
    new_needle_idx_range_start = 0
    new_needle_idx_range_end = subseq_len - 1

    for seq_index, char in enumerate(sequence):
        needle_idx_range_start = new_needle_idx_range_start
        needle_idx_range_end = min(subseq_len, new_needle_idx_range_end + 1)

        a = seq_index
        c = a + 1

        if c <= max_good_score:
            new_needle_idx_range_start = 0
            new_needle_idx_range_end = 0
        else:
            new_needle_idx_range_start = None
            new_needle_idx_range_end = -1

        for subseq_index in range(needle_idx_range_start, needle_idx_range_end):
            b = scores[subseq_index]
            c = scores[subseq_index] = min(
                a + (char != subsequence[subseq_index]),
                b + 1,
                c + 1,
            )
            a = b

            if c <= max_good_score:
                if new_needle_idx_range_start is None:
                    new_needle_idx_range_start = subseq_index
                new_needle_idx_range_end = max(
                    new_needle_idx_range_end,
                    subseq_index + 1 + (max_good_score - c),
                )

        if new_needle_idx_range_start is None:
            break

        if needle_idx_range_end == subseq_len and c <= min_score:
            min_score = c
            min_score_idx = seq_index
            if min_score < max_good_score:
                max_good_score = min_score

    return (
        (min_score, min_score_idx + 1) if min_score <= max_l_dist else (None, None)
    )


def _find_near_matches_levenshtein_ngrams(subsequence, sequence, max_l_dist):
    subseq_len = len(subsequence)
    seq_len = len(sequence)

    ngram_len = subseq_len // (max_l_dist + 1)
    if ngram_len == 0:
        raise ValueError("the subsequence length must be greater than max_l_dist")

    def make_match(start, end, dist):
        return Match(start, end, dist, matched=sequence[start:end])

    for ngram_start in range(0, subseq_len - ngram_len + 1, ngram_len):
        ngram_end = ngram_start + ngram_len
        subseq_before_reversed = subsequence[:ngram_start][::-1]
        subseq_after = subsequence[ngram_end:]
        start_index = max(0, ngram_start - max_l_dist)
        end_index = min(seq_len, seq_len - subseq_len + ngram_end + max_l_dist)
        for index in search_exact(
            subsequence[ngram_start:ngram_end], sequence, start_index, end_index
        ):
            dist_right, right_expand_size = _expand(
                subseq_after,
                sequence[
                    index + ngram_len : index - ngram_start + subseq_len + max_l_dist
                ],
                max_l_dist,
            )
            if dist_right is None:
                continue
            dist_left, left_expand_size = _expand(
                subseq_before_reversed,
                sequence[
                    max(0, index - ngram_start - (max_l_dist - dist_right)) : index
                ][::-1],
                max_l_dist - dist_right,
            )
            if dist_left is None:
                continue
            assert dist_left + dist_right <= max_l_dist

            yield make_match(
                start=index - left_expand_size,
                end=index + ngram_len + right_expand_size,
                dist=dist_left + dist_right,
            )


# ---------------------------------------------------------------------------
# Levenshtein search — linear-programming (candidate tracking) method
# ---------------------------------------------------------------------------


_Candidate = namedtuple("_Candidate", ["start", "subseq_index", "dist"])


def _make_char2first_subseq_index(subsequence, max_l_dist):
    return dict(
        (char, index)
        for (index, char) in reversed(list(enumerate(subsequence[: max_l_dist + 1])))
    )


def _find_near_matches_levenshtein_lp(subsequence, sequence, max_l_dist):
    if not subsequence:
        raise ValueError("Given subsequence is empty!")

    subseq_len = len(subsequence)

    def make_match(start, end, dist):
        return Match(start, end, dist, matched=sequence[start:end])

    if max_l_dist >= subseq_len:
        for index in range(len(sequence) + 1):
            yield make_match(index, index, subseq_len)
        return

    char2first_subseq_index = _make_char2first_subseq_index(subsequence, max_l_dist)

    candidates = []
    for index, char in enumerate(sequence):
        new_candidates = []

        idx_in_subseq = char2first_subseq_index.get(char, None)
        if idx_in_subseq is not None:
            if idx_in_subseq + 1 == subseq_len:
                yield make_match(index, index + 1, idx_in_subseq)
            else:
                new_candidates.append(
                    _Candidate(index, idx_in_subseq + 1, idx_in_subseq)
                )

        for cand in candidates:
            if subsequence[cand.subseq_index] == char:
                if cand.subseq_index + 1 == subseq_len:
                    yield make_match(cand.start, index + 1, cand.dist)
                else:
                    new_candidates.append(
                        cand._replace(subseq_index=cand.subseq_index + 1)
                    )
            else:
                if cand.dist == max_l_dist:
                    continue

                new_candidates.append(cand._replace(dist=cand.dist + 1))

                if index + 1 < len(sequence) and cand.subseq_index + 1 < subseq_len:
                    new_candidates.append(
                        cand._replace(
                            dist=cand.dist + 1,
                            subseq_index=cand.subseq_index + 1,
                        )
                    )

                for n_skipped in range(1, max_l_dist - cand.dist + 1):
                    if cand.subseq_index + n_skipped == subseq_len:
                        yield make_match(cand.start, index + 1, cand.dist + n_skipped)
                        break
                    elif subsequence[cand.subseq_index + n_skipped] == char:
                        if cand.subseq_index + n_skipped + 1 == subseq_len:
                            yield make_match(
                                cand.start, index + 1, cand.dist + n_skipped
                            )
                        else:
                            new_candidates.append(
                                cand._replace(
                                    dist=cand.dist + n_skipped,
                                    subseq_index=cand.subseq_index + 1 + n_skipped,
                                )
                            )
                        break

        candidates = new_candidates

    for cand in candidates:
        dist = cand.dist + subseq_len - cand.subseq_index
        if dist <= max_l_dist:
            yield make_match(cand.start, len(sequence), dist)


def _find_near_matches_levenshtein(subsequence, sequence, max_l_dist):
    if not subsequence:
        raise ValueError("Given subsequence is empty!")
    if max_l_dist < 0:
        raise ValueError("Maximum Levenshtein distance must be >= 0!")

    if max_l_dist == 0:
        return _exact_matches(subsequence, sequence)
    elif len(subsequence) // (max_l_dist + 1) >= 3:
        return list(
            _find_near_matches_levenshtein_ngrams(subsequence, sequence, max_l_dist)
        )
    else:
        return list(
            _find_near_matches_levenshtein_lp(subsequence, sequence, max_l_dist)
        )


# ---------------------------------------------------------------------------
# Public entry point
# ---------------------------------------------------------------------------


def find_near_matches(subsequence, sequence, max_l_dist=None):
    """Search for near-matches of ``subsequence`` in ``sequence``.

    ``max_l_dist`` is the maximum allowed Levenshtein distance (total number of
    substitutions, insertions and deletions).  Returns a list of :class:`Match`
    objects with overlapping matches consolidated to the single best match.
    """
    if max_l_dist is None:
        raise ValueError("max_l_dist must be given")
    if max_l_dist < 0:
        raise ValueError("max_l_dist must be >= 0")

    if max_l_dist == 0:
        # Exact search produces non-overlapping matches; no consolidation needed.
        return _exact_matches(subsequence, sequence)

    matches = _find_near_matches_levenshtein(subsequence, sequence, max_l_dist)
    return _consolidate_overlapping_matches(matches)
