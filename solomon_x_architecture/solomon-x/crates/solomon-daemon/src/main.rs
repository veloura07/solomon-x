use std::env;
use std::time::SystemTime;
use tracing::{info, error, warn};

use solomon_auth::verify_boot_token_and_derive_identity;
use solomon_bus::{MessageEnvelope, UnifiedBus, Transport};
use solomon_ledger::{Ledger, LedgerBlock};
use solomon_sandbox::ExecutionSandbox;
use solomon_sovereignty::SovereigntyGate;

#[tokio::main]
async fn main() -> Result<(), Box<dyn std::error::Error>> {
    // Initialize global tracing
    tracing_subscriber::fmt()
        .with_max_level(tracing::Level::INFO)
        .init();

    let args: Vec<String> = env::args().collect();
    
    // Check for CLI commands
    if args.len() > 1 {
        let command = args[1].as_str();
        match command {
            "init-token" => {
                info!("Initializing identity verification check...");
                match verify_boot_token_and_derive_identity() {
                    Ok(keypair) => {
                        println!("Identity derived successfully.");
                        println!("Public Key ID (Hex): {}", hex_encode(keypair.public.as_bytes()));
                        return Ok(());
                    }
                    Err(e) => {
                        error!("Failed to derive identity: {}", e);
                        std::process::exit(1);
                    }
                }
            }
            "sign-message" => {
                if args.len() < 3 {
                    error!("Usage: solomon-daemon sign-message <message>");
                    std::process::exit(1);
                }
                let payload = args[2].as_bytes();
                let keypair = verify_boot_token_and_derive_identity()?;
                
                // Encode the envelope
                let counter = 1u64;
                let encoded_envelope = MessageEnvelope::encode(counter, payload, &keypair);
                
                println!("{}", hex_encode(&encoded_envelope));
                return Ok(());
            }
            "verify-message" => {
                if args.len() < 3 {
                    error!("Usage: solomon-daemon verify-message <hex_envelope>");
                    std::process::exit(1);
                }
                let hex_str = &args[2];
                let decoded_bytes = match hex_decode(hex_str) {
                    Ok(b) => b,
                    Err(e) => {
                        error!("Invalid hex string: {}", e);
                        std::process::exit(1);
                    }
                };

                let envelope = MessageEnvelope::decode(&decoded_bytes)?;
                let keypair = verify_boot_token_and_derive_identity()?;

                match envelope.verify(&keypair.public) {
                    Ok(_) => {
                        println!("Signature verification succeeded!");
                        println!("Counter: {}", envelope.counter);
                        println!("Payload: {}", String::from_utf8_lossy(&envelope.payload));
                        return Ok(());
                    }
                    Err(e) => {
                        error!("Signature verification failed: {}", e);
                        std::process::exit(1);
                    }
                }
            }
            "help" | "--help" | "-h" => {
                print_usage();
                return Ok(());
            }
            _ => {
                error!("Unknown command: {}", command);
                print_usage();
                std::process::exit(1);
            }
        }
    }

    // Default: Daemon Boot Event Loop
    info!("Booting Solomon X Daemon core event loop...");

    // 1. Verify boot token and derive identity
    let identity_keys = match verify_boot_token_and_derive_identity() {
        Ok(keys) => {
            info!("Successfully derived cryptographic keypair. Public Key ID: {}", hex_encode(keys.public.as_bytes()));
            keys
        }
        Err(e) => {
            error!("TPM / Boot token identity derivation failed: {}", e);
            return Err(e);
        }
    };

    // 2. Initialize append-only audit ledger
    let ledger_path = "data/audit_ledger.db";
    let ledger = Ledger::new(ledger_path);
    if !ledger.verify_integrity() {
        error!("Audit ledger validation failed! Tampering detected.");
        return Err("Ledger corrupt".into());
    }

    // 3. Setup Sovereignty Gate
    let sovereignty_gate = SovereigntyGate::new(0.95, solomon_sovereignty::TrustLevel::Level1Proven);

    // 4. Initialize communication bus loop
    info!("Initializing inter-component IPC fabric...");
    let transport = UnifiedBus::new("solomon_bus").await?;

    info!("Solomon X Daemon base startup checks succeeded. Core running.");

    // Loop mock listening for incoming envelopes
    let rx_envelope = match transport.receive().await {
        Ok(env) => env,
        Err(e) => {
            warn!("IPC receive error (normal if pipe client not running yet): {}", e);
            // Simulating a mock envelope for self-test sequence
            let payload = b"whoami";
            let encoded = MessageEnvelope::encode(1, payload, &identity_keys);
            MessageEnvelope::decode(&encoded)?
        }
    };

    // Verify signature
    match rx_envelope.verify(&identity_keys.public) {
        Ok(_) => {
            info!("Payload signature verification succeeded.");
            
            // Log to ledger
            let latest_hash = ledger.get_latest_hash()?;
            let timestamp = SystemTime::now()
                .duration_since(SystemTime::UNIX_EPOCH)?
                .as_secs();

            let new_block = LedgerBlock {
                timestamp,
                proposing_agent_id: "engineer_spec".to_string(),
                target_path: String::from_utf8_lossy(&rx_envelope.payload).to_string(),
                state_diff_signature: hex_encode(&rx_envelope.signature),
                previous_hash: latest_hash,
            };
            
            ledger.append(&new_block)?;
            
            // Evaluate action via sovereignty gate
            if sovereignty_gate.evaluate_action(0.98, solomon_sovereignty::TrustLevel::Level1Proven) {
                // Execute in Sandbox wrapper
                let cmd_str = String::from_utf8_lossy(&rx_envelope.payload);
                let sandbox = ExecutionSandbox::new(solomon_sandbox::TrustLevel::Level1Proven);
                match sandbox.execute(&cmd_str, &[]) {
                    Ok(output) => {
                        info!("Sandboxed execution result: {:?}", String::from_utf8_lossy(&output.stdout));
                    }
                    Err(e) => {
                        warn!("Could not run sandbox command '{}': {}", cmd_str, e);
                    }
                }
            } else {
                warn!("Action rejected by Sovereignty Gate constraints.");
            }
        }
        Err(e) => {
            warn!("Message envelope signature verification failed: {}", e);
        }
    }

    Ok(())
}

fn hex_encode(bytes: &[u8]) -> String {
    let mut s = String::new();
    for byte in bytes {
        s.push_str(&format!("{:02x}", byte));
    }
    s
}

fn hex_decode(hex_str: &str) -> Result<Vec<u8>, Box<dyn std::error::Error>> {
    let mut bytes = Vec::new();
    let chars: Vec<char> = hex_str.chars().collect();
    if chars.len() % 2 != 0 {
        return Err("Odd length hex string".into());
    }
    for i in (0..chars.len()).step_by(2) {
        let pair = format!("{}{}", chars[i], chars[i+1]);
        let byte = u8::from_str_radix(&pair, 16)?;
        bytes.push(byte);
    }
    Ok(bytes)
}

fn print_usage() {
    println!("Solomon X Daemon");
    println!("Usage:");
    println!("  solomon-daemon                      Run daemon event loop listener");
    println!("  solomon-daemon init-token           Assert TPM and print derived public key");
    println!("  solomon-daemon sign-message <msg>   Sign a message using the derived keys");
    println!("  solomon-daemon verify-message <hex> Verify a hex-encoded Solomon envelope");
}