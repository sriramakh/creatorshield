"""Wording checks for YouTube Community Guidelines and Meta Community Standards.

These are risk flags, not determinations. They read the caption, hashtags,
transcript and on-screen text. They do not classify frames. Every flag cites
rule IDs that exist in the policy knowledge base for the target platform.
"""

from __future__ import annotations

import re
from collections.abc import Sequence
from dataclasses import dataclass, field
from typing import Literal, Protocol

from app.schemas import FindingDraft

SeverityName = Literal["info", "low", "medium", "high", "critical"]
ConfidenceName = Literal["low", "medium", "high"]

_RANK: dict[str, int] = {"info": 0, "low": 1, "medium": 2, "high": 3, "critical": 4}
_DOWN: dict[SeverityName, SeverityName] = {
    "critical": "high",
    "high": "medium",
    "medium": "low",
    "low": "low",
    "info": "info",
}

# Cosmetic "nude" (lipstick, nail shades) is not nudity. The lookahead is
# shared by the adult and child patterns.
_NOT_COSMETIC = (
    r"(?!\s+(?:lipstick|lipsticks|palette|nail|nails|shade|shades|"
    r"color|colour|colors|colours|makeup|make-up|tone|tones)\b)"
)

_RISK = (
    "Risk flag only: this is not a decision that the video breaks a rule, "
    "and it is not a prediction of a strike, removal, age restriction or loss of monetisation. "
)

_CONTEXT_NOTE = (
    "Words in the same line suggest news, education, documentary, satire, "
    "condemnation or a help resource. That context can change how a policy applies, "
    "and for the highest-risk areas it has to be in the video or audio, not only in "
    "a caption. This remains a risk flag for a person to review."
)

_EDSA = re.compile(
    r"\b(?:documentary|newscast|news(?:\s+report)?|satire|satirical|parody|"
    r"educational|education|condemn(?:s|ing|ed)?|awareness|public\s+service|"
    r"helpline|hotline|recovery|prevention)\b",
    re.IGNORECASE,
)


class TextSpan(Protocol):
    source: str
    ref_id: str
    text: str
    start: float | None
    end: float | None


@dataclass(frozen=True)
class Signal:
    pattern: str
    severity: SeverityName
    regex: re.Pattern[str] = field(init=False, compare=False, repr=False)

    def __post_init__(self) -> None:
        object.__setattr__(self, "regex", re.compile(self.pattern, re.IGNORECASE))


@dataclass(frozen=True)
class Pack:
    key: str
    title: str
    explanation: str
    suggested_action: str
    confidence: ConfidenceName
    youtube: tuple[str, ...]
    instagram: tuple[str, ...]
    signals: tuple[Signal, ...]
    downgrade: bool = True
    escalate_early: bool = False

    def rule_ids(self, platform: str) -> tuple[str, ...]:
        return self.youtube if platform == "youtube_shorts" else self.instagram


def _s(pattern: str, severity: SeverityName) -> Signal:
    return Signal(pattern, severity)


# Sale verbs stay narrow so "law and order" or "in order to" do not match.
_SALE = r"buy(?:ing)?|sell(?:ing)?|for\s+sale|dm\s+(?:me|to\s+(?:buy|order))"
_GUN = (
    r"(?:handguns?|firearms?|glocks?|ar-?15s?|pistols?|rifles?|"
    r"(?<!water )(?<!glue )(?<!nail )(?<!staple )guns?)"
)
_DRUG = r"cocaine|heroin|fentanyl|meth(?:amphetamine)?|mdma|ecstasy"
_TOBACCO = r"vapes?|vape\s+pens?|e-?cigs?|cigarettes?|cigars?"


PACKS: tuple[Pack, ...] = (
    Pack(
        key="child_sexual",
        title="Risk flag: possible sexual content involving a minor",
        explanation=(
            "Wording may sexualize a minor or describe sexual content involving a child. "
            "YouTube's child safety policy and Meta's child sexual exploitation policy "
            "treat this as among the most serious harms. A joke, a story, or an "
            "awareness framing does not make sexual content of a child allowed. "
            "If a child is in danger, contact local law enforcement."
        ),
        suggested_action=(
            "Remove the wording. Do not try to soften it. If this was a news report, "
            "keep sexual detail out of the video and follow the platform's reporting guidance."
        ),
        confidence="high",
        youtube=("YT-CG-CHILD",),
        instagram=("META-CS-CHILD",),
        downgrade=False,
        signals=(
            _s(r"\b(?:child\s*porn(?:ography)?|csam)\b", "critical"),
            _s(r"\bunderage\s+(?:nude|naked|porn|sex)\b", "critical"),
            _s(
                r"\b(?:children|child|minors|minor|underage|preteen|toddlers|toddler|kids|kid)\b"
                r".{0,30}\b(?:nude" + _NOT_COSMETIC + r"|naked|porn|only\s*fans)\b",
                "critical",
            ),
            _s(
                r"\b(?:nude" + _NOT_COSMETIC + r"|naked|porn|only\s*fans)\b.{0,30}"
                r"\b(?:children|child|minors|minor|underage|preteen|toddlers|toddler|kids|kid)\b",
                "critical",
            ),
            _s(r"नाबालिग.{0,40}(?:नंगा|न्यूड|सेक्स|पोर्न)", "critical"),
        ),
    ),
    Pack(
        key="hate",
        title="Risk flag: possible hate speech",
        explanation=(
            "Wording matches a slur or a call for violence against people as a group. "
            "YouTube's hate speech policy and Meta's hateful conduct policy prohibit "
            "attacks based on protected attributes such as race, religion, caste, "
            "nationality, sex, gender or sexual orientation. Condemning or reporting "
            "on hate can be allowed when that context is clear in the video."
        ),
        suggested_action=(
            "Cut the attack or slur. If you are quoting it to condemn or explain it, "
            "say that in the video itself, not only in the caption."
        ),
        confidence="medium",
        youtube=("YT-CG-HATE", "YT-CG-HARASS"),
        instagram=("META-CS-HATE", "META-CS-BULLYING"),
        signals=(
            _s(
                r"\b(?:n[i1]gg(?:er|a)s?|fagg?ots?|kikes?|ragheads?|towelheads?)\b",
                "high",
            ),
            _s(
                r"\b(?:kill|exterminate|gas)\s+all\s+(?:the\s+)?"
                r"(?:muslims|hindus|jews|christians|sikhs|blacks|whites|immigrants|"
                r"gays|trans(?:\s+people)?|women|men)\b",
                "high",
            ),
            _s(
                r"\b(?:they(?:'re|\s+are)|those\s+people\s+are)\s+"
                r"(?:animals|vermin|cockroaches|a\s+disease|subhuman)\b",
                "high",
            ),
        ),
    ),
    Pack(
        key="harassment",
        title="Risk flag: possible harassment, threat or doxxing",
        explanation=(
            "Wording looks like a threat, a sustained insult, or sharing of private "
            "contact details. YouTube's harassment policy and Meta's bullying policy "
            "prohibit threats and doxxing, with stricter rules where a minor is the target. "
            "Calling it a joke does not by itself clear a threat."
        ),
        suggested_action=(
            "Remove threats, sexual insults aimed at a person, and any phone number, "
            "email or home address. Do not tell viewers where someone lives."
        ),
        confidence="medium",
        youtube=("YT-CG-HARASS",),
        instagram=("META-CS-BULLYING",),
        signals=(
            _s(
                r"\b(?:i(?:'ll|\s+will)|i\s+am\s+going\s+to|i'm\s+going\s+to|gonna)\s+"
                r"(?:kill|murder|shoot|stab)\s+(?:you|u|him|her|them)\b",
                "high",
            ),
            _s(r"\bi\s+know\s+where\s+you\s+live\b", "high"),
            _s(r"\b(?:doxx?(?:ing)?|swat)\s+(?:you|him|her|them)\b", "high"),
            _s(r"\b(?:his|her|their)\s+(?:home\s+)?address\s+is\b", "high"),
            _s(r"\b(?:phone|mobile)\s+number\s+is\s+\+?\d", "medium"),
            _s(
                r"\byou\s+(?:stupid|ugly|fat)\s+(?:bitch|whore|slut)\b",
                "medium",
            ),
        ),
    ),
    Pack(
        key="violence",
        title="Risk flag: possible violent or graphic content",
        explanation=(
            "Wording describes a threat of violence or graphic injury. YouTube removes "
            "content that incites violence or shows gore to shock, and may age-restrict "
            "graphic footage that has enough context. Meta removes threats and the most "
            "graphic violence, and may limit other graphic footage to adults."
        ),
        suggested_action=(
            "Cut the threat or the graphic description. If this is news or education, "
            "say so in the video and blur imagery that is there to shock."
        ),
        confidence="medium",
        youtube=("YT-CG-VIOLENT",),
        instagram=("META-CS-VIOLENCE", "META-CS-GRAPHIC"),
        signals=(
            _s(r"\bbehead(?:ing|ed|s)?\b", "high"),
            _s(r"\bdismember(?:ment|ed|ing)?\b", "high"),
            _s(r"\b(?:gore\s+porn|graphic\s+(?:murder|torture|execution))\b", "high"),
            _s(r"\bschool\s+shoot(?:ing|er)\b", "medium"),
        ),
    ),
    Pack(
        key="sexual",
        title="Risk flag: possible nudity or sexual content",
        explanation=(
            "Wording describes explicit sexual content or nudity. YouTube does not allow "
            "explicit content meant to be sexually gratifying, and may age-restrict other "
            "nudity. Meta removes explicit sexual activity and certain nudity, and limits "
            "some near-nudity to adults. A makeup shade described as nude is not this flag."
        ),
        suggested_action=(
            "Cut explicit sexual content. If the moment is educational, medical or "
            "artistic, keep it non-gratuitous and expect an age restriction rather than "
            "assuming it will be left unrestricted."
        ),
        confidence="medium",
        youtube=("YT-CG-SEXUAL", "YT-MON-AD-FRIENDLY"),
        instagram=("META-CS-NUDITY", "IG-RECOMMENDATIONS"),
        signals=(
            _s(r"\bonly\s*fans\b", "medium"),
            _s(r"\bsex\s*tapes?\b", "high"),
            _s(r"\b(?:hardcore\s+)?porn(?:ography)?\b", "high"),
            _s(r"\b(?:blow\s*jobs?|dick\s*pics?)\b", "high"),
            _s(r"\bmasturbat(?:e|ing|ion)\b", "medium"),
            _s(r"\bnud(?:e|ity)\b" + _NOT_COSMETIC, "medium"),
            _s(r"\b(?:fully\s+)?naked\b", "medium"),
        ),
    ),
    Pack(
        key="dangerous",
        title="Risk flag: possible dangerous or harmful act",
        explanation=(
            "Wording describes a dangerous challenge or instructions for a violent device. "
            "YouTube does not allow content that encourages activities with a serious risk "
            'of harm, and says that "don\'t try this at home" is not sufficient context. '
            "Meta removes content that promotes or instructs suicide or self-injury, "
            "including challenges."
        ),
        suggested_action=(
            "Remove the challenge or the instructions. If you are warning people, explain "
            "the harm in the video and do not show how to copy the act."
        ),
        confidence="medium",
        youtube=("YT-CG-DANGEROUS",),
        instagram=("META-CS-SUICIDE",),
        signals=(
            _s(
                r"\b(?:blackout|choking|pass\s*out|tide\s*pod|skull\s*breaker)\s+challenge\b",
                "high",
            ),
            _s(
                r"\bhow\s+to\s+(?:make|build)\s+(?:a\s+)?(?:bomb|explosive|pipe\s+bomb|molotov)\b",
                "critical",
            ),
            _s(r"\b(?:drink|chug)\s+(?:bleach|detergent)\b", "high"),
        ),
    ),
    Pack(
        key="self_harm",
        title="Risk flag: possible suicide, self-harm or eating-disorder promotion",
        explanation=(
            "Wording may promote, instruct or glorify suicide, self-harm or an eating "
            "disorder. Both platforms allow people to talk about their own experience and "
            "recovery. They do not allow instructions, challenges, or content that encourages "
            "the behaviour. If you are in crisis, local help is listed at https://findahelpline.com."
        ),
        suggested_action=(
            "Remove instructions, methods and challenges. A personal recovery story can stay "
            "if it does not explain how to copy the harm, and if you point viewers to help "
            "in the video."
        ),
        confidence="medium",
        youtube=("YT-CG-SELFHARM",),
        instagram=("META-CS-SUICIDE",),
        signals=(
            _s(r"(?<!don't )(?<!do not )\bkill\s+yourself\b", "high"),
            _s(
                r"\bhow\s+to\s+(?:commit\s+suicide|cut\s+(?:yourself|myself)|hide\s+(?:my\s+)?cuts)\b",
                "critical",
            ),
            _s(r"\b(?:pro[\s-]?ana|thinspo|suicide\s+(?:challenge|pact))\b", "high"),
            _s(r"\b(?:blue\s+whale|momo)\s+challenge\b", "high"),
        ),
    ),
    Pack(
        key="minors_regulated",
        title="Risk flag: possible regulated goods involving a minor",
        explanation=(
            "Wording describes a minor drinking alcohol, vaping or smoking. YouTube's child "
            "safety policy lists those acts as harmful for minors. Meta restricts alcohol "
            "and tobacco, and limits much of that content to adults."
        ),
        suggested_action=(
            "Cut footage or lines that show or encourage a minor drinking, vaping or smoking. "
            "A news report should say that it is reporting, in the video."
        ),
        confidence="medium",
        youtube=("YT-CG-CHILD", "YT-CG-REGULATED"),
        instagram=("META-CS-RESTRICTED",),
        signals=(
            _s(r"\bunderage\s+drinking\b", "high"),
            _s(
                r"\b(?:minors?|kids?|children|child)\b.{0,40}"
                r"\b(?:drinking\s+alcohol|vaping|smoking\s+(?:weed|cigarettes?|tobacco))\b",
                "high",
            ),
        ),
    ),
    Pack(
        key="firearms",
        title="Risk flag: possible firearm sale or manufacture",
        explanation=(
            "Wording looks like an offer to sell a firearm, or instructions for making one "
            "or a listed accessory. YouTube does not allow that, and age-restricts some "
            "real firearm use. Meta does not allow private individuals to buy, sell, gift "
            "or trade firearms or ammunition. A water gun, glue gun or gun safe is not this flag."
        ),
        suggested_action=(
            "Remove prices, sale links, 'DM to buy' and any how-to for making or converting "
            "a firearm. News and policy discussion can stay; a sales pitch should not."
        ),
        confidence="medium",
        youtube=("YT-CG-FIREARMS", "YT-CG-REGULATED"),
        instagram=("META-CS-RESTRICTED",),
        signals=(
            _s(rf"\b(?:{_SALE})\b.{{0,40}}\b(?:{_GUN}|ammo|ammunition)\b", "high"),
            _s(rf"\b(?:{_GUN}|ammo|ammunition)\b.{{0,40}}\b(?:{_SALE})\b", "high"),
            _s(
                r"\bhow\s+to\s+(?:3d[\s-]?print|make|build|manufacture)\s+(?:a\s+)?"
                r"(?:gun|firearm|glock|silencer|suppressor)\b",
                "critical",
            ),
            _s(
                r"\b(?:ghost\s+guns?|bump\s+stocks?|auto\s+sears?|drop-in\s+auto\s+sears?)\b",
                "high",
            ),
        ),
    ),
    Pack(
        key="regulated",
        title="Risk flag: possible drug, tobacco, alcohol or gambling promotion",
        explanation=(
            "Wording looks like a sale, or a guaranteed gambling win, for drugs, tobacco, "
            "alcohol or gambling. YouTube does not allow content meant to sell or facilitate "
            "access to those goods, including uncertified online gambling. Meta restricts "
            "the same trade, and does not allow promotion of online gambling for money. "
            "Talking about the topic is a different, lower risk than selling it."
        ),
        suggested_action=(
            "Remove sale links, prices and 'DM to buy'. Do not promise a gambling win. "
            "If you are reporting on a scam or an addiction, make that the point of the line."
        ),
        confidence="medium",
        youtube=("YT-CG-REGULATED", "YT-MON-AD-FRIENDLY"),
        instagram=("META-CS-RESTRICTED", "IG-RECOMMENDATIONS"),
        signals=(
            _s(rf"\b(?:{_SALE})\b.{{0,40}}\b(?:{_DRUG}|{_TOBACCO})\b", "high"),
            _s(rf"\b(?:{_DRUG}|{_TOBACCO})\b.{{0,40}}\b(?:{_SALE})\b", "high"),
            _s(
                r"\b(?:for\s+sale|dm\s+(?:me|to\s+buy)|buy(?:ing)?)\b.{0,30}"
                r"\b(?:whisky|whiskey|vodka|beer|wine|alcohol)\b",
                "medium",
            ),
            _s(r"\b(?:fixed\s+match(?:es)?|guaranteed\s+(?:betting\s+)?wins?)\b", "high"),
            _s(r"\b(?:casino|sportsbook)\s+(?:bonus|signup|deposit)\b", "medium"),
        ),
    ),
    Pack(
        key="finance",
        title="Risk flag: possible get-rich-quick or guaranteed-returns claim",
        explanation=(
            "Wording promises a profit, a return or an income as certain or risk-free. "
            "YouTube's spam policy prohibits deceptive practices, and its advertiser-friendly "
            "guidelines treat dishonest behaviour as a monetisation problem. Meta's prohibited "
            "commercial practices include guaranteed or risk-free investment returns and "
            "money-flip offers. This flag does not decide whether a financial licence is required."
        ),
        suggested_action=(
            "Remove 'guaranteed', 'risk-free', 'double your money' and similar lines. "
            "Say what can be lost. Do not tell people a return is certain."
        ),
        confidence="medium",
        youtube=("YT-CG-SPAM", "YT-MON-AD-FRIENDLY"),
        instagram=("META-CS-COMMERCIAL", "META-CS-SPAM"),
        signals=(
            _s(r"\bguaranteed\s+(?:returns?|profits?|income|roi)\b", "high"),
            _s(
                r"\brisk[\s-]?free\s+(?:returns?|invest(?:ment|ing)?|profits?|income)\b",
                "high",
            ),
            _s(r"\b(?:double\s+your\s+money|get\s+rich\s+quick|money\s+flip)\b", "high"),
            _s(r"\b100\s*%\s+(?:profit|returns?|roi)\b", "high"),
            _s(r"\bcan(?:'t|not)\s+lose\b.{0,40}\b(?:trad(?:e|ing)|invest)", "high"),
            _s(r"गार(?:ं|न्)?[टत]ी(?:ड)?\s*रिटर्न", "high"),
            _s(r"पैसे\s*डबल", "high"),
            _s(r"रिस्क\s*फ्री", "high"),
        ),
    ),
    Pack(
        key="medical",
        title="Risk flag: possible medical misinformation",
        explanation=(
            "Wording contradicts common health-authority guidance on vaccines or presents "
            "a harmful substance as a remedy. YouTube's medical misinformation policy covers "
            "prevention and treatment claims of that kind. Meta removes misinformation that "
            "is likely to contribute to imminent harm, including harmful 'miracle' treatments. "
            "A personal story about symptoms is not this flag."
        ),
        suggested_action=(
            "Remove the line that contradicts health-authority guidance, such as a vaccine "
            "claim or a harmful substance presented as a treatment. Do not state a cure as a fact."
        ),
        confidence="medium",
        youtube=("YT-CG-MEDMISINFO", "YT-MON-AD-FRIENDLY"),
        instagram=("META-CS-MISINFO", "IG-MON-CONTENT"),
        signals=(
            _s(
                r"\bvaccines?\s+(?:cause|caused|are\s+causing)\s+(?:autism|infertility)\b",
                "high",
            ),
            _s(
                r"\b(?:don'?t|do\s+not|never)\s+(?:get|take)\s+(?:the\s+)?(?:covid(?:-19)?\s+)?vaccines?\b",
                "high",
            ),
            _s(
                r"\b(?:bleach|disinfectant)\s+(?:cures?|kills?|treats?)\b",
                "critical",
            ),
            _s(r"\bcovid(?:-19)?\s+is\s+a\s+hoax\b", "medium"),
            _s(r"(?:वैक्सीन|टीका).{0,40}ऑटि", "high"),
        ),
    ),
    Pack(
        key="elections",
        title="Risk flag: possible election misinformation",
        explanation=(
            "Wording may mislead people about how, when or who can vote, or may encourage "
            "interference with voting. YouTube's elections policy is limited to those harms. "
            "It does not ban every claim that an election was unfair. Meta removes "
            "misinformation that is likely to contribute to election interference. "
            "This check does not flag ordinary political opinion."
        ),
        suggested_action=(
            "Remove instructions that state the wrong way, date or eligibility to vote, "
            "and remove any line that tells people to block polling places or bring a weapon "
            "there. Opinions about politics can stay."
        ),
        confidence="medium",
        youtube=("YT-CG-ELECTIONS",),
        instagram=("META-CS-MISINFO",),
        signals=(
            _s(r"\b(?:vote\s+by\s+text(?:ing)?|text\s+(?:your\s+)?vote\s+to)\b", "high"),
            _s(
                r"\belection\s+is\s+only\s+(?:open\s+)?to\s+(?:voters?\s+)?(?:people\s+)?over\b",
                "high",
            ),
            _s(r"\b(?:wrong|fake|incorrect)\s+(?:election|voting)\s+(?:day|date)\b", "high"),
            _s(
                r"\bbring\s+(?:your\s+)?(?:guns?|weapons?)\s+to\s+(?:the\s+)?(?:polls?|polling)\b",
                "critical",
            ),
            _s(
                r"\b(?:block|obstruct)\s+(?:the\s+)?(?:polling(?:\s+places?|\s+stations?)?|voters|ballot)\b",
                "high",
            ),
        ),
    ),
    Pack(
        key="spam",
        title="Risk flag: possible engagement bait or spam",
        explanation=(
            "Wording asks for follows, subscriptions or comments in exchange for a reward "
            "or a follow back. YouTube's spam policy prohibits fake engagement and inorganic "
            "promotion. Meta's spam policy prohibits buying, selling or trading engagement "
            "and giveaways that require engagement."
        ),
        suggested_action=(
            "Remove 'sub for sub', 'follow for follow' and 'comment to win' lines. "
            "Ask people to follow only if you are not offering a reward for the follow."
        ),
        confidence="medium",
        youtube=("YT-CG-SPAM",),
        instagram=("META-CS-SPAM",),
        signals=(
            _s(r"\bsub\s*4\s*sub\b", "medium"),
            _s(r"\bsub(?:scribe)?\s+for\s+sub(?:scribe)?\b", "medium"),
            _s(r"\bfollow\s+for\s+follow\b", "medium"),
            _s(r"\b(?:like|comment)\s+(?:and\s+share\s+)?to\s+win\b", "medium"),
            _s(r"\bfree\s+followers?\b", "medium"),
        ),
    ),
    Pack(
        key="profanity",
        title="Risk flag: strong language that can limit ads",
        explanation=(
            "Strong language is a monetisation risk more than a removal risk. YouTube's "
            "advertiser-friendly guidelines say profanity at the start or throughout a video "
            "can mean limited or no ads, while occasional profanity may not. Instagram's "
            "content monetisation policies also list strong language as a reason to reduce "
            "monetisation. This flag is not a community-guidelines strike by itself."
        ),
        suggested_action=(
            "If you want the video to stay eligible for ads, cut strong language in the "
            "opening seconds and avoid repeating it. Occasional mild language is a smaller risk."
        ),
        confidence="low",
        youtube=("YT-MON-AD-FRIENDLY",),
        instagram=("IG-MON-CONTENT",),
        escalate_early=True,
        signals=(
            _s(
                r"\b(?:motherfuck(?:er|ing|ers)?|fuck(?:ing|ed|s)?|bullshit|shit|bitch(?:es)?|"
                r"assholes?|bastards?|madarchod|behenchod|bhosdike|chutiya)\b",
                "low",
            ),
        ),
    ),
    Pack(
        key="copyright",
        title="Risk flag: possible reused clip or copyright disclaimer",
        explanation=(
            "Wording such as 'no copyright infringement intended', 'full movie' or a credit "
            "to the owner is a sign the video may reuse someone else's clip or music. "
            "YouTube says crediting the owner, or adding a disclaimer, does not by itself "
            "make a use allowed, and reused content can affect monetisation. Instagram can "
            "remove unauthorised copies. This flag does not mean you lack a licence, and a "
            "missing flag does not mean the clip is free to use."
        ),
        suggested_action=(
            "Use footage and music you made or have a licence for, and keep the record. "
            "Remove disclaimer text. A commentary or review that adds your own analysis is "
            "a lower risk than reposting a full clip."
        ),
        confidence="low",
        youtube=("YT-COPY-BASICS", "YT-COPY-FAIR-USE", "YT-MON-YPP"),
        instagram=("IG-COPYRIGHT", "IG-MON-CONTENT"),
        signals=(
            _s(r"\bno\s+copyright(?:\s+infringement)?\s+intended\b", "low"),
            _s(r"\bfull\s+(?:movie|film|episode)\b", "low"),
            _s(r"\bleaked\s+(?:episode|footage|film|movie)\b", "medium"),
            _s(r"\bnot\s+my\s+(?:video|clip|content)\b", "low"),
            _s(r"\bre-?uploaded?\b", "low"),
            _s(
                r"\bcredits?\s+(?:goes\s+)?to\s+(?:the\s+)?(?:original\s+)?(?:owner|creator)\b",
                "low",
            ),
        ),
    ),
)

_BY_KEY = {pack.key: pack for pack in PACKS}


def is_finance_claim(text: str) -> bool:
    """True when the line is a guaranteed-returns or get-rich-quick claim."""
    return any(signal.regex.search(text) for signal in _BY_KEY["finance"].signals)


def _max_severity(levels: list[SeverityName]) -> SeverityName:
    return max(levels, key=lambda level: _RANK[level])


def _evidence(hits: list[tuple[TextSpan, str]], limit: int = 6) -> list[dict[str, object]]:
    return [
        {
            "source": item.source,
            "ref_id": item.ref_id,
            "detail": f'"{match}" in: {item.text[:160]}',
            "timestamp": item.start,
        }
        for item, match in hits[:limit]
    ]


def _span(hits: list[tuple[TextSpan, str]]) -> tuple[float | None, float | None]:
    times = [(item.start, item.end) for item, _ in hits if item.start is not None]
    if not times:
        return None, None
    return min(start for start, _ in times if start is not None), max(
        end for _, end in times if end is not None
    )


def run_community_guideline_checks(
    platform: str,
    items: Sequence[TextSpan],
) -> list[FindingDraft]:
    """One finding per pack that matches. Hashtags are included."""
    found: dict[str, list[tuple[TextSpan, str, SeverityName]]] = {}
    for pack in PACKS:
        hits: list[tuple[TextSpan, str, SeverityName]] = []
        for item in items:
            best: tuple[str, SeverityName] | None = None
            for signal in pack.signals:
                match = signal.regex.search(item.text)
                if match is None:
                    continue
                if best is None or _RANK[signal.severity] > _RANK[best[1]]:
                    best = (match.group(0), signal.severity)
            if best is not None:
                hits.append((item, best[0], best[1]))
        if hits:
            found[pack.key] = hits

    child_refs = {item.ref_id for item, _, _ in found.get("child_sexual", [])}
    if child_refs and "sexual" in found:
        found["sexual"] = [hit for hit in found["sexual"] if hit[0].ref_id not in child_refs]
        if not found["sexual"]:
            del found["sexual"]

    findings: list[FindingDraft] = []
    for pack in PACKS:
        matched = found.get(pack.key)
        if not matched:
            continue
        severity = _max_severity([level for _, _, level in matched])
        if pack.escalate_early:
            early = any(item.start is not None and item.start < 7 for item, _, _ in matched)
            if early or len(matched) >= 3:
                severity = severity if _RANK[severity] >= _RANK["medium"] else "medium"
        context: str | None = None
        confidence: ConfidenceName = pack.confidence
        if pack.downgrade and all(_EDSA.search(item.text) for item, _, _ in matched):
            severity = _DOWN[severity]
            confidence = "low"
            context = _CONTEXT_NOTE
        plain = [(item, match) for item, match, _ in matched]
        start, end = _span(plain)
        findings.append(
            FindingDraft(
                source="deterministic",
                category="community_guidelines",
                finding_type="suspected_violation",
                severity=severity,
                confidence=confidence,
                title=pack.title,
                explanation=_RISK + pack.explanation,
                suggested_action=pack.suggested_action,
                start_seconds=start,
                end_seconds=end,
                evidence=_evidence(plain),
                policy_rule_ids=list(pack.rule_ids(platform)),
                context_exception=context,
                requires_human_review=True,
            )
        )
    return findings
