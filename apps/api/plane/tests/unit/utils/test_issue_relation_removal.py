# Copyright (c) 2023-present Plane Software, Inc. and contributors
# SPDX-License-Identifier: AGPL-3.0-only
# See the LICENSE file for details.

from unittest.mock import patch

import pytest

from plane.db.models import Issue, IssueRelation, Project, State
from plane.utils.issue_relation_removal import remove_issue_relation

pytestmark = pytest.mark.django_db


def _project(workspace, user):
    return Project.objects.create(
        name="Project TST",
        identifier="TST",
        workspace=workspace,
        created_by=user,
    )


def _state(project, workspace):
    return State.objects.create(
        name="Backlog",
        project=project,
        workspace=workspace,
        group="backlog",
        default=True,
    )


def _issue(project, workspace, user, state, name):
    return Issue.objects.create(
        name=name,
        sequence_id=1,
        priority="none",
        description_html="<p></p>",
        is_draft=False,
        workspace=workspace,
        project=project,
        state=state,
        created_by=user,
    )


def _relation(issue, related_issue, relation_type, project, user):
    return IssueRelation.objects.create(
        issue=issue,
        related_issue=related_issue,
        relation_type=relation_type,
        project=project,
        workspace=project.workspace,
        created_by=user,
    )


@pytest.mark.unit
class TestRemoveIssueRelation:
    def test_blocked_by_deletes_forward_row(self, workspace, create_user):
        user = create_user
        project = _project(workspace, user)
        state = _state(project, workspace)
        issue_a = _issue(project, workspace, user, state, "A")
        issue_b = _issue(project, workspace, user, state, "B")
        _relation(issue_a, issue_b, "blocked_by", project, user)

        result = remove_issue_relation(
            workspace_slug=workspace.slug,
            issue_id=issue_a.id,
            related_issue_id=issue_b.id,
            relation_type="blocked_by",
            actor_id=user.id,
            project_id=project.id,
            requested_data="{}",
            origin="https://testserver",
        )

        assert result is True
        assert not IssueRelation.objects.filter(issue=issue_a, related_issue=issue_b).exists()

    def test_blocking_deletes_inverse_blocked_by_row(self, workspace, create_user):
        user = create_user
        project = _project(workspace, user)
        state = _state(project, workspace)
        issue_a = _issue(project, workspace, user, state, "A")
        issue_b = _issue(project, workspace, user, state, "B")
        _relation(issue_b, issue_a, "blocked_by", project, user)

        result = remove_issue_relation(
            workspace_slug=workspace.slug,
            issue_id=issue_a.id,
            related_issue_id=issue_b.id,
            relation_type="blocking",
            actor_id=user.id,
            project_id=project.id,
            requested_data="{}",
            origin="https://testserver",
        )

        assert result is True
        assert not IssueRelation.objects.filter(issue=issue_b, related_issue=issue_a).exists()

    @pytest.mark.parametrize(
        "relation_type,stored_type",
        [("start_after", "start_before"), ("finish_after", "finish_before")],
    )
    def test_temporal_reverse_types_delete_stored_row(self, workspace, create_user, relation_type, stored_type):
        user = create_user
        project = _project(workspace, user)
        state = _state(project, workspace)
        issue_a = _issue(project, workspace, user, state, "A")
        issue_b = _issue(project, workspace, user, state, "B")
        _relation(issue_b, issue_a, stored_type, project, user)

        result = remove_issue_relation(
            workspace_slug=workspace.slug,
            issue_id=issue_a.id,
            related_issue_id=issue_b.id,
            relation_type=relation_type,
            actor_id=user.id,
            project_id=project.id,
            requested_data="{}",
            origin="https://testserver",
        )

        assert result is True
        assert IssueRelation.objects.count() == 0

    @pytest.mark.parametrize("relation_type", ["relates_to", "duplicate"])
    def test_symmetric_types_delete_direct_row(self, workspace, create_user, relation_type):
        user = create_user
        project = _project(workspace, user)
        state = _state(project, workspace)
        issue_a = _issue(project, workspace, user, state, "A")
        issue_b = _issue(project, workspace, user, state, "B")
        _relation(issue_a, issue_b, relation_type, project, user)

        result = remove_issue_relation(
            workspace_slug=workspace.slug,
            issue_id=issue_a.id,
            related_issue_id=issue_b.id,
            relation_type=relation_type,
            actor_id=user.id,
            project_id=project.id,
            requested_data="{}",
            origin="https://testserver",
        )

        assert result is True
        assert IssueRelation.objects.count() == 0

    def test_implemented_by_deletes_forward_row(self, workspace, create_user):
        user = create_user
        project = _project(workspace, user)
        state = _state(project, workspace)
        issue_a = _issue(project, workspace, user, state, "A")
        issue_b = _issue(project, workspace, user, state, "B")
        _relation(issue_a, issue_b, "implemented_by", project, user)

        result = remove_issue_relation(
            workspace_slug=workspace.slug,
            issue_id=issue_a.id,
            related_issue_id=issue_b.id,
            relation_type="implemented_by",
            actor_id=user.id,
            project_id=project.id,
            requested_data="{}",
            origin="https://testserver",
        )

        assert result is True
        assert IssueRelation.objects.count() == 0

    def test_implements_deletes_stored_implemented_by_row(self, workspace, create_user):
        user = create_user
        project = _project(workspace, user)
        state = _state(project, workspace)
        issue_a = _issue(project, workspace, user, state, "A")
        issue_b = _issue(project, workspace, user, state, "B")
        _relation(issue_a, issue_b, "implemented_by", project, user)

        result = remove_issue_relation(
            workspace_slug=workspace.slug,
            issue_id=issue_a.id,
            related_issue_id=issue_b.id,
            relation_type="implements",
            actor_id=user.id,
            project_id=project.id,
            requested_data="{}",
            origin="https://testserver",
        )

        assert result is True
        assert IssueRelation.objects.count() == 0

    @pytest.mark.parametrize("relation_type", ["blocked_by", "blocking", "duplicate", "start_before", "implements"])
    def test_mismatched_type_does_not_delete_different_relation(self, workspace, create_user, relation_type):
        user = create_user
        project = _project(workspace, user)
        state = _state(project, workspace)
        issue_a = _issue(project, workspace, user, state, "A")
        issue_b = _issue(project, workspace, user, state, "B")
        _relation(issue_a, issue_b, "relates_to", project, user)

        result = remove_issue_relation(
            workspace_slug=workspace.slug,
            issue_id=issue_a.id,
            related_issue_id=issue_b.id,
            relation_type=relation_type,
            actor_id=user.id,
            project_id=project.id,
            requested_data="{}",
            origin="https://testserver",
        )

        assert result is False
        assert IssueRelation.objects.count() == 1

    @patch("plane.utils.issue_relation_removal.issue_activity")
    def test_missing_relation_returns_false_without_activity(self, mock_activity, workspace, create_user):
        user = create_user
        project = _project(workspace, user)
        state = _state(project, workspace)
        issue_a = _issue(project, workspace, user, state, "A")
        issue_b = _issue(project, workspace, user, state, "B")

        result = remove_issue_relation(
            workspace_slug=workspace.slug,
            issue_id=issue_a.id,
            related_issue_id=issue_b.id,
            relation_type="blocked_by",
            actor_id=user.id,
            project_id=project.id,
            requested_data="{}",
            origin="https://testserver",
        )

        assert result is False
        mock_activity.delay.assert_not_called()

    @patch("plane.utils.issue_relation_removal.issue_activity")
    def test_emits_single_deleted_activity_with_serialized_instance(self, mock_activity, workspace, create_user):
        user = create_user
        project = _project(workspace, user)
        state = _state(project, workspace)
        issue_a = _issue(project, workspace, user, state, "A")
        issue_b = _issue(project, workspace, user, state, "B")
        _relation(issue_a, issue_b, "blocked_by", project, user)

        result = remove_issue_relation(
            workspace_slug=workspace.slug,
            issue_id=str(issue_a.id),
            related_issue_id=str(issue_b.id),
            relation_type="blocked_by",
            actor_id=str(user.id),
            project_id=str(project.id),
            requested_data='{"relation_type": "blocked_by"}',
            origin="https://testserver",
        )
        kwargs = mock_activity.delay.call_args.kwargs
        expected_kwargs = {
            "type": "issue_relation.activity.deleted",
            "requested_data": '{"relation_type": "blocked_by"}',
            "actor_id": str(user.id),
            "issue_id": str(issue_a.id),
            "project_id": str(project.id),
            "notification": True,
            "origin": "https://testserver",
        }

        for key in ("epoch", "current_instance"):
            assert key in kwargs
            del kwargs[key]

        assert result is True
        assert mock_activity.delay.call_count == 1
        assert kwargs == expected_kwargs
