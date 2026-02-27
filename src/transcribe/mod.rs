//! Audio transcription via whisper-rs.
//!
//! Requires the `transcribe` feature flag. Use `transcribe-cuda` for GPU acceleration.
//! Speaker diarization requires the `diarize` feature flag.

#[cfg(feature = "transcribe")]
mod engine;
#[cfg(feature = "transcribe")]
mod audio;
#[cfg(feature = "transcribe")]
mod model;
#[cfg(feature = "diarize")]
mod diarize;

#[cfg(feature = "transcribe")]
pub use engine::run;

#[cfg(not(feature = "transcribe"))]
pub fn run(
    _file: &std::path::Path,
    _model: Option<&str>,
    _language: Option<&str>,
    _output: Option<&str>,
    _speakers: &[String],
    _diarize: bool,
) -> anyhow::Result<()> {
    anyhow::bail!(
        "Transcription support not compiled.\n\
         Rebuild with: cargo install corky --features transcribe-cuda"
    );
}
