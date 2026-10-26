//! Ponte PyO3: expõe ao Python (`nicx_rust`) o que o Nicx usa do Rust.
#![allow(clippy::redundant_closure, unused_variables)]

use once_cell::sync::Lazy;
use pyo3::prelude::*;

// Shared tokio runtime for async-to-sync bridge (agents, future async APIs).
pub(crate) static RUNTIME: Lazy<tokio::runtime::Runtime> =
    Lazy::new(|| tokio::runtime::Runtime::new().expect("Failed to create tokio runtime"));

pub mod agentes;
pub mod ferramentas;
pub mod memoria;
pub mod motores;
pub mod nucleo;
pub mod seguranca;

// Module-level functions

#[pyfunction]
#[pyo3(signature = (path=None))]
fn load_config(path: Option<&str>) -> PyResult<nucleo::PyConfig> {
    let p = path.map(std::path::Path::new);
    let config = nicx_nucleo::load_config(p)
        .map_err(|e| PyErr::new::<pyo3::exceptions::PyRuntimeError, _>(e.to_string()))?;
    Ok(nucleo::PyConfig { inner: config })
}

#[pyfunction]
fn detect_hardware() -> PyResult<String> {
    let hw = nicx_nucleo::hardware::detect_hardware();
    Ok(serde_json::to_string(&hw).unwrap_or_default())
}

#[pyfunction]
fn check_ssrf(url: &str) -> Option<String> {
    nicx_seguranca::check_ssrf(url)
}

#[pyfunction]
fn is_sensitive_file(path: &str) -> bool {
    nicx_seguranca::is_sensitive_file(std::path::Path::new(path))
}

#[pyfunction]
fn register_builtin_models() {
    nicx_nucleo::model_catalog::register_builtin_models();
}

#[pymodule]
fn nicx_rust(m: &Bound<'_, PyModule>) -> PyResult<()> {
    // --- Core types ---
    m.add_class::<nucleo::PyMessage>()?;
    m.add_class::<nucleo::PyToolResult>()?;
    m.add_class::<nucleo::PyToolCall>()?;
    m.add_class::<nucleo::PyConfig>()?;
    m.add_class::<nucleo::PyEventBus>()?;
    m.add_class::<nucleo::PyModelSpec>()?;
    m.add_class::<nucleo::PyRoutingContext>()?;
    m.add_class::<nucleo::PyAgentContext>()?;
    m.add_class::<nucleo::PyAgentResult>()?;

    // --- Engines ---
    m.add_class::<motores::PyEngine>()?;
    m.add_class::<motores::PyOllamaEngine>()?;

    // --- Agents ---
    m.add_class::<agentes::PySimpleAgent>()?;
    m.add_class::<agentes::PyOrchestratorAgent>()?;
    m.add_class::<agentes::PyNativeReActAgent>()?;
    m.add_class::<agentes::PyNativeOpenHandsAgent>()?;
    m.add_class::<agentes::PyMonitorOperativeAgent>()?;
    m.add_class::<agentes::PyLoopGuard>()?;

    // --- Tools ---
    m.add_class::<ferramentas::PyToolExecutor>()?;
    m.add_class::<ferramentas::PyCalculatorTool>()?;
    m.add_class::<ferramentas::PyThinkTool>()?;
    m.add_class::<ferramentas::PyFileReadTool>()?;
    m.add_class::<ferramentas::PyFileWriteTool>()?;
    m.add_class::<ferramentas::PyShellExecTool>()?;
    m.add_class::<ferramentas::PyHttpRequestTool>()?;
    m.add_class::<ferramentas::PyGitStatusTool>()?;
    m.add_class::<ferramentas::PyGitDiffTool>()?;
    m.add_class::<ferramentas::PyGitLogTool>()?;

    // --- Storage / Memory ---
    m.add_class::<memoria::PySQLiteMemory>()?;
    m.add_class::<memoria::PyBM25Memory>()?;
    m.add_class::<memoria::PyFAISSMemory>()?;
    m.add_class::<memoria::PyColBERTMemory>()?;
    m.add_class::<memoria::PyHybridMemory>()?;
    m.add_class::<memoria::PyKnowledgeGraphMemory>()?;

    // --- Security ---
    m.add_class::<seguranca::PySecretScanner>()?;
    m.add_class::<seguranca::PyPIIScanner>()?;
    m.add_class::<seguranca::PyGuardrailsEngine>()?;
    m.add_class::<seguranca::PyAuditLogger>()?;
    m.add_class::<seguranca::PyCapabilityPolicy>()?;
    m.add_class::<seguranca::PyInjectionScanner>()?;
    m.add_class::<seguranca::PyRateLimiter>()?;
    m.add_class::<seguranca::PyTaintSet>()?;

    // --- Telemetry ---
    // --- Telemetry (new session/phase/ITL/FLOPs classes) ---

    // --- Traces ---

    // --- Learning ---

    // --- MCP ---

    // --- Sessions ---

    // --- Workflow ---

    // --- Skills ---

    // --- Recipes ---

    // --- Templates ---

    // --- A2A ---

    // --- Scheduler ---

    // --- Module-level functions ---
    m.add_function(wrap_pyfunction!(load_config, m)?)?;
    m.add_function(wrap_pyfunction!(detect_hardware, m)?)?;
    m.add_function(wrap_pyfunction!(check_ssrf, m)?)?;
    m.add_function(wrap_pyfunction!(is_sensitive_file, m)?)?;
    m.add_function(wrap_pyfunction!(register_builtin_models, m)?)?;

    Ok(())
}
