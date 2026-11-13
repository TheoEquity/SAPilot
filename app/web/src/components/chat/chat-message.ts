import type { ChatMessage as StoredChatMessage } from '@/api/generated/models';

// Streaming events include the skill that produced a message; stored history may omit it.
export type ChatMessage = StoredChatMessage & { skill_id?: string };
