import React from "react";
import { Route, Routes } from "react-router-dom";
import { RulepackListPage } from "./pages/RulepackListPage";
import { RulepackDetailPage } from "./pages/RulepackDetailPage";
import { FrameworkCatalogPage } from "./pages/FrameworkCatalogPage";
import { FrameworkUpdateReviewPage } from "./pages/FrameworkUpdateReviewPage";

export const KnowledgeRoutes: React.FC = () => {
  return (
    <Routes>
      <Route index element={<RulepackListPage />} />
      <Route path="rulepacks/:id" element={<RulepackDetailPage />} />
      <Route path="frameworks" element={<FrameworkCatalogPage />} />
      <Route path="update-review" element={<FrameworkUpdateReviewPage />} />
    </Routes>
  );
};

export default KnowledgeRoutes;
