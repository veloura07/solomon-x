use serde::{Deserialize, Serialize};
use std::convert::TryInto;
use ed25519_dalek::{PublicKey, Signature, Signer, Verifier};

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct MessageEnvelope {
    pub counter: u64,
    pub signature: [u8; 64],
    pub payload: Vec<u8>,
}

impl MessageEnvelope {
    /// Encodes a payload into the binary Solomon envelope format:
    /// [magic SOLo (4B)][counter (8B)][signature (64B)][payload (N B)]
    pub fn encode<S: Signer<Signature>>(
        counter: u64,
        payload: &[u8],
        signer: &S,
    ) -> Vec<u8> {
        let mut buffer = Vec::with_capacity(4 + 8 + 64 + payload.len());
        
        // 1. Write magic
        buffer.extend_from_slice(b"SOLo");
        
        // 2. Write counter (little endian)
        buffer.extend_from_slice(&counter.to_le_bytes());
        
        // 3. Generate signature over payload
        let signature = signer.sign(payload);
        buffer.extend_from_slice(signature.as_bytes());
        
        // 4. Write payload
        buffer.extend_from_slice(payload);
        
        buffer
    }

    /// Decodes a binary Solomon envelope and validates it.
    pub fn decode(buffer: &[u8]) -> Result<Self, Box<dyn std::error::Error + Send + Sync>> {
        if buffer.len() < 76 {
            return Err("Buffer too short for Solomon envelope header".into());
        }

        // Verify magic
        if &buffer[0..4] != b"SOLo" {
            return Err("Invalid envelope magic header".into());
        }

        // Parse counter
        let counter = u64::from_le_bytes(buffer[4..12].try_into()?);

        // Parse signature
        let mut signature_bytes = [0u8; 64];
        signature_bytes.copy_from_slice(&buffer[12..76]);

        // Parse payload
        let payload = buffer[76..].to_vec();

        Ok(MessageEnvelope {
            counter,
            signature: signature_bytes,
            payload,
        })
    }

    /// Verifies the signature of the envelope against a public key.
    pub fn verify(&self, public_key: &PublicKey) -> Result<(), Box<dyn std::error::Error + Send + Sync>> {
        let signature = Signature::from_bytes(&self.signature)?;
        public_key.verify(&self.payload, &signature)
            .map_err(|e| format!("Envelope signature verification failed: {}", e).into())
    }
}

#[cfg(test)]
mod tests {
    use super::*;
    use ed25519_dalek::Keypair;
    use rand::rngs::OsRng;

    #[test]
    fn test_envelope_encode_decode() -> Result<(), Box<dyn std::error::Error + Send + Sync>> {
        let mut csprng = OsRng {};
        let keypair = Keypair::generate(&mut csprng);

        let counter = 42;
        let payload = b"{\"event\": \"sovereignty_challenge\", \"value\": 0.98}";

        // Encode
        let encoded = MessageEnvelope::encode(counter, payload, &keypair);
        
        // Decode
        let decoded = MessageEnvelope::decode(&encoded)?;
        assert_eq!(decoded.counter, counter);
        assert_eq!(decoded.payload, payload);

        // Verify signature
        decoded.verify(&keypair.public)?;

        Ok(())
    }
}
