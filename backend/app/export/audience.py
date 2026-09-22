"""Who each export is for, and what that means for its contents.

`Documents.action_items` and `Documents.raid_log` carry **every** approved item,
internal ones included, because the PM needs them. Filtering therefore has to happen
in the export layer, per format. It previously did not: the PDF filtered its prose
(which comes pre-filtered from the generator) but appended the unfiltered action-item
table, so internal remarks reached a client-facing file.
"""

from typing import Literal

from app.models import ApprovedItem

CLIENT_SAFE = "client_safe"

Audience = Literal["client", "internal"]

# What each format is for. The PDF is the thing you send a client, so it is filtered.
# The other two are working documents and carry everything, clearly labelled.
FORMAT_AUDIENCE: dict[str, Audience] = {
    "pdf": "client",
    "docx": "internal",
    "xlsx": "internal",
}

INTERNAL_BANNER = (
    "INTERNAL — contains items not cleared for the client. Do not forward."
)


def client_items(items: list[ApprovedItem]) -> list[ApprovedItem]:
    return [item for item in items if item.audience == CLIENT_SAFE]


def for_audience(items: list[ApprovedItem], audience: Audience) -> list[ApprovedItem]:
    return client_items(items) if audience == "client" else items


def reconcile_provenance(item: ApprovedItem) -> ApprovedItem:
    """Make each value agree with its own provenance tag.

    The value and the tag come from different models: the owner and due date are
    extracted by the LLM, while `owner_status` / `due_status` are banded from Jev's
    judgment about whether the transcript *explicitly* states them. They disagree
    often — 12 rows in one sample — and the disagreement reached the spreadsheet as
    rows reading `Owner: Raj Menon / Owner source: not specified`.

    Two rules, applied to display only:

      * **No value means `not_specified`.** A "stated" tag with nothing beside it
        tells the reader nothing and looks like a defect.
      * **A value the model says was not explicitly stated is `inferred`.** That is
        precisely what the middle band means, and it keeps a real extracted name
        rather than discarding it.
    """
    owner_status = item.owner_status
    due_status = item.due_status

    if not item.owner:
        owner_status = "not_specified"
    elif owner_status == "not_specified":
        owner_status = "inferred"

    if not item.due_date:
        due_status = "not_specified"
    elif due_status == "not_specified":
        due_status = "inferred"

    if owner_status == item.owner_status and due_status == item.due_status:
        return item
    return item.model_copy(update={"owner_status": owner_status, "due_status": due_status})


def prepare(items: list[ApprovedItem], audience: Audience) -> list[ApprovedItem]:
    """Filter for the audience and make provenance self-consistent."""
    return [reconcile_provenance(item) for item in for_audience(items, audience)]
