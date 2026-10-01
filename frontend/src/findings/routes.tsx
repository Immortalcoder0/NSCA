import React from "react";
import { Route, Routes } from "react-router-dom";
import { FindingWorkbenchPage } from "./pages/FindingWorkbenchPage";
import { FindingDetailPage } from "./pages/FindingDetailPage";
import { DisputeAdjudicationPage } from "./pages/DisputeAdjudicationPage";
import { AttackPathExplorerPage } from "../attack-paths/pages/AttackPathExplorerPage";

export const FindingRoutes: React.FC = () => {
  return (
    <Routes>
      <Route index element={<FindingWorkbenchPage />} />
      <Route path="attack-paths" element={<AttackPathExplorerPage />} />
      <Route path=":id" element={<FindingDetailPage />} />
      <Route path=":id/dispute" element={<DisputeAdjudicationPage />} />
    </Routes>
  );
};

export default FindingRoutes;
