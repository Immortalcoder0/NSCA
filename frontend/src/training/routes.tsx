import React from "react";
import { Route, Routes } from "react-router-dom";
import { TrainingQueuePage } from "./pages/TrainingQueuePage";
import { TrainingQuestionPage } from "./pages/TrainingQuestionPage";
import { TrainingResultPage } from "./pages/TrainingResultPage";
import { TrainingRatifyPage } from "./pages/TrainingRatifyPage";

export const TrainingRoutes: React.FC = () => {
  return (
    <Routes>
      <Route index element={<TrainingQueuePage />} />
      <Route path="queue/:platform" element={<TrainingQuestionPage />} />
      <Route path="questions" element={<TrainingQuestionPage />} />
      <Route path="result" element={<TrainingResultPage />} />
      <Route path="ratify" element={<TrainingRatifyPage />} />
    </Routes>
  );
};

export default TrainingRoutes;
