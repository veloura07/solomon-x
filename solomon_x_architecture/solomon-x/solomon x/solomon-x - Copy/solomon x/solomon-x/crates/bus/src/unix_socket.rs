#[cfg(unix)]
use tokio::net::{UnixStream, UnixListener};
use tokio::io::{AsyncReadExt, AsyncWriteExt};
use std::error::Error;
use crate::envelope::MessageEnvelope;

pub struct UnixSocketSender {
    #[cfg(unix)]
    pub stream: std::sync::Arc<tokio::sync::Mutex<UnixStream>>,
}

#[cfg(unix)]
impl UnixSocketSender {
    pub async fn new(socket_path: &str) -> Result<Self, Box<dyn Error + Send + Sync>> {
        let stream = UnixStream::connect(socket_path).await?;
        Ok(Self {
            stream: std::sync::Arc::new(tokio::sync::Mutex::new(stream)),
        })
    }

    pub async fn send_envelope(&self, envelope: &MessageEnvelope) -> Result<(), Box<dyn Error + Send + Sync>> {
        let serialized = serde_json::to_vec(envelope)?;
        let len = serialized.len() as u32;

        let mut lock = self.stream.lock().await;
        lock.write_all(&len.to_le_bytes()).await?;
        lock.write_all(&serialized).await?;
        lock.flush().await?;
        
        Ok(())
    }
}

pub struct UnixSocketReceiver {
    #[cfg(unix)]
    pub listener: UnixListener,
}

#[cfg(unix)]
impl UnixSocketReceiver {
    pub async fn new(socket_path: &str) -> Result<Self, Box<dyn Error + Send + Sync>> {
        // Remove existing socket file if it exists
        let _ = std::fs::remove_file(socket_path);
        let listener = UnixListener::bind(socket_path)?;
        Ok(Self { listener })
    }

    pub async fn receive_envelope(&self) -> Result<MessageEnvelope, Box<dyn Error + Send + Sync>> {
        let (mut stream, _) = self.listener.accept().await?;

        // Read length prefix
        let mut len_bytes = [0u8; 4];
        stream.read_exact(&mut len_bytes).await?;
        let len = u32::from_le_bytes(len_bytes) as usize;

        // Read payload
        let mut buffer = vec![0u8; len];
        stream.read_exact(&mut buffer).await?;

        let envelope: MessageEnvelope = serde_json::from_slice(&buffer)?;
        Ok(envelope)
    }
}

// Stubs for Windows/non-Unix compilation platforms
#[cfg(not(unix))]
impl UnixSocketSender {
    pub async fn new(_socket_path: &str) -> Result<Self, Box<dyn Error + Send + Sync>> {
        Err("Unix sockets are only supported on Unix platforms".into())
    }
    pub async fn send_envelope(&self, _envelope: &MessageEnvelope) -> Result<(), Box<dyn Error + Send + Sync>> {
        Ok(())
    }
}

#[cfg(not(unix))]
impl UnixSocketReceiver {
    pub async fn new(_socket_path: &str) -> Result<Self, Box<dyn Error + Send + Sync>> {
        Err("Unix sockets are only supported on Unix platforms".into())
    }
    pub async fn receive_envelope(&self) -> Result<MessageEnvelope, Box<dyn Error + Send + Sync>> {
        Err("Unix sockets are only supported on Unix platforms".into())
    }
}
