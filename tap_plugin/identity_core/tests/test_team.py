"""Behaviour tests for identity_core__team and its edges (req-identity-core-team, -team-edges, -responsible)."""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from tap_plugin.identity_core.models import Team

from tap_grid.caller_context import CallerContext
from tap_grid.models import Edge, Entity
from tap_grid.services import WriteOperation, write_batch

TYPE = "identity_core__team"
HUMAN = "identity_core__human"
BELONGS = "BELONGS_TO_TEAM__identity_core"
LEADS = "LEADS_TEAM__identity_core"
PLUGIN = Path(__file__).resolve().parent.parent
SPEC = PLUGIN.parents[1] / "specs" / "spec-identity-core-v0.md"


def _write(op: WriteOperation) -> object:
    return write_batch([op], caller_context=CallerContext()).results[0]


def _node(type_slug: str, payload: dict) -> object:
    return _write(WriteOperation(verb="create_node", type_slug=type_slug, payload=payload))


def _team(handle: str, **extra: str) -> object:
    return _node(TYPE, {"handle": handle, **extra})


def _human(handle: str) -> object:
    return _node(HUMAN, {"handle": handle})


def _edge(edge_type: str, src: object, dst: object) -> object:
    return _write(
        WriteOperation(verb="create_edge", from_target=src.entity_id, to_target=dst.entity_id, edge_type=edge_type)
    )


def _edge_json(name: str) -> dict:
    return json.loads((PLUGIN / "edges" / f"{name}.edge.json").read_text())


@pytest.mark.django_db
class TestTeam:
    @pytest.mark.spec("req-identity-core-team-1")
    def test_create_with_handle_only(self) -> None:
        result = _team("devops")
        assert result.success
        team = Team.all_objects.get(entity_id=result.entity_id)
        assert (team.handle, team.name, team.description) == ("devops", "", "")
        assert Entity.objects.get(pk=result.entity_id).name == "devops"

    @pytest.mark.spec("req-identity-core-team-1")
    def test_display_name_prefers_name(self) -> None:
        named = _team("devops", name="DevOps", description="Runs the platform")
        assert Entity.objects.get(pk=named.entity_id).name == "DevOps"
        assert Team.all_objects.get(entity_id=named.entity_id).description == "Runs the platform"

    @pytest.mark.spec("req-identity-core-team-2")
    def test_handle_required(self) -> None:
        assert not _node(TYPE, {"name": "DevOps"}).success

    @pytest.mark.spec("req-identity-core-team-3")
    def test_no_configuration_blob(self) -> None:
        assert not _node(TYPE, {"handle": "devops", "configuration": {"x": 1}}).success

    @pytest.mark.spec("req-identity-core-team-4")
    def test_role_free(self) -> None:
        assert Team.DEFAULT_DIMENSIONS == {}
        assert Team.NATURAL_KEY == ("handle",)
        assert {f.name for f in Team._meta.get_fields()}.isdisjoint({"kind", "role", "responsibility", "configuration"})
        assert Team.ENTITY_ICON == "team"
        assert (PLUGIN / "static" / "identity_core" / "icons" / "team.svg").is_file()

    @pytest.mark.spec("req-identity-core-team-5")
    def test_registered_in_manifest(self) -> None:
        text = (PLUGIN / "tap-plugin.toml").read_text()
        assert 'identity_core__team = "tap_plugin.identity_core.models.team.Team"' in text
        assert _team("registered").success


@pytest.mark.django_db
class TestTeamEdges:
    @pytest.mark.spec("req-identity-core-team-edges-1")
    def test_membership_and_nesting(self) -> None:
        person, eng, company = _human("e1"), _team("eng"), _team("company")
        assert _edge(BELONGS, person, eng).success
        assert _edge(BELONGS, eng, company).success

    @pytest.mark.spec("req-identity-core-team-edges-2")
    def test_nothing_else(self) -> None:
        """The edge types declare a team-only target and a human-only (LEADS) source.

        The grid's permission union lets any node type with no OUTBOUND_EDGES/INBOUND_EDGES of its own
        through (tap_grid.constraints), and human and organization have none, so a write to a non-team
        target is not refused at write time; the declaration is what this asserts.
        """
        from tap_grid.constraints import get_edge_type_constraints

        belongs, leads = get_edge_type_constraints(BELONGS), get_edge_type_constraints(LEADS)
        assert belongs.targets == {TYPE} and leads.targets == {TYPE}
        assert belongs.sources == {HUMAN, TYPE}
        assert leads.sources == {HUMAN}

    @pytest.mark.spec("req-identity-core-team-edges-3")
    def test_several_of_each_are_recorded(self) -> None:
        person, a, b, child = _human("e1"), _team("a"), _team("b"), _team("child")
        lead1, lead2 = _human("l1"), _human("l2")
        for src, dst in ((person, a), (person, b), (child, a), (child, b)):
            assert _edge(BELONGS, src, dst).success
        assert _edge(LEADS, lead1, a).success and _edge(LEADS, lead2, a).success
        assert Edge.objects.filter(from_entity_id=person.entity_id, edge_type=BELONGS).count() == 2
        assert Edge.objects.filter(from_entity_id=child.entity_id, edge_type=BELONGS).count() == 2
        assert Edge.objects.filter(to_entity_id=a.entity_id, edge_type=LEADS).count() == 2

    @pytest.mark.spec("req-identity-core-team-edges-4")
    def test_leader_need_not_be_a_member(self) -> None:
        leader, team = _human("boss"), _team("t")
        assert _edge(LEADS, leader, team).success
        assert not Edge.objects.filter(from_entity_id=leader.entity_id, edge_type=BELONGS).exists()

    @pytest.mark.spec("req-identity-core-team-edges-5")
    def test_names_conform(self) -> None:
        text = (PLUGIN / "tap-plugin.toml").read_text()
        for slug, name in ((BELONGS, "BELONGS_TO_TEAM"), (LEADS, "LEADS_TEAM")):
            doc = _edge_json(name)
            assert doc["slug"] == slug
            assert f'{slug} = "edges/{name}.edge.json"' in text
            assert doc["targets"] == [TYPE]
            assert "Cardinality is not constrained" in doc["description"]
            assert "cycle" in doc["description"]
        assert set(_edge_json("BELONGS_TO_TEAM")["sources"]) == {HUMAN, TYPE}
        assert _edge_json("LEADS_TEAM")["sources"] == [HUMAN]
        assert _edge_json("BELONGS_TO_TEAM")["property_schema"]["properties"] == {}


class TestResponsibilityStamp:
    """The stamp is documentation only: nothing in the plugin sets or seeds it."""

    @pytest.mark.spec("req-identity-core-responsible-1")
    def test_value_is_a_team_id_in_the_spec(self) -> None:
        text = SPEC.read_text() if SPEC.is_file() else ""
        if not text:
            pytest.skip("spec not shipped in the installed package")
        assert "entity id of an `identity_core__team`" in text

    @pytest.mark.spec("req-identity-core-responsible-2", "req-identity-core-responsible-3")
    def test_plugin_sets_no_responsible_dimension(self) -> None:
        for name in ("BELONGS_TO_TEAM", "LEADS_TEAM"):
            assert "default_dimensions" not in _edge_json(name)
        assert Team.DEFAULT_DIMENSIONS == {}
