/**
 * Copyright (c) 2023-present Plane Software, Inc. and contributors
 * SPDX-License-Identifier: AGPL-3.0-only
 * See the LICENSE file for details.
 */

import { useRef, useState } from "react";
import type { FC } from "react";
import { observer } from "mobx-react";
import { useParams } from "next/navigation";
// constants
import { ISSUE_PRIORITIES } from "@plane/constants";
// i18n
import { useTranslation } from "@plane/i18n";
// icons
import { PriorityIcon, StateGroupIcon, type ISvgIcons } from "@plane/propel/icons";
// skeleton
import { Skeleton } from "@plane/propel/skeleton";
// tooltip
import { Tooltip } from "@plane/propel/tooltip";
// types
import type { TIssue, TIssueRelationTypes } from "@plane/types";
// utils
import { cn } from "@plane/utils";
// hooks
import { useIssueDetail } from "@/hooks/store/use-issue-detail";
import { usePlatformOS } from "@/hooks/use-platform-os";
import { useProject } from "@/hooks/store/use-project";
import { useProjectState } from "@/hooks/store/use-project-state";

const SINGLE_RELATION_COUNT = 1;

const COUNT_I18N_KEY: Record<TRelationChipType, string> = {
  blocked_by: "issue.relation.blocked_by_count",
  blocking: "issue.relation.blocking_count",
};

export type TRelationChipType = Extract<TIssueRelationTypes, "blocked_by" | "blocking">;

const RelationChipTooltipCard = observer(function RelationChipTooltipCard({
  blocker,
  rowProjectId,
}: {
  blocker: TIssue;
  rowProjectId: string;
}) {
  // store hooks
  const { getProjectById, getProjectIdentifierById } = useProject();
  const { getStateById } = useProjectState();
  // derived values
  const projectDetails = getProjectById(blocker.project_id);
  const projectIdentifier = getProjectIdentifierById(blocker.project_id);
  const stateDetails = getStateById(blocker.state_id);
  const priorityTitle = ISSUE_PRIORITIES.find((priority) => priority.key === (blocker.priority ?? "none"))?.title;
  const showProject = !!projectDetails && blocker.project_id !== rowProjectId;

  return (
    <div className="flex w-64 flex-col gap-1.5 py-1">
      <div className="flex items-center gap-2">
        <span className="flex-shrink-0 text-caption-sm-medium text-primary">
          {projectIdentifier}-{blocker.sequence_id}
        </span>
        {showProject && <span className="truncate text-caption-sm-regular text-secondary">{projectDetails?.name}</span>}
      </div>
      <div className="truncate text-caption-sm-regular text-primary">{blocker.name}</div>
      <div className="flex items-center gap-2">
        {stateDetails && (
          <div className="flex items-center gap-1">
            <StateGroupIcon stateGroup={stateDetails.group} color={stateDetails.color} className="size-3 shrink-0" />
            <span className="truncate text-caption-sm-regular text-secondary">{stateDetails.name}</span>
          </div>
        )}
        <div className="flex items-center gap-1">
          <PriorityIcon priority={blocker.priority ?? "none"} size={12} className="shrink-0" />
          <span className="truncate text-caption-sm-regular text-secondary">{priorityTitle}</span>
        </div>
      </div>
    </div>
  );
});

const RelationChipSkeleton = () => (
  <div className="flex w-64 flex-col gap-2 py-1" role="status">
    <Skeleton.Item height="0.75rem" width="35%" />
    <Skeleton.Item height="0.75rem" width="95%" />
    <Skeleton.Item height="0.75rem" width="55%" />
  </div>
);

export interface IRelationCountChipProps {
  issue: TIssue;
  relationType: TRelationChipType;
  count: number;
  icon: FC<ISvgIcons>;
  chipClassName: string;
}

export const RelationCountChip = observer(function RelationCountChip(props: IRelationCountChipProps) {
  const { issue, relationType, count, icon: Icon, chipClassName } = props;
  // i18n
  const { t } = useTranslation();
  // router
  const { workspaceSlug } = useParams();
  // store hooks
  const {
    relation: { fetchRelations, getRelationByIssueIdRelationType },
    issue: { getIssueById },
  } = useIssueDetail();
  const { isMobile } = usePlatformOS();
  // state
  const [isFetching, setIsFetching] = useState(false);
  const [hasFailed, setHasFailed] = useState(false);
  const fetchInFlightRef = useRef(false);
  // derived values
  const relatedIssueIds = getRelationByIssueIdRelationType(issue.id, relationType);
  const relatedIssue = relatedIssueIds?.length === SINGLE_RELATION_COUNT ? getIssueById(relatedIssueIds[0]) : undefined;
  const countLabel = t(COUNT_I18N_KEY[relationType], { count });
  const projectId = issue.project_id ?? "";

  const handleMouseEnter = () => {
    if (isMobile) return;
    if (count !== SINGLE_RELATION_COUNT) return;
    if (relatedIssueIds !== undefined || hasFailed || fetchInFlightRef.current) return;
    if (!workspaceSlug || !issue.project_id || !issue.id) return;

    fetchInFlightRef.current = true;
    setIsFetching(true);
    fetchRelations(workspaceSlug.toString(), issue.project_id, issue.id)
      .catch((error) => {
        console.error("Failed to fetch issue relations for tooltip:", error);
        setHasFailed(true);
      })
      .finally(() => {
        fetchInFlightRef.current = false;
        setIsFetching(false);
      });
  };

  const tooltipContent = relatedIssue ? (
    <RelationChipTooltipCard blocker={relatedIssue} rowProjectId={projectId} />
  ) : isFetching ? (
    <RelationChipSkeleton />
  ) : (
    countLabel
  );

  return (
    <Tooltip tooltipContent={tooltipContent} isMobile={isMobile} renderByDefault={false}>
      <div
        onMouseEnter={handleMouseEnter}
        className={cn(
          "flex h-5 flex-shrink-0 items-center justify-center gap-2 overflow-hidden rounded-sm border-[0.5px] border-strong px-2.5 py-1",
          chipClassName
        )}
      >
        <Icon className="h-3 w-3 flex-shrink-0" />
        <div className="text-caption-sm-regular">{count}</div>
      </div>
    </Tooltip>
  );
});
