#[cfg(windows)]
use tokio::net::windows::named_pipe::{NamedPipeClient, NamedPipeServer, ServerOptions};
use tokio::io::{AsyncReadExt, AsyncWriteExt};
use std::error::Error;
use crate::envelope::MessageEnvelope;

pub struct WindowsPipeSender {
    #[cfg(windows)]
    pub pipe: std::sync::Arc<tokio::sync::Mutex<NamedPipeClient>>,
}

#[cfg(windows)]
impl WindowsPipeSender {
    pub async fn new(pipe_name: &str) -> Result<Self, Box<dyn Error + Send + Sync>> {
        let full_path = format!(r"\\.\pipe\{}", pipe_name);
        
        let client = loop {
            match NamedPipeClient::connect(&full_path) {
                Ok(client) => break client,
                Err(e) if e.kind() == std::io::ErrorKind::WouldBlock => {
                    tokio::time::sleep(std::time::Duration::from_millis(50)).await;
                }
                Err(e) => return Err(e.into()),
            }
        };

        Ok(Self {
            pipe: std::sync::Arc::new(tokio::sync::Mutex::new(client)),
        })
    }

    pub async fn send_envelope(&self, envelope: &MessageEnvelope) -> Result<(), Box<dyn Error + Send + Sync>> {
        let serialized = serde_json::to_vec(envelope)?;
        let len = serialized.len() as u32;

        let mut lock = self.pipe.lock().await;
        
        lock.write_all(&len.to_le_bytes()).await?;
        lock.write_all(&serialized).await?;
        lock.flush().await?;
        
        Ok(())
    }
}

pub struct WindowsPipeReceiver {
    #[cfg(windows)]
    pub pipe: std::sync::Arc<tokio::sync::Mutex<NamedPipeServer>>,
}

#[cfg(windows)]
impl WindowsPipeReceiver {
    pub async fn new(pipe_name: &str) -> Result<Self, Box<dyn Error + Send + Sync>> {
        let full_path = format!(r"\\.\pipe\{}", pipe_name);
        let server = ServerOptions::new()
            .first_pipe_instance(true)
            .create(&full_path)?;

        Ok(Self {
            pipe: std::sync::Arc::new(tokio::sync::Mutex::new(server)),
        })
    }

    pub async fn receive_envelope(&self) -> Result<MessageEnvelope, Box<dyn Error + Send + Sync>> {
        let mut lock = self.pipe.lock().await;
        
        lock.connect().await?;

        let mut len_bytes = [0u8; 4];
        lock.read_exact(&mut len_bytes).await?;
        let len = u32::from_le_bytes(len_bytes) as usize;

        let mut buffer = vec![0u8; len];
        lock.read_exact(&mut buffer).await?;

        let envelope: MessageEnvelope = serde_json::from_slice(&buffer)?;
        Ok(envelope)
    }
}

#[cfg(not(windows))]
impl WindowsPipeSender {
    pub async fn new(_pipe_name: &str) -> Result<Self, Box<dyn Error + Send + Sync>> {
        Err("Named pipes are only supported on Windows".into())
    }
    pub async fn send_envelope(&self, _envelope: &MessageEnvelope) -> Result<(), Box<dyn Error + Send + Sync>> {
        Ok(())
    }
}

#[cfg(not(windows))]
impl WindowsPipeReceiver {
    pub async fn new(_pipe_name: &str) -> Result<Self, Box<dyn Error + Send + Sync>> {
        Err("Named pipes are only supported on Windows".into())
    }
    pub async fn receive_envelope(&self) -> Result<MessageEnvelope, Box<dyn Error + Send + Sync>> {
        Err("Named pipes are only supported on Windows".into())
    }
}
