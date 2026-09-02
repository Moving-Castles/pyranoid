"""Static configuration transcribed from PARRY's RDATA initialisation file.

RDATA is LISP code that builds property lists at load time. Rather than execute
it, the derived data is transcribed here directly (flare topics and weights, the
pointer chain toward the Mafia delusion, delusion story sequences, sensitive
topics, and delusion vocabulary). Source: original/src/rdata.
"""

from __future__ import annotations

# --- flare topics: trigger words and weights -------------------------------
# Each flare "set" is a paranoid topic. WORDS trigger it; WT is its salience.
# FLARELIST weights, in order: (17 15 12 10 9 7 6 5 4 3 1)

FLARE_WORDS: dict[str, list[str]] = {
    "MAFIASET": ["MAFIA"],
    "RACKETSET": ["RACKETEERS", "CRIME"],
    "GANGSTERSET": ["GANGSTERS", "HOOD"],
    "PERSONSET": ["ALIOTO", "MAFIO"],
    "CHEATSET": ["CHEATING", "CHEAT"],
    "BOOKIESET": ["BOOKIES", "CROOK"],
    "GAMBLERSET": ["GAMBLING", "BET"],
    "MONEYSET": ["MONEY"],
    "HORSERACINGSET": ["HORSERACING", "RACES"],
    "POLICESET": ["POLICE", "FUZZ"],
    "ITALIANSET": ["ITALIANS", "ITALY"],
    "HORSESET": ["HORSES", "HORSE"],
}

FLARE_WEIGHTS: dict[str, int] = {
    "RACKETSET": 17,
    "GANGSTERSET": 15,
    "PERSONSET": 12,
    "CHEATSET": 10,
    "BOOKIESET": 9,
    "GAMBLERSET": 7,
    "MONEYSET": 6,
    "HORSERACINGSET": 5,
    "POLICESET": 4,
    "ITALIANSET": 3,
    "HORSESET": 1,
    "INIT": 0,  # the "no flare" sentinel
    "MAFIASET": 100,  # terminal delusion topic
}

# Each flare points to the next flare one step closer to the Mafia delusion.
FLARE_NEXT: dict[str, str] = {
    "HORSESET": "HORSERACINGSET",
    "ITALIANSET": "GANGSTERSET",
    "PERSONSET": "GANGSTERSET",
    "POLICESET": "GANGSTERSET",
    "HORSERACINGSET": "BOOKIESET",
    "MONEYSET": "GAMBLERSET",
    "GAMBLERSET": "HORSERACINGSET",
    "BOOKIESET": "RACKETSET",
    "CHEATSET": "RACKETSET",
    "GANGSTERSET": "BOOKIESET",
    "RACKETSET": "MAFIASET",
    "MAFIASET": "MAFIASET",
}

# Topic type governs how a flare is introduced.
FLARE_TYPE: dict[str, str] = {
    "MAFIASET": "INSTITUTION",
    "POLICESET": "INSTITUTION",
    "GANGSTERSET": "SPECIFIC",
    "BOOKIESET": "SPECIFIC",
    "GAMBLERSET": "SPECIFIC",
    "HORSERACINGSET": "SPECIFIC",
    "ITALIANSET": "SPECIFIC",
    "HORSESET": "SPECIFIC",
}

# --- sensitive (non-delusional) topics -------------------------------------
SENSITIVE_WORDS: dict[str, list[str]] = {
    "LOOKS": ["LOOKS"],
    "SEXLIFE": ["SEXLIFE", "SEX", "GIRLS"],
    "FAMILY": ["FAMILY", "DAD"],
    "EDUCATION": ["EDUCATION", "SCHOO"],
    "RELIGION": ["RELIGION", "GOD", "PRAY"],
}
SENSITIVE_WEIGHTS: dict[str, int] = {
    "LOOKS": 9, "SEXLIFE": 8, "FAMILY": 6, "EDUCATION": 4, "RELIGION": 2,
}

# --- ordinary topic sets ----------------------------------------------------
TOPIC_WORDS: dict[str, list[str]] = {
    "SWEARING": ["SHIT"],
    "FAMILY": ["FAMILY", "DAD"],
    "SEXLIFE": ["SEXLIFE", "SEX", "GIRLS"],
    "GIRL": ["GIRL"],
    "WORK": ["JOB"],
    "RESIDENCE": ["HOME"],
    "HOSPITAL": ["WARD"],
    "HOBBIES": ["HOBBY"],
    "EDUCATION": ["EDUCATION", "SCHOO"],
    "SERVICE": ["ARMY"],
}

# --- story sequences: for each set, the units to tell, in order -------------
# (from RDATA's STL; ^H#### rendered as H####). These drive the narrative when
# a flare/topic is elaborated.
STORY: dict[str, list[str]] = {
    "MAFIASET": ["H1010"],
    "RACKETSET": ["H0880"],
    "GANGSTERSET": ["H0860", "H0860"],
    "PERSONSET": ["H0870", "H0870"],
    "CHEATSET": ["H0900", "H0900"],
    "BOOKIESET": ["H0920", "H0930"],
    "GAMBLERSET": ["H0940", "H0940"],
    "MONEYSET": ["H0960", "H0960"],
    "HORSERACINGSET": ["H0970", "H0972"],
    "POLICESET": ["H0980", "H0980"],
    "ITALIANSET": ["H0990", "H0990"],
    "HORSESET": ["H1000", "H1000"],
    "DELNSET": [
        "H1010", "H1020", "H1050", "H1080", "H1100", "H1110",
        "H1010", "H1020", "H1050", "H1080", "H1100", "H1110",
    ],
    "FAMILY": ["H0730", "H0732"],
    "EDUCATION": ["H1540", "H1550"],
    "HOSPITAL": ["H0100", "H0210"],
    "HOBBIES": ["H0760", "H0770"],
    "GIRL": ["H0660", "H0690"],
    "SERVICE": ["H0500", "H0510"],
    "SEXLIFE": ["H1690"],
    "RESIDENCE": ["H2290", "H2330"],
    "WORK": ["H0460", "H0462", "H0490"],
    "SWEARING": ["H2410"],
}

# --- delusion vocabulary ----------------------------------------------------
# Strong delusion words push fear hard; ambiguous ones only at high mistrust.
DELUSION_NOUNS_STRONG = ["MAFIA", "GUN", "DEATH"]
DELUSION_VERBS_STRONG = ["KILL"]
DELUSION_NOUNS = DELUSION_NOUNS_STRONG + ["CHIEF"]
DELUSION_VERBS = DELUSION_VERBS_STRONG + ["SPY"]
DELUSION_AMBIG = ["BEAT", "HATE"]

# --- interrogatives ---------------------------------------------------------
QLIST = ["HOW", "WHO", "WHOM", "WHAT", "WHEN", "WHERE", "WHY", "WHICH"]

# --- version baselines (from INITPARAMS): STRONG starts all affect at 5 -----
VERSION_BASELINE = {"WEAK": 0.0, "MILD": 0.0, "STRONG": 5.0}


def word_to_flare() -> dict[str, str]:
    """Map each trigger word to its flare set (for the input scan)."""
    out: dict[str, str] = {}
    for setname, words in FLARE_WORDS.items():
        for w in words:
            out[w] = setname
    return out


def word_to_sensitive() -> dict[str, str]:
    out: dict[str, str] = {}
    for setname, words in SENSITIVE_WORDS.items():
        for w in words:
            out.setdefault(w, setname)
    return out


def word_to_topic() -> dict[str, str]:
    out: dict[str, str] = {}
    for setname, words in TOPIC_WORDS.items():
        for w in words:
            out.setdefault(w, setname)
    return out
