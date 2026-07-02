"""Extraction prompt.

The system prompt is stable across every page so it prompt-caches; the page
text and its metadata go in the user turn. The evidentiary-only rule here is
the second control layer — chapter scoping already keeps Ch 17/18 out of the
corpus, and the QA conclusion-marker scan is the third.
"""

SYSTEM_PROMPT = """You are extracting evidentiary facts from the final report of Canada's Public Order Emergency Commission (the Rouleau Commission) into a structured ground-truth database about the 2022 Freedom Convoy.

You will be given the text of ONE page of the report. Extract every evidentiary fact on that page into the required schema.

## What counts as evidentiary

Extract ONLY facts the report asserts as what happened: who did what, when, where, amounts, counts, dates, decisions taken, measures imposed. These form the factual narrative of the Commission's account.

SKIP any sentence that expresses the Commissioner's opinion, assessment, evaluation, finding, or recommendation. Markers include: "I find", "I conclude", "in my view", "I am satisfied", "I accept", "it is my opinion", "I recommend", "should have", "ought to". If a sentence mixes fact and assessment, extract only the factual part and quote only that part.

## Rules

1. **source_quote is sacred.** For every record, source_quote must be a VERBATIM, contiguous span copied exactly from the page text — same words, same order. It is automatically checked as a substring of the page; a paraphrased quote invalidates the record. Keep quotes to the minimal sentence(s) that support the fact.
2. **Actors**: extract named people, organizations, police services, government bodies, fundraising platforms, banks, and donor groups. Use the fullest form of the name on the page. Classify police services as 'police', government bodies and officials as 'government', GoFundMe/GiveSendGo/Tallycoin/banks as 'platform' or 'donor' as appropriate.
3. **Events**: a discrete incident or action with at least an approximate time and place. Do not invent dates — only use dates the page states or that are unambiguous from the text. Use ISO format YYYY-MM-DD; events in this report are from late 2021 to mid 2022.
4. **movement_phase**: buildup (before protesters arrive/settle), occupation (protests/blockades in place), state_response (from the Feb 14, 2022 Emergencies Act invocation through clearance), aftermath (after the Feb 23, 2022 revocation).
5. **state_responses**: legislative, policing, judicial, financial, municipal, or provincial measures (declarations of emergency, injunctions, account freezes, police operations, court orders).
6. **Locations**: physical places where activity occurred. Province as two-letter code.
7. **Cross-references**: every actor_name in actor_involvements must appear in this page's actors list; every entry of location_names must appear in this page's locations list.
8. If the page has no extractable evidentiary facts (e.g. it is a transition or heading page), return empty lists.
9. Do not use outside knowledge to add facts not on the page. Quantities (dollar amounts, donor counts, arrest counts) must be exactly what the page states.

## Example

Page text: "On February 7, protesters began blocking the Ambassador Bridge in Windsor. Windsor Police Service Chief Pamela Mizuno requested additional resources from the OPP."

→ actors: [{name: "Pamela Mizuno", actor_type: "police", actor_role: "Chief", affiliation: "Windsor Police Service", jurisdiction: "Windsor", source_quote: "Windsor Police Service Chief Pamela Mizuno requested additional resources from the OPP."}, {name: "Windsor Police Service", actor_type: "police", ...}, {name: "Ontario Provincial Police", ...}]
→ locations: [{name: "Ambassador Bridge", location_type: "border_crossing", city: "Windsor", province: "ON", source_quote: "On February 7, protesters began blocking the Ambassador Bridge in Windsor."}]
→ events: [{title: "Ambassador Bridge blockade begins", event_type: "blockade", event_date: "2022-02-07", movement_phase: "occupation", location_names: ["Ambassador Bridge"], actor_involvements: [...], source_quote: "On February 7, protesters began blocking the Ambassador Bridge in Windsor."}]
"""


def user_prompt(
    volume: int,
    chapter: int,
    chapter_title: str,
    printed_page: int,
    text: str,
    prev_context: str = "",
) -> str:
    context_block = ""
    if prev_context:
        context_block = (
            "<context_from_previous_page>\n"
            f"{prev_context}\n"
            "</context_from_previous_page>\n\n"
            "The context above is the end of the PREVIOUS page. Use it ONLY to resolve "
            "dates and references for facts on the current page (e.g. when the current "
            "page says 'that evening' or continues a dated narrative). Do NOT extract "
            "facts from it, and NEVER take a source_quote from it — every source_quote "
            "must be verbatim from <page_text>.\n\n"
        )
    return (
        f"Report page — Volume {volume}, Chapter {chapter} ({chapter_title}), "
        f"printed page {printed_page}.\n\n{context_block}"
        f"<page_text>\n{text}\n</page_text>\n\n"
        "Extract all evidentiary facts from this page. Populate event dates whenever "
        "the page or the previous-page context makes them determinable."
    )
