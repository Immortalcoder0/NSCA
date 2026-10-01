import { createBrowserRouter, Navigate } from "react-router-dom";
import { Shell } from "./shell";
import { Showcase } from "./showcase";
import { RequireRole } from "./auth-guard";

// Track 1 Real Routes
import { CampaignListPage } from "../campaigns/pages/CampaignListPage";
import { CampaignDetailPage } from "../campaigns/pages/CampaignDetailPage";
import { CampaignComparePage } from "../campaigns/pages/CampaignComparePage";
import { IngestionDashboardPage } from "../ingestion/pages/IngestionDashboardPage";
import { EstateGridPage } from "../estate/pages/EstateGridPage";
import { DeviceDetailPage } from "../estate/pages/DeviceDetailPage";

// Track 2 Real Routes
import { FindingWorkbenchPage } from "../findings/pages/FindingWorkbenchPage";
import { FindingDetailPage } from "../findings/pages/FindingDetailPage";
import { DisputeAdjudicationPage } from "../findings/pages/DisputeAdjudicationPage";
import { AttackPathExplorerPage } from "../attack-paths/pages/AttackPathExplorerPage";
import { RemediationPlaybookPage } from "../remediation/pages/RemediationPlaybookPage";
import { RemediationDryRunPage } from "../remediation/pages/RemediationDryRunPage";

// Track 3 Real Routes
import { TrainingQueuePage } from "../training/pages/TrainingQueuePage";
import { TrainingQuestionPage } from "../training/pages/TrainingQuestionPage";
import { TrainingResultPage } from "../training/pages/TrainingResultPage";
import { TrainingRatifyPage } from "../training/pages/TrainingRatifyPage";

import { RulepackListPage } from "../knowledge/pages/RulepackListPage";
import { RulepackDetailPage } from "../knowledge/pages/RulepackDetailPage";
import { FrameworkCatalogPage } from "../knowledge/pages/FrameworkCatalogPage";
import { FrameworkUpdateReviewPage } from "../knowledge/pages/FrameworkUpdateReviewPage";

import { ReportLibraryPage } from "../reports/pages/ReportLibraryPage";
import { ReportViewerPage } from "../reports/pages/ReportViewerPage";

import { AdminDashboardPage } from "../admin/pages/AdminDashboardPage";
import { UsersManagementPage } from "../admin/pages/UsersManagementPage";
import { CredentialVaultPage } from "../admin/pages/CredentialVaultPage";
import { AuditLogViewerPage } from "../admin/pages/AuditLogViewerPage";

export const router = createBrowserRouter([
  {
    path: "/",
    element: <Shell />,
    children: [
      {
        index: true,
        element: <Navigate to="/campaigns" replace />,
      },
      {
        path: "_showcase",
        element: <Showcase />,
      },
      // Track 1: Campaigns & Ingestion
      {
        path: "campaigns",
        children: [
          {
            index: true,
            element: <CampaignListPage />,
          },
          {
            path: "compare",
            element: <CampaignComparePage />,
          },
          {
            path: ":id",
            element: <CampaignDetailPage />,
          },
          {
            path: ":id/ingest",
            element: <IngestionDashboardPage />,
          },
        ],
      },
      // Track 1: Ingestion
      {
        path: "ingestion",
        element: <IngestionDashboardPage />,
      },
      // Track 1: Estate
      {
        path: "estate",
        children: [
          {
            index: true,
            element: <EstateGridPage />,
          },
          {
            path: ":id",
            element: <DeviceDetailPage />,
          },
        ],
      },
      // Track 2: Findings & Risk Workbench
      {
        path: "findings",
        children: [
          {
            index: true,
            element: <FindingWorkbenchPage />,
          },
          {
            path: "attack-paths",
            element: <AttackPathExplorerPage />,
          },
          {
            path: ":id",
            element: <FindingDetailPage />,
          },
          {
            path: ":id/dispute",
            element: <DisputeAdjudicationPage />,
          },
        ],
      },
      // Track 2: Remediation Playbook & Dry-Run
      {
        path: "remediation",
        children: [
          {
            index: true,
            element: <RemediationPlaybookPage />,
          },
          {
            path: "dry-run",
            element: <RemediationDryRunPage />,
          },
        ],
      },
      // Track 3: Training Studio
      {
        path: "training",
        element: (
          <RequireRole roles={["lead_assessor", "assessor", "platform_administrator"]}>
            <TrainingQueuePage />
          </RequireRole>
        ),
      },
      {
        path: "training/queue/:platform",
        element: <TrainingQuestionPage />,
      },
      {
        path: "training/questions",
        element: <TrainingQuestionPage />,
      },
      {
        path: "training/result",
        element: <TrainingResultPage />,
      },
      {
        path: "training/ratify",
        element: (
          <RequireRole roles={["lead_assessor", "platform_administrator"]}>
            <TrainingRatifyPage />
          </RequireRole>
        ),
      },
      // Track 3: Knowledge Base
      {
        path: "knowledge",
        children: [
          {
            index: true,
            element: <RulepackListPage />,
          },
          {
            path: "rulepacks/:id",
            element: <RulepackDetailPage />,
          },
          {
            path: "frameworks",
            element: <FrameworkCatalogPage />,
          },
          {
            path: "update-review",
            element: <FrameworkUpdateReviewPage />,
          },
        ],
      },
      // Track 3: Reports Library & Viewer
      {
        path: "reports",
        children: [
          {
            index: true,
            element: <ReportLibraryPage />,
          },
          {
            path: ":id",
            element: <ReportViewerPage />,
          },
        ],
      },
      // Track 3: Administration & Credential Vault
      {
        path: "admin",
        children: [
          {
            index: true,
            element: (
              <RequireRole roles={["platform_administrator", "lead_assessor"]}>
                <AdminDashboardPage />
              </RequireRole>
            ),
          },
          {
            path: "users",
            element: (
              <RequireRole roles={["platform_administrator", "lead_assessor"]}>
                <UsersManagementPage />
              </RequireRole>
            ),
          },
          {
            path: "credentials",
            element: (
              <RequireRole roles={["platform_administrator", "lead_assessor"]}>
                <CredentialVaultPage />
              </RequireRole>
            ),
          },
          {
            path: "audit-log",
            element: (
              <RequireRole roles={["platform_administrator", "lead_assessor"]}>
                <AuditLogViewerPage />
              </RequireRole>
            ),
          },
        ],
      },
      {
        path: "*",
        element: (
          <div className="p-12 text-center space-y-3">
            <h2 className="text-xl font-bold">404 — Route Not Found</h2>
            <p className="text-sm text-muted-foreground">The requested section does not exist.</p>
          </div>
        ),
      },
    ],
  },
]);
