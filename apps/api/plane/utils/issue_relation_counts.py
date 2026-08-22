# Copyright (c) 2023-present Plane Software, Inc. and contributors
# SPDX-License-Identifier: AGPL-3.0-only
# See the LICENSE file for details.

from django.db.models import F, Func, IntegerField, OuterRef, Subquery, Value
from django.db.models.functions import Coalesce

from plane.db.models import IssueRelation
from plane.db.models.issue import IssueRelationChoices
from plane.db.models.state import StateGroup

RESOLVED_STATE_GROUPS = [StateGroup.COMPLETED.value, StateGroup.CANCELLED.value]


def _count(qs):
    return Coalesce(
        Subquery(
            qs.order_by()
            .annotate(count=Func(F("id"), function="Count", output_field=IntegerField()))
            .values("count")[:1],
            output_field=IntegerField(),
        ),
        Value(0),
        output_field=IntegerField(),
    )


def blocked_by_count_subquery(outer_ref="id"):
    return _count(
        IssueRelation.objects.filter(
            issue_id=OuterRef(outer_ref),
            relation_type=IssueRelationChoices.BLOCKED_BY.value,
            deleted_at__isnull=True,
        )
        .exclude(related_issue__state__group__in=RESOLVED_STATE_GROUPS)
        .exclude(related_issue__archived_at__isnull=False)
        .exclude(related_issue__is_draft=True)
        .exclude(related_issue__deleted_at__isnull=False)
    )


def blocking_count_subquery(outer_ref="id"):
    return _count(
        IssueRelation.objects.filter(
            related_issue_id=OuterRef(outer_ref),
            relation_type=IssueRelationChoices.BLOCKED_BY.value,
            deleted_at__isnull=True,
        )
        .exclude(issue__state__group__in=RESOLVED_STATE_GROUPS)
        .exclude(issue__archived_at__isnull=False)
        .exclude(issue__is_draft=True)
        .exclude(issue__deleted_at__isnull=False)
    )
