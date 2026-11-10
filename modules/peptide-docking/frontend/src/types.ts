export interface BindingSiteResidue {
  residue_id: string;
  chain: string;
  residue_name: string;
  pocket_role: string;
}

export interface Target {
  target_id: string;
  name: string;
  organism: string;
  uniprot_id: string;
  has_human_ortholog: boolean;
  ortholog_Verification_note: string;
  binding_site_residues: BindingSiteResidue[];
  structure_sha256: string;
}

export interface Peptide {
  peptide_id: string;
  sequence: string;
  length: number;
  molecular_weight_da: number;
  net_charge_ph7: number;
  gravy_hydropathy: number;
  isoelectric_point: number;
  source_family: string;
  notes: string;
}

export type InteractionType = "hydrogen_bond" | "salt_bridge" | "hydrophobic" | "pi_stacking";

export interface PoseContact {
  peptide_residue_index: number;
  peptide_residue: string;
  target_residue_id: string;
  distance_angstrom: number;
  interaction_type: InteractionType;
}

export interface DockingPose {
  pose_rank: number;
  docking_score: number;
  rmsd_to_top_pose_angstrom: number;
  interface_area_angstrom2: number;
  contacts: PoseContact[];
}

export interface DockingResult {
  job_id: string;
  run_id: string;
  peptide_id: string;
  target_id: string;
  engine_name: string;
  engine_version: string;
  status: "completed" | "cached" | "stub_blocked" | "failed";
  seed: number;
  parameters_hash: string;
  top_score: number;
  mean_top3_score: number;
  binding_site_contact_ratio: number;
  poses: DockingPose[];
  completed_at_utc: string;
  hypothesis_disclaimer: string;
}

export type TriageTier =
  "prioridade_alta_triagem" | "prioridade_media_triagem" | "baixa_prioridade_triagem";

export interface RankedCandidate {
  rank: number;
  peptide: Peptide;
  result: DockingResult;
  z_score: number;
  percentile: number;
  triage_tier: TriageTier;
  hypothesis_note: string;
}

export interface ResidueHotspotSummary {
  target_residue_id: string;
  contact_count: number;
  candidate_fraction: number;
}

export interface RunRankingSummary {
  run_id: string;
  engine_name: string;
  seed: number;
  total_evaluated: number;
  filtered_count: number;
  best_top_score: number;
  median_top_score: number;
  mean_top_score: number;
  std_top_score: number;
  high_priority_count: number;
  medium_priority_count: number;
  low_priority_count: number;
  residue_hotspots: ResidueHotspotSummary[];
  hypothesis_disclaimer: string;
}

export interface DockingRunManifest {
  run_id: string;
  target_id: string;
  engine_name: string;
  engine_version: string;
  seed: number;
  batch_size: number;
  total_jobs: number;
  completed_jobs: number;
  cached_jobs: number;
  failed_jobs: number;
  status: "running" | "completed" | "partial";
  parameters: Record<string, unknown>;
  started_at_utc: string;
  updated_at_utc: string;
  hypothesis_disclaimer: string;
}

export interface ResultsResponse {
  manifest: DockingRunManifest;
  target: Target;
  summary: RunRankingSummary;
  candidates: RankedCandidate[];
  hypothesis_disclaimer: string;
}
