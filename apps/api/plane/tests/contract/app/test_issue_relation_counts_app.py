# Copyright (c) 2023-present Plane Software, Inc. and contributors
# SPDX-License-Identifier: AGPL-3.0-only
# See the LICENSE file for details.

import pytest
from django.utils import timezone
from rest_framework import status

from plane.db.models import (
    Issue,
    IssueRelation,
    Project,
    ProjectMember,
    State,
)
pytestmark = pytest.mark.django_db


def _state(project, workspace, group, name):
    return State.objects.create(
        name=name,
        project=project,
        workspace=workspace,
        group=group,
        default=True,
    )


def _issue(project, workspace, user, state, name):
    return Issue.objects.create(
        name=name,
        workspace=workspace,
        project=project,
        state=state,
        created_by=user,
    )


def _relation(blocked, blocker, project, workspace, user):
    return IssueRelation.objects.create(
        issue=blocked,
        related_issue=blocker,
        relation_type="blocked_by",
        project=project,
        workspace=workspace,
        created_by=user,
    )


@pytest.fixture
def project_with_member(db, workspace, create_user):
    project = Project.objects.create(
        name="Relation Counts Project",
        identifier="RLC",
        workspace=workspace,
        created_by=create_user,
    )
    ProjectMember.objects.create(project=project, member=create_user, role=20, is_active=True)
    return project


@pytest.fixture
def relation_setup(db, workspace, create_user, project_with_member):
    project = project_with_member
    backlog = _state(project, workspace, "backlog", "Backlog")
    done = _state(project, workspace, "completed", "Done")
    blocked = _issue(project, workspace, create_user, backlog, "Blocked item")
    active_blocker = _issue(project, workspace, create_user, backlog, "Active blocker")
    done_blocker = _issue(project, workspace, create_user, done, "Done blocker")
    _relation(blocked, active_blocker, project, workspace, create_user)
    _relation(blocked, done_blocker, project, workspace, create_user)
    return {
        "project": project,
        "blocked": blocked,
        "active_blocker": active_blocker,
        "done_blocker": done_blocker,
    }


def _fetch_issue(session_client, workspace, project, issue_id):
    url = f"/api/workspaces/{workspace.slug}/projects/{project.id}/issues/"
    response = session_client.get(url)
    assert response.status_code == status.HTTP_200_OK
    payload = response.data
    results = payload.get("results", payload) if isinstance(payload, dict) else payload
    return next(item for item in results if str(item["id"]) == str(issue_id))


@pytest.mark.contract
class TestIssueRelationCountsPayload:
    def test_blocked_item_counts_unresolved_blockers(
        self, session_client, workspace, create_user, relation_setup
    ):
        item = _fetch_issue(
            session_client, workspace, relation_setup["project"], relation_setup["blocked"].id
        )
        assert item["blocked_by_count"] == 1
        assert item["blocking_count"] == 0

    def test_blocker_carries_blocking_count(
        self, session_client, workspace, create_user, relation_setup
    ):
        item = _fetch_issue(
            session_client,
            workspace,
            relation_setup["project"],
            relation_setup["active_blocker"].id,
        )
        assert item["blocking_count"] == 1
        assert item["blocked_by_count"] == 0

    def test_item_without_relations_carries_zero_counts(
        self, session_client, workspace, create_user, relation_setup
    ):
        project = relation_setup["project"]
        lone = Issue.objects.create(
            name="Lone item",
            workspace=workspace,
            project=project,
            state=relation_setup["active_blocker"].state,
            created_by=create_user,
        )
        item = _fetch_issue(session_client, workspace, project, lone.id)
        assert item["blocked_by_count"] == 0
        assert item["blocking_count"] == 0

    def test_archived_deleted_and_draft_blockers_not_counted(
        self, session_client, workspace, create_user, project_with_member
    ):
        project = project_with_member
        backlog = _state(project, workspace, "backlog", "Backlog")
        blocked = _issue(project, workspace, create_user, backlog, "Blocked item")
        archived = _issue(project, workspace, create_user, backlog, "Archived blocker")
        deleted = _issue(project, workspace, create_user, backlog, "Deleted blocker")
        draft = _issue(project, workspace, create_user, backlog, "Draft blocker")

        for blocker in (archived, deleted, draft):
            _relation(blocked, blocker, project, workspace, create_user)

        Issue.objects.filter(id=archived.id).update(archived_at=timezone.now().date())
        Issue.objects.filter(id=draft.id).update(is_draft=True)
        IssueRelation.objects.filter(issue=blocked, related_issue=deleted).update(deleted_at=timezone.now())

        item = _fetch_issue(session_client, workspace, project, blocked.id)
        assert item["blocked_by_count"] == 0

    def test_cross_project_blocker_counted(
        self, session_client, workspace, create_user, project_with_member
    ):
        project_a = project_with_member
        project_b = Project.objects.create(
            name="Relation Counts Project B",
            identifier="RLB",
            workspace=workspace,
            created_by=create_user,
        )
        ProjectMember.objects.create(project=project_b, member=create_user, role=20, is_active=True)
        state_a = _state(project_a, workspace, "backlog", "Backlog A")
        state_b = _state(project_b, workspace, "backlog", "Backlog B")
        blocked = _issue(project_a, workspace, create_user, state_a, "Blocked in A")
        blocker = _issue(project_b, workspace, create_user, state_b, "Blocker in B")
        _relation(blocked, blocker, project_a, workspace, create_user)

        item = _fetch_issue(session_client, workspace, project_a, blocked.id)
        assert item["blocked_by_count"] == 1
