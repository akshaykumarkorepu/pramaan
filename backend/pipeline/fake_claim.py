"""The deliberately false claim of verifier_test=1.

It looks like a real duty (so the demo is credible) but is built from a small list of templates, and each candidate is
run through the real verifier first: one whose quote is found in the document is skipped, so the injected claim is
guaranteed to be rejected because its quote is not in the text. Pure code, no LLM and no network."""
import secrets
from datetime import date, timedelta

from verify.verifier import InjectedObligation, verify

# (who, must_do, quote, days from today until the deadline). None of these is taken from a real notice.
TEMPLATES: dict[str, list[tuple[str, str, str, int]]] = {
    "rbi": [
        ("All regulated entities", "Report every de-listing request to RBI within 7 days",
         "Every regulated entity shall report each de-listing request to the Reserve Bank within seven days of receiving it.", 7),
        ("All banks and NBFCs", "Submit a revised cyber-incident return to RBI",
         "All banks and NBFCs shall submit a revised cyber-incident return to the Reserve Bank in the prescribed format.", 30),
        ("Regulated entities", "Appoint a nodal officer for customer grievance escalation",
         "Regulated entities shall appoint a nodal officer for escalation of customer grievances and intimate the Reserve Bank.", 45),
    ],
    "sebi": [
        ("All intermediaries", "Report every client-data breach to SEBI within 7 days",
         "Every intermediary shall report each client-data breach to the Board within seven days of its detection.", 7),
        ("Registered stock brokers", "File a revised compliance certificate with the stock exchange",
         "Registered stock brokers shall file a revised compliance certificate with the stock exchange in the specified format.", 30),
        ("Listed entities", "Disclose changes in key managerial personnel on the exchange website",
         "Listed entities shall disclose every change in key managerial personnel on the website of the stock exchange.", 45),
    ],
    "pib": [
        ("All eligible beneficiaries", "Update bank account details on the scheme portal",
         "All eligible beneficiaries shall update their bank account details on the scheme portal before the cut-off date.", 30),
        ("State governments", "Submit a utilisation report to the Ministry",
         "State governments shall submit a utilisation report for the scheme to the Ministry in the prescribed format.", 45),
        ("Implementing agencies", "Publish beneficiary lists on the scheme website",
         "Implementing agencies shall publish the beneficiary lists of the scheme on the official scheme website.", 60),
    ],
}


def make_fake_claim(source: str | None, doc, today: date | None = None) -> InjectedObligation:
    """A plausible fabricated duty for `source` (rbi|sebi|pib) whose quote is NOT in `doc`; its deadline is within 60 days."""
    today = today or date.today()
    candidates = TEMPLATES.get(source or "", TEMPLATES["rbi"])
    for who, must_do, quote, days in candidates:
        claim = _claim(who, must_do, quote, today + timedelta(days=days))
        # "rejected" alone is not enough: a quote that IS in the document is also rejected when the invented
        # deadline is not, so insist on the reason that says the quote itself was not found
        if verify([claim], doc)[0][0].reason == "quote not found in source":
            return claim
    # every template matched the document (practically impossible): a random token cannot be in any real text
    token = secrets.token_hex(4)
    return _claim("All regulated entities", f"Report every de-listing request ({token}) to the regulator within 7 days",
                  f"Every regulated entity shall report each de-listing request ({token}) to the regulator within seven days.",
                  today + timedelta(days=7))


def _claim(who: str, must_do: str, quote: str, deadline: date) -> InjectedObligation:
    return InjectedObligation(
        who=who, must_do=must_do, deadline=deadline.isoformat(), effective_from=None,
        paragraph=None, quote=quote, penalty_or_consequence=None,
    )
