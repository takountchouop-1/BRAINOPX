from sqlalchemy import Column, Integer, String, DateTime, Boolean, Text, ForeignKey
from sqlalchemy.sql import func
from .database import Base


class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    full_name = Column(String(150), nullable=False)
    email = Column(String(150), unique=True, index=True, nullable=False)
    hashed_password = Column(String(255), nullable=False)
    profile_picture = Column(String(500), nullable=True)
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    reset_code = Column(String(6), nullable=True)
    reset_code_expires_at = Column(DateTime(timezone=True), nullable=True)

    # Set on every successful login. Real usage data rather than a
    # placeholder — nothing else in the app tracked this before.
    last_login_at = Column(DateTime(timezone=True), nullable=True)

    address = Column(String(255), nullable=True)

    # "admin" | "member". Deliberately two separate defaults:
    #   - `default` (Python-side) is what the ORM fills in for a User
    #     object built without a role, i.e. every future self-registration
    #     via /auth/register — new signups get no admin rights by default.
    #   - `server_default` (DB-side) is what backfills rows that already
    #     existed when this column was added. Everyone using the app
    #     before roles existed had full, unrestricted access, so the
    #     migration preserves that instead of silently locking them out
    #     of a page they used to be able to reach implicitly.
    role = Column(String(20), nullable=False, default="member", server_default="admin")

    # JSON-encoded list of permission tags, e.g. ["data_export","data_import"].
    # Read/written through the helpers in app.services.user_access — never
    # touch this column directly, so "[]" vs NULL vs "not valid JSON"
    # is handled in one place.
    access = Column(Text, nullable=True)

    # UI language + AI reply language: "en" | "fr".
    language = Column(String(5), nullable=False, default="en", server_default="en")


class ConfigurationTask(Base):
    __tablename__ = "configuration_tasks"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    name = Column(String(150), nullable=False)
    description = Column(Text, nullable=True)
    category = Column(String(50), nullable=False, default="other")

    template_filename = Column(String(255), nullable=False)
    template_file_path = Column(String(500), nullable=False)
    expected_columns = Column(Text, nullable=False)

    # Real SQL Server table this task's script writes to, with rules derived from constraints.
    target_table = Column(String(150), nullable=True)
    column_rules = Column(Text, nullable=True)  # JSON list, see schema_introspection.py
    category_metadata = Column(Text, nullable=True)  # JSON: category-specific fields

    is_active = Column(Boolean, default=True)
    created_by = Column(Integer, ForeignKey("users.id"), nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    rules_document_filename = Column(String(255), nullable=True)  # ✅ Add this
    rules_document_path = Column(String(500), nullable=True)      # ✅ Add this
    rules_content = Column(Text, nullable=True)                  # ✅ Add this


class Notification(Base):
    __tablename__ = "notifications"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    title = Column(String(200), nullable=False)
    message = Column(Text, nullable=True)
    type = Column(String(50), nullable=False, default="info")  # info, success, warning, error
    link = Column(String(500), nullable=True)
    is_read = Column(Boolean, default=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now())


class ConfigurationRequest(Base):
    __tablename__ = "configuration_requests"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    # Nullable so an upload whose task template doesn't exist yet can still
    # open a configuration request and let the AI assistant gather the task
    # definition (and, if asked, escalate to an expert) instead of leaving
    # the user at a dead end. See app/services/task_definition_service.py.
    task_id = Column(
        Integer, 
        ForeignKey("configuration_tasks.id", ondelete="CASCADE"),
        nullable=True
    )
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)

    status = Column(String(50), nullable=False, default="draft")

    # How urgent this request is: "low", "medium" or "high".
    # server_default so rows that existed before the column was added
    # come back as "medium" rather than NULL.
    priority = Column(String(20), nullable=False, default="medium", server_default="medium")

    # Finer-grained sub-status for the report-analysis conversation flow,
    # separate from `status` so nothing already reading `status` breaks.
    # See app.services.report_analysis_service for the stage machine.
    current_stage = Column(String(30), nullable=False, default="draft", server_default="draft")

    uploaded_filename = Column(String(255), nullable=True)
    uploaded_file_path = Column(String(500), nullable=True)

    validation_errors = Column(Text, nullable=True)
    eval_profile = Column(Text, nullable=True)
    conversation = Column(Text, nullable=True)
    generated_script = Column(Text, nullable=True)

    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())


class ReportReferenceFile(Base):
    """
    A supplementary file (e.g. a production extract) the user submits
    mid-conversation to resolve an unknown-code anomaly on a report
    analysis request. A request can accumulate several of these across
    rounds — see app.services.report_analysis_service.
    """

    __tablename__ = "report_reference_files"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    request_id = Column(
        Integer,
        ForeignKey("configuration_requests.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    uploaded_by = Column(Integer, ForeignKey("users.id"), nullable=False)

    original_filename = Column(String(255), nullable=False)
    stored_path = Column(String(500), nullable=False)
    content_type = Column(String(100), nullable=True)
    size_bytes = Column(Integer, nullable=True)

    # Anomaly id (from eval_profile.analysis_state.anomalies) this file
    # was requested to resolve.
    linked_anomaly_id = Column(String(64), nullable=True)
    comparison_result = Column(Text, nullable=True)  # JSON: row-level diff output

    created_at = Column(DateTime(timezone=True), server_default=func.now())


class ReportScriptVersion(Base):
    """One generated SQL script for a report analysis request.

    Kept as its own history table rather than overwriting
    ConfigurationRequest.generated_script directly, so earlier versions
    stay inspectable if the user resolves more anomalies and regenerates.
    """

    __tablename__ = "report_script_versions"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    request_id = Column(
        Integer,
        ForeignKey("configuration_requests.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    version_number = Column(Integer, nullable=False)
    script_text = Column(Text, nullable=False)
    row_count = Column(Integer, nullable=False, default=0)
    generated_by = Column(Integer, ForeignKey("users.id"), nullable=True)

    generated_at = Column(DateTime(timezone=True), server_default=func.now())


class StepAttachment(Base):
    """
    A file or screenshot the user submits mid-walkthrough because the
    AI asked for one after several confused turns on the same step
    (see app.services.guided_engine's off-track/confusion tracking).

    Kept separate from ReportReferenceFile: that table is for a
    production-extract cross-check tied to a report-analysis anomaly,
    keyed off a specific column value. This one is a general "here is
    what I'm looking at" attachment tied to a step index, used only to
    give the AI more context for its explanation — never compared
    against anything automatically.
    """

    __tablename__ = "step_attachments"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    request_id = Column(
        Integer,
        ForeignKey("configuration_requests.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    uploaded_by = Column(Integer, ForeignKey("users.id"), nullable=False)

    step_index = Column(Integer, nullable=False)
    rule_name = Column(String(200), nullable=True)

    original_filename = Column(String(255), nullable=False)
    stored_path = Column(String(500), nullable=False)
    content_type = Column(String(100), nullable=True)
    size_bytes = Column(Integer, nullable=True)

    # True for an image (screenshot/photo) — those have no extracted
    # text, only a filename, since no OCR/vision pipeline reads them.
    is_image = Column(Boolean, default=False)
    extracted_text = Column(Text, nullable=True)

    created_at = Column(DateTime(timezone=True), server_default=func.now())


class SkillEngineRun(Base):
    """
    A Rule Engine run.

    Each run parses a rules document into discrete rules, then runs a
    dedicated AI workflow for EACH rule against the user's input. Per-rule
    conversations are stored inside `results_json` so the user can follow up
    on any single rule.
    """
    __tablename__ = "skill_engine_runs"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    task_id = Column(Integer, ForeignKey("configuration_tasks.id"), nullable=True)

    status = Column(String(50), nullable=False, default="completed")

    rules_json = Column(Text, nullable=False)       # parsed rules list
    user_input_text = Column(Text, nullable=True)   # pasted input text (or file text)
    results_json = Column(Text, nullable=True)      # per-rule workflow verdicts + conversations
    summary_stats = Column(Text, nullable=True)     # JSON {total, passed, needs_work, not_answered, progress}

    created_at = Column(DateTime(timezone=True), server_default=func.now())


class GuidedSession(Base):
    """
    One guided rule walkthrough.

    The user is walked through a run's rules one at a time. For each step
    they are shown an example input derived from that step's rule, and the
    value they submit is validated against it.

    Sessions live in their own table rather than inside
    SkillEngineRun.results_json so that:

      - a session is found by its own indexed session_id, instead of
        scanning a window of the user's recent runs;
      - writing step progress does not rewrite the run's results blob,
        so concurrent submissions cannot clobber each other.
    """
    __tablename__ = "guided_sessions"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)

    # Public identifier handed to the client.
    session_id = Column(String(32), unique=True, nullable=False, index=True)

    run_id = Column(
        Integer,
        ForeignKey("skill_engine_runs.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)

    current_step_index = Column(Integer, nullable=False, default=0)
    total_steps = Column(Integer, nullable=False, default=0)
    all_completed = Column(Boolean, nullable=False, default=False)

    # Per-step state: rule snapshot, status, attempts, suggested_example,
    # last verdict and conversation. See rule_router_service._rule_to_step().
    steps_json = Column(Text, nullable=False)

    started_at = Column(DateTime(timezone=True), server_default=func.now())
    completed_at = Column(DateTime(timezone=True), nullable=True)
    updated_at = Column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
    )


class AssistantConversation(Base):
    """One thread of the sidebar AI assistant, general chatbot for the app."""

    __tablename__ = "assistant_conversations"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    title = Column(String(200), nullable=True)

    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
    )


class AssistantMessage(Base):
    __tablename__ = "assistant_messages"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    conversation_id = Column(
        Integer,
        ForeignKey("assistant_conversations.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    role = Column(String(20), nullable=False)  # "user" | "assistant"
    content = Column(Text, nullable=False)

    created_at = Column(DateTime(timezone=True), server_default=func.now())


class AssistantAttachment(Base):
    """A file uploaded into the assistant chat (e.g. a PDF/Word doc to summarize).

    Attached before the conversation/message it belongs to necessarily exist yet
    (the user picks a file, then types and sends), so conversation_id/message_id
    start out null and get filled in once the message they're sent with is saved.

    conversation_id uses ondelete="SET NULL"; message_id deliberately has NO
    cascading action (plain FK, default NO ACTION). SQL Server treats SET NULL
    as a cascading action just like CASCADE — assistant_messages.conversation_id
    already cascades from assistant_conversations, so giving BOTH conversation_id
    and message_id a cascading action here would create two cascading paths from
    assistant_conversations down into this table (one direct, one via
    assistant_messages), which SQL Server rejects at DDL time (error 1785).
    Only one of the two can cascade; the other must be NO ACTION. Cleanup of
    attachment rows/files for a deleted conversation is therefore done
    explicitly in the assistant router (before the conversation delete), which
    also keeps message_id's NO ACTION FK safe — no attachment ever still
    points at a message_id whose row is about to be cascade-deleted.
    """

    __tablename__ = "assistant_attachments"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    conversation_id = Column(
        Integer,
        ForeignKey("assistant_conversations.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    message_id = Column(
        Integer,
        ForeignKey("assistant_messages.id"),
        nullable=True,
        index=True,
    )
    original_filename = Column(String(255), nullable=False)
    stored_path = Column(String(500), nullable=False)  # relative path, under uploads/
    content_type = Column(String(100), nullable=True)
    size_bytes = Column(Integer, nullable=True)
    extracted_text = Column(Text, nullable=True)
    extractable = Column(Boolean, default=True)

    created_at = Column(DateTime(timezone=True), server_default=func.now())


class SupportTicket(Base):
    """
    One help request from a user, worked by a specialist in the
    dedicated specialist interface.

    A ticket owns a two-way thread of SupportMessage rows: the user
    writes on one side, a specialist replies on the other. Tickets are
    a shared inbox — every active specialist sees every ticket — so
    there is no hard assignment; `claimed_by` only records who is
    currently working it.
    """

    __tablename__ = "support_tickets"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)

    # The configuration request that triggered the escalation, when one
    # exists (a no-template upload escalates from a request; a user can
    # also open a support thread directly).
    request_id = Column(
        Integer,
        ForeignKey("configuration_requests.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )

    subject = Column(String(200), nullable=False)
    status = Column(String(20), nullable=False, default="open", server_default="open")
    claimed_by = Column(Integer, ForeignKey("users.id"), nullable=True)
    resolved_by = Column(Integer, ForeignKey("users.id"), nullable=True)
    resolved_at = Column(DateTime(timezone=True), nullable=True)

    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
    )


class SupportMessage(Base):
    """
    One message inside a SupportTicket's thread. `sender_role` is
    "user", "specialist", "assistant" (a replayed AI assistant turn) or
    "system" (a marker such as the specialist-handoff point); the two
    read flags let each side track what it hasn't seen yet without
    needing two separate mailboxes.
    """

    __tablename__ = "support_messages"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    ticket_id = Column(
        Integer,
        ForeignKey("support_tickets.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    sender_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    sender_role = Column(String(20), nullable=False)  # "user" | "specialist"
    body = Column(Text, nullable=False)

    read_by_user = Column(Boolean, default=False)
    read_by_specialist = Column(Boolean, default=False)

    created_at = Column(DateTime(timezone=True), server_default=func.now())

