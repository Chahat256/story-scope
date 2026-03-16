export type JobStatus =
  | "pending"
  | "processing"
  | "extracting"
  | "chunking"
  | "indexing"
  | "analyzing"
  | "complete"
  | "failed";

export interface JobStatusResponse {
  job_id: string;
  status: JobStatus;
  progress: number;
  message: string;
  filename: string;
  created_at: string;
  updated_at: string;
}

export interface SupportingPassage {
  text: string;
  page_reference: string | null;
  relevance: string;
}

export interface CharacterAnalysis {
  name: string;
  aliases: string[];
  role: string;
  defining_traits: string[];
  goals: string[];
  conflicts: string[];
  important_relationships: string[];
  supporting_passages: SupportingPassage[];
  confidence: string;
}

export interface RelationshipAnalysis {
  character_a: string;
  character_b: string;
  relationship_type: string;
  description: string;
  dynamics: string;
  supporting_passages: SupportingPassage[];
  confidence: string;
}

export interface ThemeAnalysis {
  theme: string;
  description: string;
  motifs: string[];
  supporting_passages: SupportingPassage[];
  prevalence: string;
}

export interface TropeAnalysis {
  trope_name: string;
  trope_id: string;
  confidence: string;
  explanation: string;
  supporting_passages: SupportingPassage[];
  related_characters: string[];
}

export interface NovelOverview {
  title_guess: string;
  author_guess: string | null;
  genre_guess: string;
  setting_description: string;
  narrative_summary: string;
  estimated_time_period: string | null;
  point_of_view: string;
  tone: string;
}

export interface AnalysisReport {
  job_id: string;
  overview: NovelOverview;
  characters: CharacterAnalysis[];
  relationships: RelationshipAnalysis[];
  themes: ThemeAnalysis[];
  tropes: TropeAnalysis[];
  created_at: string;
}

export interface ChatMessage {
  role: "user" | "assistant";
  content: string;
}

export interface ChatResponse {
  response: string;
  sources: SupportingPassage[];
  confidence: string;
}
