"""Team — a group of people who act together and answer for something together."""

from typing import Any, ClassVar

from django.db import models

from tap_grid.models import BaseModel


class Team(BaseModel):
    """A group of people: a devops team, an engineering team, a company that contains them.

    Deliberately not an ``organization``. An organization is a party that holds identities (a
    company or agency); a team is the unit people join and leave, and it nests, through
    ``BELONGS_TO_TEAM__identity_core`` from one team to another. Role-free, like organization: what
    a team is responsible for is asserted elsewhere, by the ``team.responsible`` dimension, so a
    type that said "devops" or "engineering" would bake one view in.

    Identity is ``handle``: an identifier the operator assigns and keeps stable, such as ``devops``
    or ``git-serious``. A name changes; a handle does not. The type carries no free-form
    ``configuration`` blob: there is no source payload to preserve, and a team record is where
    unchosen detail would collect.

    Spec: specs/spec-identity-core-v0.md (req-identity-core-team).
    """

    ENTITY_TYPE: ClassVar[str] = "identity_core__team"
    ENTITY_NAME: ClassVar[str] = "Team"
    ENTITY_DESCRIPTION: ClassVar[str] = (
        "A group of people who act together and answer for something together. Humans belong to "
        "and lead teams, and a team can belong to another team."
    )
    ENTITY_ICON: ClassVar[str] = "team"
    # No default dimension: a kind-of-team value would bake one view in.
    DEFAULT_DIMENSIONS: ClassVar[dict[str, str]] = {}
    NATURAL_KEY: ClassVar[tuple[str, ...]] = ("handle",)
    DEFAULT_DISPLAY: ClassVar[dict[str, Any]] = {
        "tap_viz": {
            "shape": "ellipse",
            "colors": {"fill": "#FFF8E1", "border": "#F9A825", "label": "#5F4300"},
            "label": {"valign": "bottom", "halign": "center", "position": "outside"},
        }
    }

    FIELD_CRUD_SCHEMA: ClassVar[dict[str, Any]] = {
        "handle": {"type": "string", "minLength": 1},
        "name": {"type": "string"},
        "description": {"type": "string"},
    }
    FIELD_VALIDATION_SCHEMA: ClassVar[dict[str, Any]] = {
        "handle": {"validation": "jsonschema", "schema": {"type": "string", "minLength": 1}},
        "name": {"validation": "jsonschema", "schema": {"type": "string"}},
        "description": {"validation": "jsonschema", "schema": {"type": "string"}},
    }
    CREATE_REQUIRED: ClassVar[list[str]] = ["handle"]

    handle = models.CharField(max_length=255, blank=True, default="", db_index=True)
    name = models.CharField(max_length=255, blank=True, default="")
    description = models.TextField(blank=True, default="")

    class Meta(BaseModel.Meta):
        db_table = "identity_core__team"

    def get_name(self) -> str:
        return self.name or self.handle

    def __str__(self) -> str:
        return self.get_name()
