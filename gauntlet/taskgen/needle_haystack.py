"""Needle-in-haystack generator: fresh random haystack per run (contamination-resistant).

Haystacks are assembled from filler sentences drawn from a large combinatorial
space with a seeded RNG, so tasks differ every run and models cannot have
memorized them. Includes a NoLiMa-style mode where the needle shares NO lexical
overlap with the question.
"""

from __future__ import annotations

import random
import uuid

from gauntlet.task import Assert, Task

FILLER_SUBJECTS = [
    "the city council", "a retired cartographer", "two bakers", "the local chess club",
    "an elderly lighthouse keeper", "three college roommates", "the volunteer fire brigade",
    "a traveling violinist", "the night-shift nurses", "a stubborn escape-goat",
    "the museum curator", "a group of birdwatchers", "the harbor master", "two rival food trucks",
    "a self-taught botanist", "the village postman", "a semi-pro soccer team", "the aquarium staff",
]
FILLER_EVENTS = [
    "argued about parking permits", "painted the fence bright turquoise", "rediscovered an old recipe",
    "organized a charity bake sale", "rebuilt the footbridge after the storm", "won the regional tournament",
    "planted a community garden", "disagreed about the budget", "hosted a film night",
    "catalogued hundreds of specimens", "petitioned for a new crosswalk", "practiced every weekend",
    "complained about the noise ordinance", "repaired the clock tower", "adopted a stray cat",
    "lobbied for longer library hours", "repainted the water tower", "recorded every sunset for a year",
]

# NoLiMa-style: needle entity/relation with zero lexical overlap with the question
NOLIMA_PAIRS = [
    # (needle sentence, question asking about it without shared content words)
    (
        "The velvet compass belongs to Marisol Vane.",
        "Who owns the item used for wayfinding that has a soft fabric covering?",
    ),
    (
        "Renwick's flagship store opened during a leap year.",
        "In what type of year did the company's main shop first open its doors?",
    ),
    (
        "The violinist hides spare rosin inside a hollowed cookbook.",
        "Where does the string musician keep extra bow resin?",
    ),
    (
        "Professor Okonkwo commutes by unicycle when it rains.",
        "How does the educator travel to work in wet weather?",
    ),
    (
        "The bakery's secret ingredient is smoked sea salt.",
        "What special component gives the bread shop's goods their flavor?",
    ),
    (
        "Captain Reyes keeps the ship's log in violet ink.",
        "What color ink does the vessel's commander use for records?",
    ),
    (
        "The lighthouse generator runs on recycled cooking oil.",
        "What fuel powers the beacon's machinery?",
    ),
    (
        "Agnieszka paints only during thunderstorms.",
        "Under what weather conditions does the artist work?",
    ),
]


def _filler_paragraph(rng: random.Random, n: int) -> str:
    sentences = []
    for _ in range(n):
        s = rng.choice(FILLER_SUBJECTS) + " " + rng.choice(FILLER_EVENTS) + "."
        sentences.append(s[0].upper() + s[1:])
    return " ".join(sentences)


def make_needle_task(
    task_id: str,
    context_tokens_target: int,
    seed: int,
    nolima: bool = False,
) -> Task:
    """Build a needle-in-haystack task with ~context_tokens_target tokens of filler."""
    rng = random.Random(seed)
    canary = f"gauntlet-canary-{uuid.UUID(int=rng.getrandbits(128))}"

    if nolima:
        needle, question = rng.choice(NOLIMA_PAIRS)
    else:
        code = f"ZEBRA-{rng.randint(10000, 99999)}"
        needle = f"The secret access code for the vault is {code}."
        question = "What is the secret access code for the vault?"

    # ~1.3 tokens per word average -> words needed
    words_needed = int(context_tokens_target / 1.3)
    paragraphs = []
    words = 0
    while words < words_needed:
        p = _filler_paragraph(rng, rng.randint(3, 6))
        paragraphs.append(p)
        words += len(p.split())

    # plant needle at a random depth (beginning/middle/end all occur)
    pos = rng.randint(0, len(paragraphs))
    paragraphs.insert(pos, needle)

    context = "\n\n".join(paragraphs)
    prompt = f"{context}\n\nQuestion: {question}\nAnswer with only the answer itself."

    asserts = (
        [Assert(type="contains_any", values=[n for n, q in NOLIMA_PAIRS if n == needle][0].split()[4].rstrip("."))]
        if nolima
        else None
    )
    if not nolima:
        code = needle.split()[-1].rstrip(".")
        asserts = [Assert(type="contains_all", values=[code])]

    return Task(
        id=task_id,
        suite="retrieval",
        description=f"needle@{context_tokens_target}t nolima={nolima}",
        prompt=prompt,
        system="Answer from the provided context only. If the answer is not present, say NOT_FOUND.",
        asserts=asserts,
        max_tokens=128,
        timeout=600.0,  # long prompts take longer to prefill on small GPUs
        contamination_risk="generated",
        canary=canary,
    )


def make_refusal_task(task_id: str, seed: int) -> Task:
    """Context does NOT contain the answer; correct behavior is NOT_FOUND."""
    rng = random.Random(seed)
    paragraphs = [_filler_paragraph(rng, 5) for _ in range(8)]
    context = "\n\n".join(paragraphs)
    return Task(
        id=task_id,
        suite="retrieval",
        description="anti-hallucination refusal",
        prompt=f"{context}\n\nQuestion: What is the secret access code for the vault?\n"
        "Answer with only the answer itself, or NOT_FOUND if it is not in the text.",
        system="Answer from the provided context only. If the answer is not present, say NOT_FOUND.",
        asserts=[Assert(type="contains_all", values=["NOT_FOUND"])],
        max_tokens=64,
        contamination_risk="generated",
        canary=f"gauntlet-canary-{uuid.UUID(int=rng.getrandbits(128))}",
    )
