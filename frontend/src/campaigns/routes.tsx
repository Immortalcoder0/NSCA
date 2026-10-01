import React from "react";
import { Route, Routes } from "react-router-dom";
import { CampaignListPage } from "./pages/CampaignListPage";
import { CampaignDetailPage } from "./pages/CampaignDetailPage";
import { CampaignComparePage } from "./pages/CampaignComparePage";
import { IngestionDashboardPage } from "../ingestion/pages/IngestionDashboardPage";

export const CampaignRoutes: React.FC = () => {
  return (
    <Routes>
      <Route index element={<CampaignListPage />} />
      <Route path="compare" element={<CampaignComparePage />} />
      <Route path=":id" element={<CampaignDetailPage />} />
      <Route path=":id/ingest" element={<IngestionDashboardPage />} />
    </Routes>
  );
};

export default CampaignRoutes;
