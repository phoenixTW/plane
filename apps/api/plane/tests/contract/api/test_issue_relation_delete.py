# Copyright (c) 2023-present Plane Software, Inc. and contributors
# SPDX-License-Identifier: AGPL-3.0-only
# See the LICENSE file for details.

import uuid
from urllib.parse import urlencode

import pytest
from rest_framework import status
from rest_framework.test import APIClient

from plane.db.models import Issue, IssueRelation, Project, ProjectMember, State, Workspace, WorkspaceMember, User
from plane.db.models.api import APIToken

pytestmark = [pytest.mark.django_db, pytest.mark.contract]


def _make_project(workspace, user):
    project = Project.objects.create(
        name="P", identifier="P", workspace=workspace, created_by=user,
    )
    ProjectMember.objects.create(
        project=project, workspace=workspace, member=user, role=20, is_active=True,
    )
    return project


def _make_state(project, workspace):
    return State.objects.create(
        name="Backlog", project=project, workspace=workspace, group="backlog", default=True,
    )


def _make_issue(project, workspace, user, state, name):
    return Issue.objects.create(
        name=name, sequence_id=1, priority="none",
        description_html="<p></p>", is_draft=False,
        workspace=workspace, project=project, state=state, created_by=user,
    )


def _base_url(slug, project_id, issue_id, related_id):
    return f"/api/v1/workspaces/{slug}/projects/{project_id}/work-items/{issue_id}/relations/{related_id}/"


def _delete_url(slug, project_id, issue_id, related_id, relation_type):
    return f"{_base_url(slug, project_id, issue_id, related_id)}?{urlencode({'relation_type': relation_type})}"


def _other_workspace_client():
    user = User.objects.create_user(email="other@plane.so", username="other-user", first_name="O", last_name="U")
    user.set_password("x")
    user.save()
    ws = Workspace.objects.create(name="Other", owner=user, slug="other-ws")
    WorkspaceMember.objects.create(workspace=ws, member=user, role=20)
    token = APIToken.objects.create(user=user, label="other")
    client = APIClient()
    client.credentials(HTTP_X_API_KEY=token.token)
    return client


class TestDeleteRelationSuccess:
    @pytest.mark.parametrize(
        "relation_type,stored_type,is_reverse",
        [
            ("blocked_by", "blocked_by", False),
            ("blocking", "blocked_by", True),
            ("duplicate", "duplicate", False),
            ("relates_to", "relates_to", False),
            ("start_before", "start_before", False),
            ("start_after", "start_before", True),
            ("finish_before", "finish_before", False),
            ("finish_after", "finish_before", True),
        ],
    )
    def test_delete_each_built_in_type(
        self, api_key_client, workspace, create_user, relation_type, stored_type, is_reverse
    ):
        project = _make_project(workspace, create_user)
        state = _make_state(project, workspace)
        issue_a = _make_issue(project, workspace, create_user, state, "A")
        issue_b = _make_issue(project, workspace, create_user, state, "B")

        if is_reverse:
            IssueRelation.objects.create(
                issue=issue_b, related_issue=issue_a, relation_type=stored_type,
                project=project, workspace=workspace, created_by=create_user,
            )
        else:
            IssueRelation.objects.create(
                issue=issue_a, related_issue=issue_b, relation_type=stored_type,
                project=project, workspace=workspace, created_by=create_user,
            )

        url = _delete_url(workspace.slug, project.id, issue_a.id, issue_b.id, relation_type)
        response = api_key_client.delete(url)

        assert response.status_code == 204
        assert not IssueRelation.objects.exists()


class TestDeleteRelationErrors:
    def test_missing_relation_type_returns_400(self, api_key_client, workspace, create_user):
        project = _make_project(workspace, create_user)
        state = _make_state(project, workspace)
        issue_a = _make_issue(project, workspace, create_user, state, "A")
        issue_b = _make_issue(project, workspace, create_user, state, "B")

        response = api_key_client.delete(_base_url(workspace.slug, project.id, issue_a.id, issue_b.id))

        assert response.status_code == 400

    def test_invalid_relation_type_returns_400(self, api_key_client, workspace, create_user):
        project = _make_project(workspace, create_user)
        state = _make_state(project, workspace)
        issue_a = _make_issue(project, workspace, create_user, state, "A")
        issue_b = _make_issue(project, workspace, create_user, state, "B")

        url = _delete_url(workspace.slug, project.id, issue_a.id, issue_b.id, "invalid")
        response = api_key_client.delete(url)

        assert response.status_code == 400

    def test_nonexistent_relation_returns_404(self, api_key_client, workspace, create_user):
        project = _make_project(workspace, create_user)
        state = _make_state(project, workspace)
        issue_a = _make_issue(project, workspace, create_user, state, "A")
        issue_b = _make_issue(project, workspace, create_user, state, "B")

        url = _delete_url(workspace.slug, project.id, issue_a.id, issue_b.id, "blocked_by")
        response = api_key_client.delete(url)

        assert response.status_code == 404

    def test_nonexistent_related_issue_returns_404(self, api_key_client, workspace, create_user):
        project = _make_project(workspace, create_user)
        state = _make_state(project, workspace)
        issue_a = _make_issue(project, workspace, create_user, state, "A")
        fake_id = uuid.uuid4()

        url = _delete_url(workspace.slug, project.id, issue_a.id, fake_id, "blocked_by")
        response = api_key_client.delete(url)

        assert response.status_code == 404

    def test_fallback_does_not_delete_different_relation_type(self, api_key_client, workspace, create_user):
        project = _make_project(workspace, create_user)
        state = _make_state(project, workspace)
        issue_a = _make_issue(project, workspace, create_user, state, "A")
        issue_b = _make_issue(project, workspace, create_user, state, "B")
        IssueRelation.objects.create(
            issue=issue_a, related_issue=issue_b, relation_type="relates_to",
            project=project, workspace=workspace, created_by=create_user,
        )

        url = _delete_url(workspace.slug, project.id, issue_a.id, issue_b.id, "blocked_by")
        response = api_key_client.delete(url)

        assert response.status_code == 404
        assert IssueRelation.objects.filter(relation_type="relates_to").exists()

    def test_cross_project_related_issue_returns_404(self, api_key_client, workspace, create_user):
        project_a = _make_project(workspace, create_user)
        project_b = Project.objects.create(
            name="P2", identifier="P2", workspace=workspace, created_by=create_user,
        )
        ProjectMember.objects.create(
            project=project_b, workspace=workspace, member=create_user, role=20, is_active=True,
        )
        state_a = _make_state(project_a, workspace)
        state_b = _make_state(project_b, workspace)
        issue_a = _make_issue(project_a, workspace, create_user, state_a, "A")
        issue_b = _make_issue(project_b, workspace, create_user, state_b, "B")
        IssueRelation.objects.create(
            issue=issue_a, related_issue=issue_b, relation_type="blocked_by",
            project=project_a, workspace=workspace, created_by=create_user,
        )

        url = _delete_url(workspace.slug, project_a.id, issue_a.id, issue_b.id, "blocked_by")
        response = api_key_client.delete(url)

        assert response.status_code == 404
        assert IssueRelation.objects.exists()

    def test_cross_tenant_api_key_returns_403(self, api_key_client, workspace, create_user):
        project = _make_project(workspace, create_user)
        state = _make_state(project, workspace)
        issue_a = _make_issue(project, workspace, create_user, state, "A")
        issue_b = _make_issue(project, workspace, create_user, state, "B")
        IssueRelation.objects.create(
            issue=issue_a, related_issue=issue_b, relation_type="blocked_by",
            project=project, workspace=workspace, created_by=create_user,
        )

        other_client = _other_workspace_client()
        url = _delete_url(workspace.slug, project.id, issue_a.id, issue_b.id, "blocked_by")
        response = other_client.delete(url)

        assert response.status_code == 403


class TestDeleteRelationOptions:
    def test_options_on_detail_reports_delete(self, api_key_client, workspace, create_user):
        project = _make_project(workspace, create_user)
        state = _make_state(project, workspace)
        issue_a = _make_issue(project, workspace, create_user, state, "A")
        issue_b = _make_issue(project, workspace, create_user, state, "B")

        response = api_key_client.options(_base_url(workspace.slug, project.id, issue_a.id, issue_b.id))

        assert response.status_code == 200
        assert "DELETE" in [m.upper() for m in response["Allow"].split(", ")]


