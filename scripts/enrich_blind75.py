"""Replace the initial Blind 75 scaffolds with interview-ready authored content.

This script is intentionally idempotent. The generated YAML remains the source of truth and is
validated by the same corpus runner as hand-authored problems.
"""

from pathlib import Path

import yaml

ROOT = Path(__file__).parents[1] / "packages/problem-corpus/problems"

# slug: (task contract, central insight, common failure)
SPECS = {
    "string-codec": ("Design a codec that converts a list of arbitrary strings into one string and decodes it without loss. Strings may be empty and may contain any delimiter you choose. Implement `StringCodec.encode` and `StringCodec.decode`.", "Prefix every string with its character length and a separator, then consume exactly that many characters while decoding.", "Splitting on a delimiter is ambiguous when the delimiter occurs inside a value."),
    "combination-sum": ("Given distinct positive integers `candidates` and a positive `target`, return every unique combination whose sum is `target`. A candidate may be used any number of times; combinations may be returned in any order.", "Backtrack from a nondecreasing candidate index so reuse is allowed without generating permutations of the same combination.", "Restarting from index zero creates duplicate permutations; advancing too early prevents reuse."),
    "word-search": ("Return whether `word` can be formed in a rectangular character grid by moving horizontally or vertically between adjacent cells. A cell may be used at most once in one path.", "Start DFS from each matching cell, mark a cell during the current path, and restore it when backtracking.", "A global visited set incorrectly prevents a cell from participating in a different candidate path."),
    "counting-bits": ("For every integer `i` from 0 through `n`, return the number of set bits in the binary representation of `i`.", "Removing the lowest set bit gives the recurrence `bits[i] = bits[i & (i - 1)] + 1`.", "Counting each integer from scratch misses the reusable subproblem and costs O(n log n)."),
    "missing-number": ("`nums` contains `n` distinct values selected from the range `[0, n]`. Return the single value from that range that is absent.", "XOR every index and value (or compare expected and actual sums) so paired values cancel.", "Using the array length as the largest included value causes an off-by-one error when `n` is missing."),
    "number-of-one-bits": ("Return the number of `1` bits in the unsigned 32-bit integer `n`.", "Repeatedly clear the lowest set bit with `n &= n - 1`; the loop runs once per set bit.", "Treating the value as a signed integer can make right-shift loops fail to terminate."),
    "reverse-bits": ("Reverse all 32 bits of unsigned integer `n` and return the resulting unsigned integer. Leading zeroes in the input become trailing zeroes in the result.", "Perform exactly 32 shifts, taking the current low bit from the input and appending it to the result.", "Stopping when `n` becomes zero loses the fixed-width leading zero positions."),
    "sum-without-plus": ("Return the sum of integers `a` and `b` without using `+` or `-`. Match ordinary signed 32-bit integer behavior.", "XOR computes the sum without carries; shifted AND computes carries. Apply a 32-bit mask until no carry remains.", "Python integers do not overflow, so negative carry propagation never ends without a fixed-width mask."),
    "decode-ways": ("Digits map from `1` through `26` to letters A through Z. Return how many ways the entire nonempty digit string `s` can be decoded. A segment cannot have a leading zero.", "At each position, add ways from a valid one-digit decode and a valid two-digit decode.", "Accepting `0` alone or accepting pairs outside 10 through 26 overcounts invalid decodings."),
    "house-robber-ii": ("Houses form a circle and `nums[i]` is the money in house `i`. Return the most money obtainable without robbing adjacent houses; the first and last houses are adjacent.", "The optimum excludes either the first house or the last, so solve two ordinary linear robber ranges.", "Running the linear recurrence once can illegally select both endpoints."),
    "longest-increasing-subsequence": ("Return the length of the longest strictly increasing subsequence of `nums`. The chosen values need not be contiguous but must retain their original order.", "Maintain the smallest possible tail for an increasing subsequence of each length and replace tails by binary search.", "Using an upper-bound search treats equal values as increasing and overstates the length."),
    "longest-palindromic-substring": ("Return a longest contiguous substring of `s` that reads the same forward and backward. If several answers have maximum length, return the earliest one.", "Expand around every odd and even center; update the best only when a strictly longer palindrome is found.", "Checking only character centers misses even-length palindromes such as `bb`."),
    "maximum-product-subarray": ("Return the largest product of a nonempty contiguous subarray of `nums`.", "Track both maximum and minimum products ending at each position because a negative value can swap their roles.", "Keeping only the maximum discards a large-magnitude negative product that a later negative value can flip."),
    "palindromic-substrings": ("Return the number of contiguous substrings of `s` that are palindromes. Count equal text at different positions separately.", "Expand around all `2n - 1` odd and even centers and count every successful expansion.", "Counting distinct palindrome values instead of occurrences undercounts repeated substrings."),
    "word-break": ("Return whether `s` can be segmented completely into one or more words from `words`. Dictionary words may be reused.", "Let `dp[i]` mean the prefix ending before `i` is segmentable, and extend only from reachable boundaries.", "A greedy choice of the longest or shortest matching word can block a valid later segmentation."),
    "longest-common-subsequence": ("Return the length of the longest sequence that is a subsequence of both strings `a` and `b`. Characters need not be contiguous but order must be preserved.", "Use a two-dimensional prefix/suffix DP: matching characters extend the diagonal; otherwise discard one side.", "A longest-common-substring algorithm incorrectly resets when matching characters are noncontiguous."),
    "unique-paths": ("A robot starts at the top-left of a `rows` by `cols` grid and may move only right or down. Return the number of paths to the bottom-right.", "Each cell's path count is the sum of the counts immediately above and to its left.", "Initializing the first row or column to zero eliminates every path along that boundary."),
    "alien-dictionary": ("Given words sorted according to an unknown lowercase alphabet, return one valid ordering of all letters. Return an empty string if the ordering is impossible. The output must be deterministic: choose the lexicographically smallest available letter.", "The first differing character in each adjacent word pair creates one directed edge; then perform a deterministic topological sort.", "Ignoring the invalid case where a longer word precedes its exact prefix accepts an impossible dictionary."),
    "clone-graph": ("The graph is represented by a 1-indexed adjacency list for a connected undirected graph. Return an independent deep copy as an adjacency list with the same neighbor order.", "Create each node exactly once and memoize old-to-new identity before recursively or iteratively cloning neighbors.", "Copying only adjacency values without identity memoization duplicates nodes on cycles."),
    "pacific-atlantic": ("In `heights`, water flows from a cell to an orthogonal neighbor of equal or lower height. Return all coordinates that can reach both the top/left ocean and the bottom/right ocean.", "Search backward from each ocean into equal-or-higher neighbors, then intersect the two reachable sets.", "Running a fresh downhill search from every cell repeats work and commonly mishandles equal-height plateaus."),
    "jump-game": ("`nums[i]` is the maximum forward jump length from index `i`. Return whether the last index is reachable from index 0.", "Scan while maintaining the farthest reachable index; fail as soon as the scan reaches a position beyond it.", "Assuming the maximum jump must be taken can skip a route that requires a shorter jump."),
    "maximum-subarray": ("Return the largest sum of a nonempty contiguous subarray of `nums`.", "At each value, choose between starting a new subarray and extending the best subarray ending immediately before it.", "Initializing the best sum to zero incorrectly returns zero for an all-negative array."),
    "median-data-stream": ("Implement `MedianFinder`: `add_num` inserts an integer and `find_median` returns the median of all inserted values. For an even count, return the average of the two middle values.", "Keep a max-heap for the lower half and a min-heap for the upper half, balanced within one element.", "Balancing heap sizes without enforcing ordering can leave the wrong values at the two roots."),
    "insert-interval": ("Insert `new` into start-sorted, pairwise non-overlapping `intervals`, merging every overlap, and return the resulting sorted non-overlapping intervals.", "Append intervals ending before the new interval, merge every overlap into the new interval, then append the remainder.", "Treating touching or overlapping boundaries inconsistently can leave mergeable intervals separate."),
    "meeting-rooms-ii": ("Given meeting intervals `[start, end]`, return the minimum number of rooms required so every meeting can occur. A room is reusable when one meeting ends exactly as another starts.", "Process starts and ends in time order, releasing every room whose meeting has ended before allocating the next.", "Treating an end time equal to a start time as overlap allocates an unnecessary room."),
    "meeting-rooms": ("Return whether one person can attend every meeting in `intervals`. Meetings ending exactly when another begins do not overlap.", "Sort by start time and compare each start with the preceding end.", "Checking intervals only in their input order misses overlaps between nonadjacent input entries."),
    "merge-intervals": ("Merge all overlapping intervals and return the disjoint intervals sorted by start. Intervals sharing an endpoint are considered overlapping.", "Sort by start, then either extend the last merged end or begin a new interval.", "Failing to sort first means an interval can overlap an earlier merged range without being adjacent in the input."),
    "non-overlapping-intervals": ("Return the minimum number of intervals to remove so the remaining intervals do not overlap. Touching endpoints do not overlap.", "Keep intervals in ascending end-time order; the earliest finishing compatible interval leaves the most room for the future.", "Keeping the interval that starts earliest can block several shorter intervals and cause excess removals."),
    "merge-k-sorted-lists": ("Given `lists`, where each inner list is sorted in nondecreasing order, merge all values into one sorted list. Empty input lists are allowed.", "Place the first value from each nonempty list in a min-heap and advance only the list whose value was removed.", "Concatenating and repeatedly selecting the global minimum without a heap loses the intended O(N log k) bound."),
    "rotate-image": ("Return the square `matrix` rotated 90 degrees clockwise. Perform the transformation in place and also return the matrix used by the exercise harness.", "Transpose across the main diagonal, then reverse every row.", "Reversing rows before transposing produces the opposite rotation."),
    "set-matrix-zeroes": ("If an element of `matrix` is zero, set its entire row and column to zero. Mutate and return the matrix while using O(1) auxiliary space beyond a few flags.", "Use the first row and column as marker storage, while preserving separate flags for their original zero state.", "Writing zeroes during the initial scan causes newly written zeroes to cascade into unrelated rows and columns."),
    "spiral-matrix": ("Return every element of the rectangular `matrix` in clockwise spiral order, beginning at the top-left.", "Shrink top, bottom, left, and right boundaries after traversing each side, checking for crossed bounds.", "Traversing the bottom or left side after the bounds cross duplicates the center row or column."),
    "tree-codec": ("Implement `TreeCodec.serialize` and `TreeCodec.deserialize` for level-order tree lists. Serialization uses comma-separated values and `#` null markers with unnecessary trailing nulls removed; an empty tree serializes to an empty string.", "Preserve null positions during breadth-first traversal so child relationships survive the round trip.", "Dropping internal null markers changes which parent owns later children."),
    "implement-trie": ("Implement a prefix tree with `insert(word)`, `search(word)`, and `starts_with(prefix)`. `search` succeeds only for complete inserted words; prefix lookup need not end at a word.", "Store one child map per character and an explicit terminal marker at word endings.", "Equating path existence with word existence makes `search('app')` true after inserting only `apple`."),
    "word-dictionary": ("Implement `WordDictionary.add_word` and `search`. Search patterns contain lowercase letters and `.`, where each dot matches exactly one arbitrary character.", "Traverse trie edges normally; at a dot, branch into every child and succeed if any remaining path matches.", "Treating `.` as zero or more characters violates its exactly-one-character contract."),
    "word-search-ii": ("Return every distinct word from `words` that can be formed in the board by orthogonal moves without reusing a cell within a word. Results may be returned in any order.", "Build a trie for all words and share one board DFS, pruning trie branches and removing words once found.", "Running independent searches without restoring cells can make one word search corrupt the next."),
}


def constraints(data: dict) -> list[str]:
    if data.get("kind") == "class":
        return ["At most 20,000 operations are issued.", "Inputs follow the method contracts shown in the examples."]
    topic = data["topic"]
    if topic in {"dp-1d", "greedy", "bit-manipulation"}:
        return ["1 <= input length <= 20,000 where a sequence is supplied.", "Inputs fit signed 32-bit values unless the statement specifies unsigned values."]
    if topic in {"graphs", "backtracking", "tries", "math-geometry", "dp-2d"}:
        return ["The total input size is at most 10,000 elements.", "The input structure is valid and rectangular where a matrix is supplied."]
    return ["0 <= input length <= 20,000.", "All intervals and collections satisfy the structural contract in the statement."]


for path in ROOT.rglob("*.yaml"):
    data = yaml.safe_load(path.read_text())
    spec = SPECS.get(data.get("slug"))
    if spec is None:
        continue
    statement, insight, trap = spec
    data["version"] = max(2, int(data.get("version", 1)))
    data["statement"] = statement
    data["constraints"] = constraints(data)
    data["key_insight"] = insight
    data["clarifications"] = [
        {
            "question": f"What exact contract should `{data['entrypoint']}` implement?",
            "answer": statement,
        },
        {
            "question": "Which boundary condition is easiest to overlook?",
            "answer": trap,
        },
    ]
    data["follow_ups"] = [
        (
            f"Justify the claimed {data['time_complexity']} time and "
            f"{data['space_complexity']} space bounds."
        ),
        f"Design a test that exposes this failure: {trap}",
    ]
    data["hints"] = [
        "State precisely what information must be preserved after processing part of the input.",
        insight,
        f"Boundary check: {trap}",
        "Trace the sample and the smallest valid input before coding.",
        "Before finishing, verify the claimed time and space complexity against the implementation.",
    ]
    capability = data["capabilities"][0]["slug"]
    data["common_mistakes"] = [
        {"id": "contract-boundary", "description": trap, "capability": capability},
        {
            "id": "sample-overfit",
            "description": "Handles the sample shape but does not implement the general contract.",
            "capability": capability,
        },
    ]
    for wrong in data.get("wrong_solutions", []):
        if wrong["mistake"] not in {item["id"] for item in data["common_mistakes"]}:
            data["common_mistakes"].append(
                {
                    "id": wrong["mistake"],
                    "description": trap,
                    "capability": capability,
                }
            )
    data["wrong_solutions"] = [
        {
            "mistake": "sample-overfit",
            "expect": "wrong_answer",
            "code": f"def {data['entrypoint']}(*args):\n    return {data['visible_tests'][0]['expected']!r}",
        }
    ] if data.get("kind", "function") == "function" else data["wrong_solutions"]
    if data["slug"] == "merge-k-sorted-lists":
        data["wrong_solutions"] = [
            {
                "mistake": "sample-overfit",
                "expect": "wrong_answer",
                "code": (
                    "def merge_k_lists(lists):\n"
                    "    return next((node for node in lists if node is not None), None)"
                ),
            }
        ]
    path.write_text(yaml.safe_dump(data, sort_keys=False, width=1000))

print(f"Enriched {len(SPECS)} Blind 75 problems")
