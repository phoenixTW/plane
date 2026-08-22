/**
 * Copyright (c) 2023-present Plane Software, Inc. and contributors
 * SPDX-License-Identifier: AGPL-3.0-only
 * See the LICENSE file for details.
 */

import { observer } from "mobx-react";
// icons
import { Ban } from "lucide-react";
// ui
import { Row } from "@plane/ui";
// types
import type { TIssue } from "@plane/types";
import { ISSUE_RELATION_OPTIONS } from "@/components/relations";
// local components
import { RelationCountChip } from "../../properties/relation-count-chip";

type Props = {
  issue: TIssue;
  onClose: () => void;
  onChange: (issue: TIssue, data: Partial<TIssue>, updates: any) => void;
  disabled: boolean;
};

export const SpreadsheetBlockedByColumn = observer(function SpreadsheetBlockedByColumn(props: Props) {
  const { issue } = props;
  const count = issue?.blocked_by_count ?? 0;

  return (
    <Row className="flex h-11 w-full items-center border-b-[0.5px] border-subtle px-2.5 px-page-x py-1 text-11 group-[.selected-issue-row]:bg-accent-primary/5 hover:bg-layer-1 group-[.selected-issue-row]:hover:bg-accent-primary/10">
      {count > 0 && (
        <RelationCountChip
          issue={issue}
          relationType="blocked_by"
          count={count}
          icon={Ban}
          chipClassName={ISSUE_RELATION_OPTIONS.blocked_by.className}
        />
      )}
    </Row>
  );
});
