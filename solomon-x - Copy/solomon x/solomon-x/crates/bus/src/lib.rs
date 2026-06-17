pub mod envelope;
pub mod windows_pipe;
pub mod unix_socket;

use async_trait::async_trait;
use std::error::Error;

pub use envelope::MessageEnvelope;

#[async_trait]
pub trait Transport {
    async fn send(&self, envelope: &MessageEnvelope) -> Result<(), Box<dyn Error + Send + Sync>>;
    async fn receive(&self) -> Result<MessageEnvelope, Box<dyn Error + Send + Sync>>;
}

pub struct UnifiedBus {
    #[cfg(windows)]
    pub sender: Option<windows_pipe::WindowsPipeSender>,
    #[cfg(windows)]
    pub receiver: Option<windows_pipe::WindowsPipeReceiver>,
    
    #[cfg(unix)]
    pub sender: Option<unix_socket::UnixSocketSender>,
    #[cfg(unix)]
    pub receiver: Option<unix_socket::UnixSocketReceiver>,
}

impl UnifiedBus {
    #[cfg(windows)]
    pub async fn new(address: &str) -> Result<Self, Box<dyn Error + Send + Sync>> {
        let sender = match windows_pipe::WindowsPipeSender::new(address).await {
            Ok(s) => Some(s),
            Err(e) => {
                tracing::warn!("Windows Named Pipe sender setup failed (normal if server is not up yet): {}", e);
                None
            }
        };
        let receiver = match windows_pipe::WindowsPipeReceiver::new(address).await {
            Ok(r) => Some(r),
            Err(e) => {
                tracing::warn!("Windows Named Pipe receiver setup failed: {}", e);
                None
            }
        };
        Ok(Self { sender, receiver })
    }

    #[cfg(unix)]
    pub async fn new(address: &str) -> Result<Self, Box<dyn Error + Send + Sync>> {
        let sender = match unix_socket::UnixSocketSender::new(address).await {
            Ok(s) => Some(s),
            Err(e) => {
                tracing::warn!("Unix Domain Socket sender setup failed: {}", e);
                None
            }
        };
        let receiver = match unix_socket::UnixSocketReceiver::new(address).await {
            Ok(r) => Some(r),
            Err(e) => {
                tracing::warn!("Unix Domain Socket receiver setup failed: {}", e);
                None
            }
        };
        Ok(Self { sender, receiver })
    }
}

#[async_trait]
impl Transport for UnifiedBus {
    async fn send(&self, envelope: &MessageEnvelope) -> Result<(), Box<dyn Error + Send + Sync>> {
        #[cfg(windows)]
        {
            if let Some(ref s) = self.sender {
                s.send_envelope(envelope).await?;
                return Ok(());
            }
        }
        #[cfg(unix)]
        {
            if let Some(ref s) = self.sender {
                s.send_envelope(envelope).await?;
                return Ok(());
            }
        }
        Err("No active sender transport channel configured".into())
    }

    async fn receive(&self) -> Result<MessageEnvelope, Box<dyn Error + Send + Sync>> {
        #[cfg(windows)]
        {
            if let Some(ref r) = self.receiver {
                return r.receive_envelope().await;
            }
        }
        #[cfg(unix)]
        {
            if let Some(ref r) = self.receiver {
                return r.receive_envelope().await;
            }
        }
        Err("No active receiver transport channel configured".into())
    }
}
