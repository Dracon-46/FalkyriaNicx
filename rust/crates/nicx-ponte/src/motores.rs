//! PyO3 bindings for engine types.

use crate::nucleo::PyMessage;
use nicx_motores::InferenceEngine;
use pyo3::prelude::*;

/// Wraps the Engine enum (static dispatch internally, opaque to Python).
#[pyclass(name = "Engine")]
pub struct PyEngine {
    pub inner: nicx_motores::Engine,
}

#[pymethods]
impl PyEngine {
    /// Create an engine by key (e.g. "ollama", "vllm", "sglang", "llamacpp",
    /// "mlx", "lmstudio", "exo", "nexa", "uzu", "apple_fm").
    #[new]
    #[pyo3(signature = (engine_key="ollama", host=None))]
    fn new(engine_key: &str, host: Option<&str>) -> PyResult<Self> {
        let engine = match engine_key {
            "ollama" => nicx_motores::Engine::Ollama(nicx_motores::OllamaEngine::new(
                host.unwrap_or("http://localhost:11434"),
                120.0,
            )),
            "vllm" => nicx_motores::Engine::Vllm(nicx_motores::OpenAICompatEngine::vllm(
                host.unwrap_or("http://localhost:8000"),
            )),
            "sglang" => nicx_motores::Engine::Sglang(nicx_motores::OpenAICompatEngine::sglang(
                host.unwrap_or("http://localhost:30000"),
            )),
            "llamacpp" => nicx_motores::Engine::LlamaCpp(
                nicx_motores::OpenAICompatEngine::llamacpp(host.unwrap_or("http://localhost:8080")),
            ),
            "mlx" => nicx_motores::Engine::Mlx(nicx_motores::OpenAICompatEngine::mlx(
                host.unwrap_or("http://localhost:8080"),
            )),
            "lmstudio" => nicx_motores::Engine::LmStudio(
                nicx_motores::OpenAICompatEngine::lmstudio(host.unwrap_or("http://localhost:1234")),
            ),
            "exo" => nicx_motores::Engine::Exo(nicx_motores::OpenAICompatEngine::exo(
                host.unwrap_or("http://localhost:52415"),
            )),
            "nexa" => nicx_motores::Engine::Nexa(nicx_motores::OpenAICompatEngine::nexa(
                host.unwrap_or("http://localhost:18181"),
            )),
            "uzu" => nicx_motores::Engine::Uzu(nicx_motores::OpenAICompatEngine::uzu(
                host.unwrap_or("http://localhost:8080"),
            )),
            "apple_fm" => nicx_motores::Engine::AppleFm(
                nicx_motores::OpenAICompatEngine::apple_fm(host.unwrap_or("http://localhost:8079")),
            ),
            "vllm_native" => nicx_motores::Engine::VLLM(nicx_motores::VLLMEngine::new(
                host.unwrap_or("http://localhost"),
                8000,
                None,
                120.0,
            )),
            "sglang_native" => nicx_motores::Engine::SGLang(nicx_motores::SGLangEngine::new(
                host.unwrap_or("http://localhost"),
                30000,
                120.0,
            )),
            "llamacpp_native" => nicx_motores::Engine::LlamaCppNative(
                nicx_motores::LlamaCppEngine::new(host.unwrap_or("http://localhost"), 8080, 120.0),
            ),
            other => {
                return Err(PyErr::new::<pyo3::exceptions::PyValueError, _>(format!(
                    "Unknown engine: {other}"
                )));
            }
        };
        Ok(Self { inner: engine })
    }

    fn engine_id(&self) -> &str {
        self.inner.engine_id()
    }

    fn variant_key(&self) -> &str {
        self.inner.variant_key()
    }

    fn health(&self) -> bool {
        self.inner.health()
    }

    fn list_models(&self) -> PyResult<Vec<String>> {
        self.inner
            .list_models()
            .map_err(|e| PyErr::new::<pyo3::exceptions::PyRuntimeError, _>(e.to_string()))
    }

    #[pyo3(signature = (messages, model, temperature=0.7, max_tokens=1024))]
    fn generate(
        &self,
        messages: Vec<PyMessage>,
        model: &str,
        temperature: f64,
        max_tokens: i64,
    ) -> PyResult<String> {
        let core_msgs: Vec<nicx_nucleo::Message> = messages.iter().map(|m| m.to_core()).collect();
        let result = self
            .inner
            .generate(&core_msgs, model, temperature, max_tokens, None)
            .map_err(|e| PyErr::new::<pyo3::exceptions::PyRuntimeError, _>(e.to_string()))?;
        Ok(serde_json::to_string(&result).unwrap_or_default())
    }

    fn __repr__(&self) -> String {
        format!("Engine({})", self.inner.variant_key())
    }
}

/// Convenience alias for backward compatibility.
#[pyclass(name = "OllamaEngine")]
pub struct PyOllamaEngine {
    inner: nicx_motores::OllamaEngine,
}

#[pymethods]
impl PyOllamaEngine {
    #[new]
    #[pyo3(signature = (host="http://localhost:11434", timeout=120.0))]
    fn new(host: &str, timeout: f64) -> Self {
        Self {
            inner: nicx_motores::OllamaEngine::new(host, timeout),
        }
    }

    fn engine_id(&self) -> &str {
        self.inner.engine_id()
    }

    fn health(&self) -> bool {
        self.inner.health()
    }

    fn list_models(&self) -> PyResult<Vec<String>> {
        self.inner
            .list_models()
            .map_err(|e| PyErr::new::<pyo3::exceptions::PyRuntimeError, _>(e.to_string()))
    }

    #[pyo3(signature = (messages, model, temperature=0.7, max_tokens=1024))]
    fn generate(
        &self,
        messages: Vec<PyMessage>,
        model: &str,
        temperature: f64,
        max_tokens: i64,
    ) -> PyResult<String> {
        let core_msgs: Vec<nicx_nucleo::Message> = messages.iter().map(|m| m.to_core()).collect();
        let result = self
            .inner
            .generate(&core_msgs, model, temperature, max_tokens, None)
            .map_err(|e| PyErr::new::<pyo3::exceptions::PyRuntimeError, _>(e.to_string()))?;
        Ok(serde_json::to_string(&result).unwrap_or_default())
    }
}
