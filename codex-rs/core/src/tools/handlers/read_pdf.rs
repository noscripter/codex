use async_trait::async_trait;
use base64::engine::general_purpose::STANDARD as BASE64;
use base64::Engine as _;
use serde::Deserialize;
use tokio::fs;

use crate::function_tool::FunctionCallError;
use crate::protocol::EventMsg;
use crate::protocol::ReadPdfToolCallEvent;
use crate::tools::context::FunctionToolOutput;
use crate::tools::context::ToolInvocation;
use crate::tools::context::ToolPayload;
use crate::tools::handlers::parse_arguments;
use crate::tools::registry::ToolHandler;
use crate::tools::registry::ToolKind;
use codex_protocol::models::FunctionCallOutputContentItem;

pub struct ReadPdfHandler;

#[derive(Deserialize)]
struct ReadPdfArgs {
    path: String,
}

#[async_trait]
impl ToolHandler for ReadPdfHandler {
    type Output = FunctionToolOutput;

    fn kind(&self) -> ToolKind {
        ToolKind::Function
    }

    async fn handle(&self, invocation: ToolInvocation) -> Result<Self::Output, FunctionCallError> {
        let ToolInvocation {
            session,
            turn,
            payload,
            call_id,
            ..
        } = invocation;

        let arguments = match payload {
            ToolPayload::Function { arguments } => arguments,
            _ => {
                return Err(FunctionCallError::RespondToModel(
                    "read_pdf handler received unsupported payload".to_string(),
                ));
            }
        };

        let args: ReadPdfArgs = parse_arguments(&arguments)?;
        let abs_path = turn.resolve_path(Some(args.path));

        let metadata = fs::metadata(&abs_path).await.map_err(|e| {
            FunctionCallError::RespondToModel(format!(
                "unable to locate PDF at `{}`: {e}",
                abs_path.display()
            ))
        })?;

        if !metadata.is_file() {
            return Err(FunctionCallError::RespondToModel(format!(
                "PDF path `{}` is not a file",
                abs_path.display()
            )));
        }

        let bytes = fs::read(&abs_path).await.map_err(|e| {
            FunctionCallError::RespondToModel(format!(
                "failed to read PDF at `{}`: {e}",
                abs_path.display()
            ))
        })?;

        let filename = abs_path
            .file_name()
            .map(|n| n.to_string_lossy().into_owned())
            .unwrap_or_else(|| "document.pdf".to_string());

        let file_data = BASE64.encode(&bytes);

        session
            .send_event(
                turn.as_ref(),
                EventMsg::ReadPdfToolCall(ReadPdfToolCallEvent {
                    call_id,
                    path: abs_path,
                }),
            )
            .await;

        Ok(FunctionToolOutput::from_content(
            vec![FunctionCallOutputContentItem::InputFile { filename, file_data }],
            Some(true),
        ))
    }
}
