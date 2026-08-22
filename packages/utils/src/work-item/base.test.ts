/**
 * Copyright (c) 2023-present Plane Software, Inc. and contributors
 * SPDX-License-Identifier: AGPL-3.0-only
 * See the LICENSE file for details.
 */

import { describe, it, expect } from "vitest";
import { generateWorkItemBranchName } from "./base";

describe("generateWorkItemBranchName", () => {
  it("builds username prefix, identifier, sequence id and title slug", () => {
    const branchName = generateWorkItemBranchName({
      displayName: "Kaustav",
      email: "kaustav@plane.so",
      projectIdentifier: "PROJ",
      sequenceId: 123,
      title: "Fix login redirect",
    });

    expect(branchName).toEqual("kaustav/PROJ-123-fix-login-redirect");
  });

  it("falls back to email local-part when display name sanitizes to empty", () => {
    const branchName = generateWorkItemBranchName({
      displayName: "कौस्तव",
      email: "kaustav.ron@gmail.com",
      projectIdentifier: "PROJ",
      sequenceId: 123,
      title: "Fix login redirect",
    });

    expect(branchName).toEqual("kaustav-ron/PROJ-123-fix-login-redirect");
  });

  it("drops username prefix when no email is given and display name sanitizes to empty", () => {
    const branchName = generateWorkItemBranchName({
      displayName: "कौस्तव",
      projectIdentifier: "PROJ",
      sequenceId: 123,
      title: "Fix login redirect",
    });

    expect(branchName).toEqual("PROJ-123-fix-login-redirect");
  });

  it("drops slug when title contains only emoji", () => {
    const branchName = generateWorkItemBranchName({
      displayName: "Kaustav",
      projectIdentifier: "PROJ",
      sequenceId: 123,
      title: "🎉🎉🎉",
    });

    expect(branchName).toEqual("kaustav/PROJ-123");
  });

  it("drops slug when title is empty", () => {
    const branchName = generateWorkItemBranchName({
      displayName: "Kaustav",
      projectIdentifier: "PROJ",
      sequenceId: 123,
      title: "",
    });

    expect(branchName).toEqual("kaustav/PROJ-123");
  });

  it("truncates slug at the last hyphen within 50 characters", () => {
    const branchName = generateWorkItemBranchName({
      displayName: "Kaustav",
      projectIdentifier: "PROJ",
      sequenceId: 123,
      title: "Fix login redirect bug in payment gateway module today",
    });

    const slug = branchName.split("PROJ-123-")[1];

    expect(branchName).toEqual("kaustav/PROJ-123-fix-login-redirect-bug-in-payment-gateway-module");
    expect(slug.length).toBeLessThanOrEqual(50);
    expect(slug.endsWith("-")).toBe(false);
  });

  it("hard cuts slug at 50 characters when the first word exceeds it", () => {
    const longWord = "a".repeat(60);

    const branchName = generateWorkItemBranchName({
      displayName: "Kaustav",
      projectIdentifier: "PROJ",
      sequenceId: 123,
      title: longWord,
    });

    expect(branchName).toEqual(`kaustav/PROJ-123-${"a".repeat(50)}`);
  });

  it("returns empty string when sequence id is missing", () => {
    const undefinedSequenceId = generateWorkItemBranchName({
      displayName: "Kaustav",
      projectIdentifier: "PROJ",
      sequenceId: undefined,
      title: "Fix login redirect",
    });

    const nullSequenceId = generateWorkItemBranchName({
      displayName: "Kaustav",
      projectIdentifier: "PROJ",
      sequenceId: null,
      title: "Fix login redirect",
    });

    expect(undefinedSequenceId).toEqual("");
    expect(nullSequenceId).toEqual("");
  });

  it("returns empty string when project identifier is missing", () => {
    const branchName = generateWorkItemBranchName({
      displayName: "Kaustav",
      projectIdentifier: undefined,
      sequenceId: 123,
      title: "Fix login redirect",
    });

    expect(branchName).toEqual("");
  });

  it("drops username prefix when display name and email both sanitize to empty", () => {
    const branchName = generateWorkItemBranchName({
      displayName: "!!!",
      email: "??@x.com",
      projectIdentifier: "PROJ",
      sequenceId: 123,
      title: "Fix login redirect",
    });

    expect(branchName).toEqual("PROJ-123-fix-login-redirect");
  });

  it("treats numeric zero sequence id as valid", () => {
    const branchName = generateWorkItemBranchName({
      displayName: "Kaustav",
      projectIdentifier: "PROJ",
      sequenceId: 0,
      title: "Fix login redirect",
    });

    expect(branchName).toEqual("kaustav/PROJ-0-fix-login-redirect");
  });

  it("collapses special characters in the title to single hyphens", () => {
    const branchName = generateWorkItemBranchName({
      displayName: "Kaustav",
      projectIdentifier: "PROJ",
      sequenceId: 123,
      title: "Fix: login & redirect!!",
    });

    expect(branchName).toEqual("kaustav/PROJ-123-fix-login-redirect");
  });
});
