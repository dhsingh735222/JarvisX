export interface User {
  id: number;
  username: string;
  email: string;
  full_name: string;
  created_at: string;
}

export interface Message {
  id: number;
  role: "user" | "assistant" | "tool" | "system";
  content: string;
  tool_calls?: { id: string; name: string; input: Record<string, unknown> }[] | null;
  tool_use_id?: string | null;
  created_at: string;
}

export interface Conversation {
  id: number;
  title: string;
  created_at: string;
  updated_at: string;
}

export interface ConversationDetail extends Conversation {
  messages: Message[];
}

export interface PendingAction {
  id: number;
  conversation_id: number;
  tool_name: string;
  tool_input: Record<string, unknown>;
  status: string;
  created_at: string;
}

export interface ChatResponse {
  conversation_id: number;
  messages: Message[];
  pending_action: PendingAction | null;
}

export interface ApiKeyStatus {
  provider: string;
  configured: boolean;
  updated_at: string | null;
}

export interface SettingsData {
  llm_provider: string;
  llm_model: string;
  tts_engine: string;
  api_keys: ApiKeyStatus[];
}

export interface ActivityLogEntry {
  id: number;
  action_type: string;
  tool_name: string | null;
  input_data: unknown;
  output_data: unknown;
  status: string;
  created_at: string;
}

export interface MemoryItem {
  id: number;
  category: string;
  key: string;
  value: string;
  created_at: string;
  updated_at: string;
}
