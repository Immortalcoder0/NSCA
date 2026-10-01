import React from "react";
import { Route, Routes } from "react-router-dom";
import { ReportLibraryPage } from "./pages/ReportLibraryPage";
import { ReportViewerPage } from "./pages/ReportViewerPage";

export const ReportRoutes: React.FC = () => {
  return (
    <Routes>
      <Route index element={<ReportLibraryPage />} />
      <Route path=":id" element={<ReportViewerPage />} />
    </Routes>
  );
};

export default ReportRoutes;
