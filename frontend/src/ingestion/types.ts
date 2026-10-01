export type ArtifactOutcomeState =
  | "parsed"
  | "parsed_with_caveat"
  | "platform_not_taught"
  | "unidentified";

export interface CorrelatedArtifact {
  name: string;
  type: string;
  sha256: string;
}

export interface IngestionArtifactItem {
  id: string;
  device: string;
  platform?: string;
  os_version?: string;
  status: ArtifactOutcomeState;
  export_mode?: "verbose" | "terse" | "show_tech";
  correlated_artifacts: CorrelatedArtifact[];
  unassessable_controls_count?: number;
  training_questions_count?: number;
  training_estimate_minutes?: number;
  grammar_coverage?: number;
  message?: string;
}

export interface MissingDeviceItem {
  name: string;
  // The real `GET /campaigns/{id}/completeness` endpoint
  // (`nsca_platform/services/campaign.py::completeness`) only returns a
  // bare list of missing hostnames -- FR-ING-016's "reason/owner per
  // missing device" needs finding-lifecycle machinery that isn't wired up
  // to this endpoint yet (its own docstring flags this as real-for-M1,
  // owner-attribution-later). ip/role/owner are optional so real API data
  // renders honestly instead of fabricating contact details.
  ip?: string;
  role?: string;
  owner?: string;
  last_seen?: string;
}

export interface CollectionCompletenessData {
  total_in_scope: number;
  collected: number;
  missing: number;
  percentage: number;
  missing_devices: MissingDeviceItem[];
}
