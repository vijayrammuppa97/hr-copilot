"""
Follow-up question generator.

Given the retrieved KB sections, returns 2-3 natural follow-up questions
the user is likely to ask next. No LLM call — purely rule-based mapping
from section title patterns to related questions. Fast and deterministic.
"""

import re
from typing import NamedTuple

_SECTION_QUESTIONS: list[tuple[re.Pattern, list[str]]] = [
    # Annual leave
    (re.compile(r"1\.[12]\b|annual leave overview|annual leave days", re.I), [
        "How do I apply for annual leave?",
        "Can I carry forward unused leave to next year?",
        "What happens to my leave if I resign?",
    ]),
    (re.compile(r"1\.3\b|annual leave request|apply for", re.I), [
        "How much notice do I need to give for annual leave?",
        "Can my manager reject my leave request?",
        "Can I take leave during my notice period?",
    ]),
    (re.compile(r"1\.4\b|carry.forward|roll.?over|unused", re.I), [
        "How many days can I carry forward to next year?",
        "What is the deadline to use carry-forward leave?",
        "Do I need manager approval to carry forward leave?",
    ]),
    (re.compile(r"1\.5\b|notice period|resign", re.I), [
        "Can I take annual leave during my notice period?",
        "Will unused leave be paid out when I leave?",
        "How is my final leave balance calculated?",
    ]),
    # Sick leave
    (re.compile(r"1\.6\b|sick leave policy", re.I), [
        "Do I need a doctor's note for sick leave?",
        "Can I use sick leave to care for a family member?",
        "How many sick days do I get per year?",
    ]),
    (re.compile(r"1\.7\b|sick leave documentation|doctor.?s note|certificate", re.I), [
        "When do I need a medical certificate?",
        "How many consecutive sick days before I need documentation?",
        "What counts as valid medical documentation?",
    ]),
    (re.compile(r"1\.8\b|mental health", re.I), [
        "How many mental health days can I take per year?",
        "Do mental health days count towards my sick leave balance?",
        "Do I need to give a reason when taking a mental health day?",
    ]),
    # Parental leave
    (re.compile(r"1\.9\b|maternity", re.I), [
        "When can maternity leave start?",
        "Is maternity leave fully paid?",
        "How much notice do I need to give before taking maternity leave?",
    ]),
    (re.compile(r"1\.10\b|paternity", re.I), [
        "How long is paternity leave and is it paid?",
        "When must paternity leave be taken by?",
        "Can I take additional unpaid paternity leave?",
    ]),
    (re.compile(r"1\.11\b|shared parental", re.I), [
        "Can both parents take shared parental leave at the same time?",
        "How much shared parental leave is paid?",
        "How do I apply for shared parental leave?",
    ]),
    (re.compile(r"1\.12\b|adoption", re.I), [
        "When does adoption leave start?",
        "Is adoption leave the same as maternity leave?",
        "Can both adoptive parents take leave?",
    ]),
    # Special leave
    (re.compile(r"bereavement|special leave|1\.13\b", re.I), [
        "How many days bereavement leave do I get?",
        "Does bereavement leave apply to extended family?",
        "Can I take additional unpaid leave for bereavement?",
    ]),
    (re.compile(r"jury|civic|court|1\.14\b", re.I), [
        "Will I be paid during jury service?",
        "How long can jury duty absence last?",
        "Do I need to notify my manager about jury duty?",
    ]),
    # Remote work
    (re.compile(r"2\.[12]\b|remote work|who is eligible|wfh eligibility", re.I), [
        "How many days per week can I work from home?",
        "What equipment does the company provide for remote work?",
        "What are the internet requirements for working from home?",
    ]),
    (re.compile(r"2\.3\b|remote work days|days.allowed|wfh days", re.I), [
        "Who decides my remote work schedule?",
        "Can I work remotely more than the standard allowance?",
        "What is the process to apply for a formal remote work arrangement?",
    ]),
    (re.compile(r"2\.6|equipment|laptop|device", re.I), [
        "What equipment does the company provide for remote work?",
        "What do I do if my company laptop is stolen?",
        "Am I responsible for damage to company equipment?",
    ]),
    (re.compile(r"2\.6\.1|stolen|lost.equipment|reporting procedure", re.I), [
        "How quickly must I report stolen equipment?",
        "Who do I contact if my laptop is lost or stolen?",
        "What happens if I don't report stolen equipment in time?",
    ]),
    # Grievance / HR process
    (re.compile(r"5\.4\b|grievance|formal complaint", re.I), [
        "How long does HR have to acknowledge my grievance?",
        "What happens after I raise a formal grievance?",
        "Can I bring a colleague to a grievance meeting?",
    ]),
    (re.compile(r"5\.5\b|harassment|discrimination|reporting", re.I), [
        "How do I report harassment anonymously?",
        "What is the anti-harassment policy?",
        "What protections do I have after reporting misconduct?",
    ]),
    (re.compile(r"5\.8\b|disciplinary", re.I), [
        "What are the stages of the disciplinary process?",
        "Can I appeal a disciplinary decision?",
        "What counts as gross misconduct?",
    ]),
    # Benefits
    (re.compile(r"4\.1\b|health insurance", re.I), [
        "What does the health insurance cover?",
        "When does health insurance start?",
        "Can I add dependants to my health insurance?",
    ]),
    (re.compile(r"4\.3\b|401k|retirement|pension", re.I), [
        "How much does the company match on the 401k?",
        "When am I eligible for the retirement plan?",
        "How do I enrol in the 401k?",
    ]),
    (re.compile(r"4\.7\b|professional development|training budget|learning", re.I), [
        "How much is the professional development budget?",
        "What types of training are covered?",
        "How do I claim my professional development allowance?",
    ]),
]


def generate_follow_up_questions(kb_results: list[dict], max_questions: int = 3) -> list[str]:
    """
    Return up to max_questions follow-up questions based on retrieved section titles.
    Deduplicates across sections. Returns questions from the highest-ranked sections first.
    """
    seen: set[str] = set()
    questions: list[str] = []

    for result in kb_results:
        section = result.get("section", "")
        for pattern, qs in _SECTION_QUESTIONS:
            if pattern.search(section):
                for q in qs:
                    if q not in seen:
                        seen.add(q)
                        questions.append(q)
                        if len(questions) >= max_questions:
                            return questions
                break  # only first matching pattern per section

    return questions[:max_questions]
