# Copyright (c) 2023-present Plane Software, Inc. and contributors
# SPDX-License-Identifier: AGPL-3.0-only
# See the LICENSE file for details.

import pytest

from plane.db.models import Issue, IssueRelation, Project, ProjectMember, State

pytestmark = [pytest.mark.django_db, pytest.mark.unit]


def _project(workspace, user):
    return Project.objects.create(
        name="P", identifier="P", workspace=workspace, created_by=user,
    )


def _state(project, workspace):
    return State.objects.create(
        name="Backlog", project=project, workspace=workspace, group="backlog", default=True,
    )


def _issue(project, workspace, user, state, name):
    return Issue.objects.create(
        name=name, sequence_id=1, priority="none",
        description_html="<p></p>", is_draft=False,
        workspace=workspace, project=project, state=state, created_by=user,
    )


def _make_member(project, workspace, user):
    ProjectMember.objects.create(
        project=project, workspace=workspace, member=user, role=20,
    )


@pytest.mark.unit
class TestRemoveRelationEndpoint:
    def test_remove_existing_relation_returns_204(self, workspace, create_user, session_client):
        project = _project(workspace, create_user)
        _make_member(project, workspace, create_user)
        state = _state(project, workspace)
        issue_a = _issue(project, workspace, create_user, state, "A")
        issue_b = _issue(project, workspace, create_user, state, "B")
        IssueRelation.objects.create(
            issue=issue_a, related_issue=issue_b, relation_type="blocked_by",
            project=project, workspace=workspace, created_by=create_user,
        )

        response = session_client.post(
            f"/api/workspaces/{workspace.slug}/projects/{project.id}/issues/{issue_a.id}/remove-relation/",
            data={"related_issue": str(issue_b.id), "relation_type": "blocked_by"},
            format="json",
        )

        assert response.status_code == 204
        assert not IssueRelation.objects.exists()

    def test_remove_nonexistent_relation_returns_404(self, workspace, create_user, session_client):
        project = _project(workspace, create_user)
        _make_member(project, workspace, create_user)
        state = _state(project, workspace)
        issue_a = _issue(project, workspace, create_user, state, "A")
        issue_b = _issue(project, workspace, create_user, state, "B")

        response = session_client.post(
            f"/api/workspaces/{workspace.slug}/projects/{project.id}/issues/{issue_a.id}/remove-relation/",
            data={"related_issue": str(issue_b.id), "relation_type": "blocked_by"},
            format="json",
        )

        assert response.status_code == 404
