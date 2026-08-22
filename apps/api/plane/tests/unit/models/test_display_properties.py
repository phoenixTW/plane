# Copyright (c) 2023-present Plane Software, Inc. and contributors
# SPDX-License-Identifier: AGPL-3.0-only
# See the LICENSE file for details.

import importlib
from uuid import uuid4

import pytest
from django.apps import apps as global_apps
from django.db import connection

from plane.db.models import (
    Cycle,
    CycleUserProperties,
    IssueView,
    Module,
    ModuleUserProperties,
    ProjectUserProperty,
    WorkspaceUserProperties,
)
from plane.db.models.cycle import get_default_display_properties as cycle_defaults
from plane.db.models.issue import get_default_display_properties as issue_defaults
from plane.db.models.module import get_default_display_properties as module_defaults
from plane.db.models.view import get_default_display_properties as view_defaults
from plane.db.models.workspace import (
    get_default_display_properties as workspace_defaults,
)
from plane.tests.factories import ProjectFactory, UserFactory, WorkspaceFactory

MIGRATION_MODULE = "plane.db.migrations.0123_backfill_relation_count_display_properties"

LEGACY_KEYS = {
    "assignee": True,
    "attachment_count": True,
    "created_on": True,
    "due_date": True,
    "estimate": True,
    "key": True,
    "labels": True,
    "link": True,
    "priority": False,
    "start_date": True,
    "state": True,
    "sub_issue_count": True,
    "updated_on": True,
}

FACTORY_DEFAULTS = [
    issue_defaults,
    cycle_defaults,
    module_defaults,
    view_defaults,
]


def load_migration():
    return importlib.import_module(MIGRATION_MODULE)


def run_forward():
    migration = load_migration()
    with connection.schema_editor() as schema_editor:
        migration.backfill_relation_count_display_properties(global_apps, schema_editor)


def run_reverse():
    migration = load_migration()
    with connection.schema_editor() as schema_editor:
        migration.remove_relation_count_display_properties(global_apps, schema_editor)


@pytest.mark.unit
class TestRelationCountDisplayPropertyDefaults:
    @pytest.mark.parametrize("factory", FACTORY_DEFAULTS, ids=["issue", "cycle", "module", "view"])
    def test_flat_defaults_include_relation_counts(self, factory):
        defaults = factory()

        assert defaults["blocked_by_count"] is True
        assert defaults["blocking_count"] is True

    def test_workspace_defaults_include_relation_counts(self):
        defaults = workspace_defaults()

        assert defaults["display_properties"]["blocked_by_count"] is True
        assert defaults["display_properties"]["blocking_count"] is True

    @pytest.mark.parametrize("factory", FACTORY_DEFAULTS, ids=["issue", "cycle", "module", "view"])
    def test_flat_defaults_preserve_existing_keys(self, factory):
        defaults = factory()

        assert defaults == {**LEGACY_KEYS, "priority": True, "blocked_by_count": True, "blocking_count": True}

    @pytest.mark.django_db
    def test_new_rows_carry_relation_count_defaults(self):
        user = UserFactory(username=f"user-{uuid4()}")
        workspace = WorkspaceFactory(owner=user)
        project = ProjectFactory(workspace=workspace)

        project_property = ProjectUserProperty.objects.create(user=user, project=project)
        cycle = Cycle.objects.create(name="Cycle", project=project, owned_by=user)
        cycle_property = CycleUserProperties.objects.create(cycle=cycle, project=project, user=user)
        module = Module.objects.create(name="Module", project=project)
        module_property = ModuleUserProperties.objects.create(module=module, project=project, user=user)
        view = IssueView.objects.create(name="View", query={}, workspace=workspace, owned_by=user)
        workspace_property = WorkspaceUserProperties.objects.create(user=user, workspace=workspace)

        for row in (project_property, cycle_property, module_property, view):
            assert row.display_properties["blocked_by_count"] is True
            assert row.display_properties["blocking_count"] is True

        assert workspace_property.display_properties["display_properties"]["blocked_by_count"] is True
        assert workspace_property.display_properties["display_properties"]["blocking_count"] is True


@pytest.mark.unit
@pytest.mark.django_db
class TestRelationCountDisplayPropertiesMigration:
    def _create_user_workspace_project(self):
        user = UserFactory(username=f"user-{uuid4()}")
        workspace = WorkspaceFactory(owner=user)
        project = ProjectFactory(workspace=workspace)

        return user, workspace, project

    def _create_legacy_rows(self, workspace, project, user):
        legacy_flat = dict(LEGACY_KEYS)

        project_property = ProjectUserProperty.objects.create(
            user=user, project=project, display_properties=dict(legacy_flat)
        )
        cycle = Cycle.objects.create(name="Cycle", project=project, owned_by=user)
        cycle_property = CycleUserProperties.objects.create(
            cycle=cycle, project=project, user=user, display_properties=dict(legacy_flat)
        )
        module = Module.objects.create(name="Module", project=project)
        module_property = ModuleUserProperties.objects.create(
            module=module, project=project, user=user, display_properties=dict(legacy_flat)
        )
        view = IssueView.objects.create(
            name="View",
            query={},
            workspace=workspace,
            owned_by=user,
            display_properties=dict(legacy_flat),
        )
        workspace_property = WorkspaceUserProperties.objects.create(
            user=user,
            workspace=workspace,
            display_properties={"display_properties": dict(legacy_flat)},
        )

        return [project_property, cycle_property, module_property, view, workspace_property]

    def _flat_rows(self):
        return list(
            ProjectUserProperty.objects.all()
        ) + list(CycleUserProperties.objects.all()) + list(
            ModuleUserProperties.objects.all()
        ) + list(IssueView.objects.all())

    def test_forward_backfills_keys_and_preserves_existing_values(self):
        user, workspace, project = self._create_user_workspace_project()
        self._create_legacy_rows(workspace, project, user)

        run_forward()

        for row in self._flat_rows():
            assert row.display_properties["blocked_by_count"] is True
            assert row.display_properties["blocking_count"] is True
            assert row.display_properties["priority"] is False

        workspace_property = WorkspaceUserProperties.objects.get(workspace=workspace, user=user)
        inner = workspace_property.display_properties["display_properties"]
        assert inner["blocked_by_count"] is True
        assert inner["blocking_count"] is True
        assert inner["priority"] is False

    def test_forward_is_idempotent(self):
        user, workspace, project = self._create_user_workspace_project()
        self._create_legacy_rows(workspace, project, user)

        run_forward()
        run_forward()

        for row in self._flat_rows():
            assert row.display_properties["blocked_by_count"] is True
            assert row.display_properties["blocking_count"] is True
            assert row.display_properties["priority"] is False

    def test_reverse_removes_keys(self):
        user, workspace, project = self._create_user_workspace_project()
        self._create_legacy_rows(workspace, project, user)

        run_forward()
        run_reverse()

        for row in self._flat_rows():
            assert "blocked_by_count" not in row.display_properties
            assert "blocking_count" not in row.display_properties
            assert row.display_properties["priority"] is False

        workspace_property = WorkspaceUserProperties.objects.get(workspace=workspace, user=user)
        inner = workspace_property.display_properties["display_properties"]
        assert "blocked_by_count" not in inner
        assert "blocking_count" not in inner
