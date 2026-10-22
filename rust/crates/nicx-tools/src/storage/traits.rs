//! MemoryBackend trait for all storage backends.

use nicx_core::{NicxError, RetrievalResult};
use serde_json::Value;

pub trait MemoryBackend: Send + Sync {
    fn backend_id(&self) -> &str;
    fn store(
        &self,
        content: &str,
        source: &str,
        metadata: Option<&Value>,
    ) -> Result<String, NicxError>;
    fn retrieve(
        &self,
        query: &str,
        top_k: usize,
    ) -> Result<Vec<RetrievalResult>, NicxError>;
    fn delete(&self, doc_id: &str) -> Result<bool, NicxError>;
    fn clear(&self) -> Result<(), NicxError>;
    fn count(&self) -> Result<usize, NicxError>;
}
