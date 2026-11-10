export interface SensorNodeSpec {
  node_id: string;
  label: string;
  anatomical_region: string;
  modality: "imu" | "eeg" | "emg";
  channels: string[];
  x_pos: number;
  y_pos: number;
}

export interface GraphEdge {
  source: string;
  target: string;
  kind: "anatomical" | "bilateral" | "functional" | "hybrid" | "corticospinal";
  weight: number;
  correlation: number;
}

export interface BodyGraph {
  node_order: string[];
  nodes: SensorNodeSpec[];
  edges: GraphEdge[];
  correlation_threshold: number;
  adjacency_matrix: number[][];
  normalized_adjacency: number[][];
  graph_density: number;
  mean_functional_correlation: number;
}

export interface Subject {
  subject_id: string;
  age_group: string;
  hoehn_yahr_stage: number;
  disease_duration_years: number;
  medication_state: "ON" | "OFF";
}

export interface FOGEvent {
  event_id: string;
  session_id: string;
  subject_id: string;
  onset_seconds: number;
  offset_seconds: number;
  trigger_task: string;
}

export interface Session {
  session_id: string;
  subject_id: string;
  sampling_rate_hz: number;
  duration_seconds: number;
  modalities: string[];
  events: FOGEvent[];
}

export interface SubjectSummaryItem {
  subject: Subject;
  sessions: Session[];
  total_fog_events: number;
  total_fog_duration_seconds: number;
}

export interface SubjectsResponse {
  count: number;
  items: SubjectSummaryItem[];
  privacy_note: string;
}

export interface FogEvaluationMetrics {
  auprc: number;
  f1_score: number;
  sensitivity: number;
  specificity: number;
  precision: number;
  false_positives_per_hour: number;
  mean_detection_latency_seconds: number;
  event_detection_rate: number;
  threshold: number;
  total_windows: number;
  positive_windows: number;
  methodology_note: string;
}

export interface WindowPredictionRecord {
  window_id: string;
  subject_id: string;
  session_id: string;
  start_seconds: number;
  end_seconds: number;
  true_label: number;
  fog_overlap_ratio: number;
  baseline_prob: number;
  st_gnn_prob: number;
  ankle_freeze_index: number;
}

export interface SubjectFoldReport {
  fold_id: string;
  held_out_subject_id: string;
  train_subject_ids: string[];
  train_windows_count: number;
  test_windows_count: number;
  test_fog_windows_count: number;
  baseline_metrics: FogEvaluationMetrics;
  st_gnn_metrics: FogEvaluationMetrics;
  auprc_gain: number;
}

export interface MetricsResponse {
  experiment_id: string;
  seed: number;
  window_size_seconds: number;
  window_stride_seconds: number;
  correlation_threshold: number;
  baseline_overall: FogEvaluationMetrics;
  st_gnn_overall: FogEvaluationMetrics;
  auprc_improvement_abs: number;
  f1_improvement_abs: number;
  per_subject_folds: SubjectFoldReport[];
  window_predictions: WindowPredictionRecord[];
  methodology_note: string;
}

export interface GraphResponse {
  experiment_id: string;
  regime: "normal" | "fog" | "both";
  normal_gait_graph: BodyGraph;
  fog_episode_graph: BodyGraph;
}

export interface ModelInfoResponse {
  model_type: string;
  pyg_available: boolean;
  backend: string;
  sensor_nodes_count: number;
  validation_protocol: string;
  rare_event_criterion: string;
  canonical_sensors: string[];
}


