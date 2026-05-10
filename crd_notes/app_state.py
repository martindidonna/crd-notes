from __future__ import annotations

from crd_notes.ai.factory import ConnectorFactory
from crd_notes.ai.service import AiService
from crd_notes.chat import WorkspaceChatService
from crd_notes.conversion import FFmpegLocator, MediaConverter
from crd_notes.core.config import SettingsStore
from crd_notes.jobs import JobRunner
from crd_notes.library.operations import OperationService
from crd_notes.library.repository import LibraryRepository
from crd_notes.library.service import LibraryService
from crd_notes.library.summary_metadata import SummaryMetadataService
from crd_notes.library.summary_workflow import SummaryWorkflowService
from crd_notes.library.workspace_intelligence import WorkspaceIntelligenceService
from crd_notes.rag import RagService
from crd_notes.recording import RecordingService
from crd_notes.transcription import WhisperTranscriber


settings_store = SettingsStore()
repository = LibraryRepository()
library_service = LibraryService(repository)
operation_service = OperationService(repository)
summary_metadata_service = SummaryMetadataService(repository)
workspace_intelligence_service = WorkspaceIntelligenceService(repository)
rag_service = RagService(repository)
ai_service = AiService(ConnectorFactory())
summary_workflow_service = SummaryWorkflowService(
    repository=repository,
    library_service=library_service,
    operation_service=operation_service,
    summary_metadata_service=summary_metadata_service,
    ai_service=ai_service,
    rag_service=rag_service,
)
workspace_chat_service = WorkspaceChatService(
    repository=repository,
    rag_service=rag_service,
    ai_service=ai_service,
)
converter = MediaConverter(FFmpegLocator())
transcriber = WhisperTranscriber()
job_runner = JobRunner(
    repository=repository,
    library_service=library_service,
    settings_store=settings_store,
    converter=converter,
    transcriber=transcriber,
    summary_workflow_service=summary_workflow_service,
)
recording_service = RecordingService(ffmpeg_locator=FFmpegLocator(), job_runner=job_runner)
