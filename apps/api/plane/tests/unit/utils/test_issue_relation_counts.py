# Copyright (c) 2023-present Plane Software, Inc. and contributors
# SPDX-License-Identifier: AGPL-3.0-only
# See the LICENSE file for details.

import pytest
from django.utils import timezone

from plane.db.models import Issue, IssueRelation, Project, State
from plane.utils.issue_relation_counts import blocked_by_count_subquery, blocking_count_subquery

pytestmark = pytest.mark.django_db


def _project(workspace, user, identifier="TST"):
    return Project.objects.create(
        name=f"Project {identifier}",
        identifier=identifier,
        workspace=workspace,
        created_by=user,
    )


def _state(project, workspace, group):
    return State.objects.create(
        name=f"State {group}",
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


def _counts(queryset):
    annotated = queryset.annotate(
        blocked_by_count=blocked_by_count_subquery(),
        blocking_count=blocking_count_subquery(),
    )
    return annotated.get()


@pytest.mark.unit
class TestIssueRelationCounts:
    def test_blocked_by_counts_unresolved_blockers_only(self, workspace, create_user):
        project = _project(workspace, create_user)
        backlog = _state(project, workspace, "backlog")
        done = _state(project, workspace, "completed")
        blocked = _issue(project, workspace, create_user, backlog, "Blocked")
        active_blocker = _issue(project, workspace, create_user, backlog, "Active blocker")
        done_blocker = _issue(project, workspace, create_user, done, "Done blocker")

        IssueRelation.objects.create(
            issue=blocked,
            related_issue=active_blocker,
            relation_type="blocked_by",
            project=project,
            workspace=workspace,
            created_by=create_user,
        )
        IssueRelation.objects.create(
            issue=blocked,
            related_issue=done_blocker,
            relation_type="blocked_by",
            project=project,
            workspace=workspace,
            created_by=create_user,
        )

        row = _counts(Issue.objects.filter(id=blocked.id))
        assert row.blocked_by_count == 1
        assert row.blocking_count == 0

        blocker_row = _counts(Issue.objects.filter(id=active_blocker.id))
        assert blocker_row.blocking_count == 1
        assert blocker_row.blocked_by_count == 0

    def test_no_relations_coalesces_to_zero(self, workspace, create_user):
        project = _project(workspace, create_user)
        backlog = _state(project, workspace, "backlog")
        issue = _issue(project, workspace, create_user, backlog, "Lonely")

        row = _counts(Issue.objects.filter(id=issue.id))
        assert row.blocked_by_count == 0
        assert row.blocking_count == 0

    def test_archived_deleted_and_draft_blockers_excluded(self, workspace, create_user):
        project = _project(workspace, create_user)
        backlog = _state(project, workspace, "backlog")
        blocked = _issue(project, workspace, create_user, backlog, "Blocked")
        archived = _issue(project, workspace, create_user, backlog, "Archived")
        deleted = _issue(project, workspace, create_user, backlog, "Deleted")
        draft = _issue(project, workspace, create_user, backlog, "Draft")

        for blocker in (archived, deleted, draft):
            IssueRelation.objects.create(
                issue=blocked,
                related_issue=blocker,
                relation_type="blocked_by",
                project=project,
                workspace=workspace,
                created_by=create_user,
            )

        Issue.objects.filter(id=archived.id).update(archived_at=timezone.now().date())
        Issue.objects.filter(id=draft.id).update(is_draft=True)
        IssueRelation.objects.filter(issue=blocked, related_issue=deleted).update(deleted_at=timezone.now())

        row = _counts(Issue.objects.filter(id=blocked.id))
        assert row.blocked_by_count == 0

    def test_soft_deleted_relation_not_counted(self, workspace, create_user):
        project = _project(workspace, create_user)
        backlog = _state(project, workspace, "backlog")
        blocked = _issue(project, workspace, create_user, backlog, "Blocked")
        blocker = _issue(project, workspace, create_user, backlog, "Blocker")

        relation = IssueRelation.objects.create(
            issue=blocked,
            related_issue=blocker,
            relation_type="blocked_by",
            project=project,
            workspace=workspace,
            created_by=create_user,
        )

        row = _counts(Issue.objects.filter(id=blocked.id))
        assert row.blocked_by_count == 1

        IssueRelation.objects.filter(id=relation.id).update(deleted_at=timezone.now())

        row = _counts(Issue.objects.filter(id=blocked.id))
        assert row.blocked_by_count == 0

    def test_cross_project_blocker_counted(self, workspace, create_user):
        project_a = _project(workspace, create_user, "AAA")
        project_b = _project(workspace, create_user, "BBB")
        state_a = _state(project_a, workspace, "backlog")
        state_b = _state(project_b, workspace, "backlog")
        blocked = _issue(project_a, workspace, create_user, state_a, "Blocked in A")
        blocker = _issue(project_b, workspace, create_user, state_b, "Blocker in B")

        IssueRelation.objects.create(
            issue=blocked,
            related_issue=blocker,
            relation_type="blocked_by",
            project=project_a,
            workspace=workspace,
            created_by=create_user,
        )

        row = _counts(Issue.objects.filter(id=blocked.id))
        assert row.blocked_by_count == 1

    def test_non_blocked_by_relations_ignored(self, workspace, create_user):
        project = _project(workspace, create_user)
        backlog = _state(project, workspace, "backlog")
        first = _issue(project, workspace, create_user, backlog, "First")
        second = _issue(project, workspace, create_user, backlog, "Second")

        IssueRelation.objects.create(
            issue=first,
            related_issue=second,
            relation_type="relates_to",
            project=project,
            workspace=workspace,
            created_by=create_user,
        )

        row = _counts(Issue.objects.filter(id=first.id))
        assert row.blocked_by_count == 0
        assert row.blocking_count == 0

    def test_outer_ref_parameter(self, workspace, create_user):
        project = _project(workspace, create_user)
        backlog = _state(project, workspace, "backlog")
        blocked = _issue(project, workspace, create_user, backlog, "Blocked")
        blocker = _issue(project, workspace, create_user, backlog, "Blocker")

        relation = IssueRelation.objects.create(
            issue=blocked,
            related_issue=blocker,
            relation_type="blocked_by",
            project=project,
            workspace=workspace,
            created_by=create_user,
        )

        row = (
            IssueRelation.objects.filter(id=relation.id)
            .annotate(
                blocked_by_count=blocked_by_count_subquery(outer_ref="issue_id"),
                blocking_count=blocking_count_subquery(outer_ref="related_issue_id"),
            )
            .get()
        )
        assert row.blocked_by_count == 1
        assert row.blocking_count == 1
