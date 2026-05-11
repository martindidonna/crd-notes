export type Workspace = {
  id: string;
  name: string;
  description: string;
  is_default: boolean;
  created_at: string;
  updated_at: string;
};

export type Prompt = {
  id: string;
  title: string;
  description: string;
};

export type LibraryEntry = {
  id: string;
  workspace_id: string;
  title: string;
  notes: string;
  participants: string[];
  source_filename: string;
  audio_filename: string | null;
  duration_seconds: number | null;
  recorded_on: string | null;
  created_at: string;
  summary_count: number;
  operation_open_count: number;
  operation_total_count: number;
  tags: string[];
  keywords: string[];
  people: string[];
  topics: string[];
};

export type JobStatus = {
  id: string;
  status: string;
  stage: string;
  progress: number;
  message: string;
  error: string | null;
  entry_id: string | null;
  created_at: string;
  updated_at: string;
};

export type RecordingSource = {
  id: string;
  label: string;
};

export type RecordingSources = {
  microphones: RecordingSource[];
  system: RecordingSource[];
  window_supported: boolean;
  window_detail: string;
};

export type RecordingMode = "microphone" | "system" | "microphone_system" | "window";

export type RecordingSession = {
  id: string;
  workspace_id: string;
  title: string;
  recorded_on: string | null;
  notes: string;
  participants: string[];
  mode: RecordingMode;
  microphone_device: string;
  system_device: string;
  window_hint: string;
  status: string;
  elapsed_seconds: number;
  bookmarks: Array<{
    id: string;
    label: string;
    timestamp_seconds: number;
    created_at: string;
  }>;
  created_at: string;
  updated_at: string;
  error: string;
};

export type Summary = {
  id: string;
  entry_id: string;
  provider: string;
  model: string;
  prompt_id: string;
  content: string;
  created_at: string;
  tags: string[];
  keywords: string[];
  people: string[];
  topics: string[];
  context: string;
};

export type LibraryDetail = {
  entry: LibraryEntry & { transcript: string };
  summaries: Summary[];
};

export type OperationItem = {
  id: string;
  entry_id: string;
  summary_id: string | null;
  kind: "action" | "decision" | "risk" | "question" | string;
  text: string;
  owner: string;
  due_date: string | null;
  status: string;
  source: string;
  created_at: string;
  updated_at: string;
  entry: {
    id: string;
    workspace_id: string;
    title: string;
    recorded_on: string | null;
    created_at: string;
  } | null;
};

export type KnowledgeFile = {
  id: string;
  workspace_id: string;
  original_name: string;
  content_type: string;
  extension: string;
  size_bytes: number;
  sha256: string;
  status: string;
  error: string;
  created_at: string;
  updated_at: string;
};

export type IntelligenceItem = {
  text: string;
  score: number;
  count: number;
};

export type WorkspaceIntelligence = {
  workspace_id: string;
  generated_at: string;
  entry_count: number;
  summary_count: number;
  operation_open_count: number;
  top_tags: IntelligenceItem[];
  top_keywords: IntelligenceItem[];
  top_people: IntelligenceItem[];
  top_topics: IntelligenceItem[];
  clusters: Array<{
    id: string;
    title: string;
    terms: string[];
    entry_ids: string[];
    entry_titles: string[];
    score: number;
  }>;
  decisions: Array<IntelligenceTimelineItem>;
  risks: Array<IntelligenceTimelineItem>;
  questions: Array<IntelligenceTimelineItem>;
  local_brief: string;
};

export type IntelligenceTimelineItem = {
  text: string;
  entry_id: string;
  entry_title: string;
  recorded_on: string | null;
  created_at: string;
};

export type ChatThread = {
  id: string;
  workspace_id: string;
  title: string;
  created_at: string;
  updated_at: string;
};

export type ChatSource = {
  id: string;
  message_id: string;
  entry_id: string;
  entry_title: string;
  doc_type: string;
  source: string;
  score: number;
  snippet: string;
  created_at: string;
};

export type ChatMessage = {
  id: string;
  thread_id: string;
  role: string;
  content: string;
  provider: string;
  model: string;
  created_at: string;
  sources: ChatSource[];
  followups: string[];
};

export type SettingsResponse = {
  settings: Record<string, unknown>;
};

export type ProviderSettings = {
  enabled: boolean;
  base_url: string;
  model: string;
  api_key: string;
  available_models?: string[];
  timeout_seconds?: number;
};

export type ProviderModelsResponse = {
  provider: string;
  models: string[];
  source: string;
  message: string;
};

export type CopilotLoginStatus = {
  running?: boolean;
  completed?: boolean;
  success?: boolean;
  message?: string;
  verification_uri?: string;
  user_code?: string;
  models?: string[];
};
