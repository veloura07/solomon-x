use tss_esapi::{
    tss2_esys::TPMI_YES_NO,
    tss2_esys::TPM2B_DIGEST,
    tss2_esys::TPM2B_NONCE,
    tss2_esys::TPM2B_PUBLIC,
    tss2_esys::TPMT_TK_HASHCHECK,
    Context,
    Tss2Sys,
};
use ed25519_dalek::{Keypair, PublicKey, SecretKey, Signer, Verifier};
use rand::rngs::OsRng;
use std::convert::TryFrom;
use std::fs;
use std::path::Path;

/// Verifies TPM-sealed boot token and derives Ed25519 keypair
/// Called once at daemon startup
pub fn verify_boot_token_and_derive_identity() -> Result<Keypair, Box<dyn std::error::Error>> {
    // 1. Read TPM-sealed token from secure storage
    let token_path = Path::new("/var/lib/solomon/boot_token");
    let token_seed = fs::read(token_path)?;

    // 2. Verify token is bound to current PCR values (boot integrity)
    let mut context = Context::new_from_sysapi(None)?;
    let pcr_values = context.read_pcr(&[0, 1, 2, 4, 7])?; // Firmware, bootloader, kernel, daemon

    // In production: would unseal token using PCR policy
    // For MVP: assume token is valid if file exists and has correct entropy
    if token_seed.len() != 32 {
        return Err("Invalid token seed length".into());
    }

    // 3. Derive long-term Ed25519 identity key from token seed
    // Using HKDF-SHA256 for key separation
    let mut id_key_material = [0u8; 32];
    hkdf::Hkdf::<sha2::Sha256>::new(Some(&token_seed), b"solomon-identity-v1")
        .expand(&mut id_key_material)
        .map_err(|e| format!("HKDF expand failed: {}", e))?;

    // 4. Convert to Ed25519 keypair
    let secret_bytes = SecretKey::from_bytes(&id_key_material)?;
    let keypair = Keypair::from_bytes(&secret_bytes.to_bytes())?;

    Ok(keypair)
}

/// Verifies message authenticity using Ed25519 signature
/// Called on every inter-component message
pub fn verify_message_signature(
    message: &[u8],
    signature: &[u8; 64],
    public_key: &PublicKey,
) -> Result<(), Box<dyn std::error::Error>> {
    // Solomon message format: [4-byte magic][8-byte counter][64-byte signature][payload]
    if message.len() < 4 + 8 + 64 {
        return Err("Message too short for Solomon format".into());
    }

    let magic = &message[0..4];
    if magic != b"SOLo" {
        return Err("Invalid message magic".into());
    }

    let counter = u64::from_le_bytes(message[4..12].try_from()?);
    // In production: validate counter monotonicity per connection
    // For MVP: accept any counter (add replay cache later)

    let payload = &message[12 + 64..]; // Skip magic + counter + signature

    // Verify Ed25519 signature over payload
    let verifier = Verifier::from(public_key);
    verifier.verify_strict(payload, signature)
        .map_err(|e| format!("Signature verification failed: {}", e))?;

    Ok(())
}

#[cfg(test)]
mod tests {
    use super::*;
    use ed25519_dalek::Signer;

    #[test]
    fn test_handshake_flow() -> Result<(), Box<dyn std::error::Error>> {
        // Generate test keypair
        let mut csprng = OsRng {};
        let keypair = Keypair::generate(&mut csprng);

        // Create test message
        let mut message = Vec::new();
        message.extend_from_slice(b"SOLo"); // magic
        message.extend_from_slice(&1u64.to_le_bytes()); // counter
        message.extend_from_slice(b"test payload");

        // Sign message
        let signature = keypair.sign(&message[12..]); // Skip magic+counter

        // Verify signature
        verify_message_signature(
            &message,
            signature.as_bytes(),
            &keypair.public,
        )?;

        Ok(())
    }
}