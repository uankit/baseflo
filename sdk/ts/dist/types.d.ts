/**
 * Shared types — match the FastAPI Pydantic models in `server/app/api/v1/routes/`.
 *
 * These are hand-typed for v0.1; v0.2 will swap to `openapi-typescript-codegen`
 * against the live OpenAPI spec.
 */
/** A user identifier (UUIDv7 hex string). */
export type UUID = string;
/** ISO 8601 timestamp string, UTC. */
export type Timestamp = string;
export interface MagicLinkResponse {
    accepted: boolean;
    expires_at: string | null;
}
export interface MeResponse {
    user_id: UUID;
    organization_id: UUID;
    role: string | null;
    session_id: UUID | null;
    is_api_key: boolean;
}
export interface CreateOrgRequest {
    name: string;
    slug: string;
}
export interface CreateOrgResponse {
    organization_id: UUID;
    workspace_id: UUID;
    membership_id: UUID;
    slug: string;
    role: string;
}
export interface CreateProjectRequest {
    name: string;
    slug: string;
    description?: string;
    workspace_id?: UUID;
    deployment_mode?: "hosted" | "byo_db" | "self_host" | "local_dev";
}
export interface CreateProjectResponse {
    project_id: UUID;
    workspace_id: UUID;
    slug: string;
}
export interface ProjectSummary {
    id: UUID;
    organization_id: UUID;
    workspace_id: UUID;
    name: string;
    slug: string;
    description: string | null;
    deployment_mode: string;
    current_version_id: UUID | null;
    tenant_data_schema_name: string | null;
    created_at: Timestamp;
}
export interface ConnectorSummary {
    id: UUID;
    project_id: UUID;
    kind: string;
    display_name: string;
    status: string;
    config: Record<string, unknown>;
    last_sync_at: Timestamp | null;
    created_at: Timestamp;
}
export interface ConnectorListResponse {
    connectors: ConnectorSummary[];
}
export interface ConnectorInstallResult {
    connector_id: UUID;
    kind: string;
    project_id: UUID;
    display_name: string;
    account_id?: string | null;
}
export interface OAuthInstallResponse {
    redirect_url: string;
    state: string;
}
export interface StripeInstallRequest {
    project_id: UUID;
    api_key: string;
}
export interface ConversationSummary {
    id: UUID;
    project_id: UUID;
    state: string;
    created_at: Timestamp;
}
export interface ConversationMessage {
    id: UUID;
    conversation_id: UUID;
    author: string;
    content: string;
    created_at: Timestamp;
}
export interface CreateConversationRequest {
    project_id: UUID;
    content: string;
}
export interface JobAccepted {
    job_id: UUID;
    conversation_id: UUID;
    status: "queued" | string;
    sse_url: string;
}
export interface MessageResponse {
    message_id: UUID;
    conversation_id: UUID;
}
export interface SSEEvent {
    event: string;
    data: Record<string, unknown>;
    id?: string;
    retry?: number;
}
export interface RefinementRequest {
    request: string;
}
export interface RefinementResult {
    refinement_id: UUID;
    new_version_id: UUID | null;
    diff_summary: string | null;
    clarification_needed: boolean;
    clarification_question?: string | null;
}
export interface ErrorBody {
    error_code: string;
    message: string;
    details?: Record<string, unknown>;
    request_id?: string;
}
//# sourceMappingURL=types.d.ts.map