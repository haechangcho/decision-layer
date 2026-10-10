"""Prepare a public Method proposal only from explicitly supplied public text."""
import re
from urllib.parse import urlencode

from ..methods import InvalidBinding


def method_proposal(run, request, repository):
    outcomes = run.conclusion.goal_outcomes if run.conclusion else []
    outcome = next((item for item in outcomes if item.goal_id == request.goal_id), None)
    if not outcome or outcome.status != "unsupported" or outcome.reason_code != "method_missing":
        raise InvalidBinding("Method proposals require a recorded missing-Method outcome.")
    if not re.fullmatch(r"[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+", repository):
        raise InvalidBinding("Configure a valid GitHub issue repository.")
    title = f"Method proposal: {request.title.strip()}"
    body = ("## Analysis question\n\n" + request.public_question.strip() + "\n\n"
            "## Expected result\n\n" + request.expected_result.strip() + "\n\n"
            "## Existing support\n\nThis request was recorded as requiring an unregistered analytical capability. "
            "Please verify whether an existing Method or Recipe can cover it.\n\n"
            "## Reproduction and validation\n\nAdd a public or synthetic example and expected checks here.\n")
    return {"title": title, "body": body, "submitted": False,
            "url": f"https://github.com/{repository}/issues/new?" + urlencode({"title": title, "body": body}),
            "existing_issues_url": f"https://github.com/{repository}/issues?" + urlencode({"q": request.title}),
            "guidance": "Review existing issues and the public draft before submitting on GitHub. No Run data, queries, identifiers or original question were copied. Review your supplied text for confidential information."}
