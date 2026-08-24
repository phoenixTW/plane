# Copyright (c) 2023-present Plane Software, Inc. and contributors
# SPDX-License-Identifier: AGPL-3.0-only
# See the LICENSE file for details.

import json

from django.core.serializers.json import DjangoJSONEncoder
from django.db.models import Q
from django.utils import timezone

from plane.bgtasks.issue_activities_task import issue_activity
from plane.db.models import IssueRelation
from plane.utils.issue_relation_mapper import get_actual_relation

REVERSE_RELATION_TYPES = ("blocking", "start_after", "finish_after")


def remove_issue_relation(
    *,
    workspace_slug,
    issue_id,
    related_issue_id,
    relation_type,
    actor_id,
    project_id,
    requested_data,
    origin,
):
    """Removes one relation between two work items. Returns True if a relation was deleted."""
    from plane.app.serializers import IssueRelationSerializer

    actual_relation = get_actual_relation(relation_type)
    if relation_type in REVERSE_RELATION_TYPES:
        first_issue_id, second_issue_id = related_issue_id, issue_id
    else:
        first_issue_id, second_issue_id = issue_id, related_issue_id
    relation = IssueRelation.objects.filter(
        workspace__slug=workspace_slug,
        issue_id=first_issue_id,
        related_issue_id=second_issue_id,
        relation_type=actual_relation,
    ).first()

    if relation is None:
        relation = IssueRelation.objects.filter(
            workspace__slug=workspace_slug,
        ).filter(
            Q(issue_id=related_issue_id, related_issue_id=issue_id)
            | Q(issue_id=issue_id, related_issue_id=related_issue_id)
        ).first()

    if relation is None:
        return False

    current_instance = json.dumps(IssueRelationSerializer(relation).data, cls=DjangoJSONEncoder)
    relation.delete()
    issue_activity.delay(
        type="issue_relation.activity.deleted",
        requested_data=requested_data,
        actor_id=str(actor_id),
        issue_id=str(issue_id),
        project_id=str(project_id),
        current_instance=current_instance,
        epoch=int(timezone.now().timestamp()),
        notification=True,
        origin=origin,
    )
    return True
