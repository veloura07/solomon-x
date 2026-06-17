// Solomon X Sovereignty Gating.
// Implements security controls and trust transitions for high-confidence actions.

use tracing::{info, warn};
use solomon_auth::verify_message_signature;
use ed25519_dalek::PublicKey;

#[derive(Debug, Clone, Copy, PartialEq, Eq, PartialOrd, Ord)]
pub enum TrustLevel {
    Level0Untrusted = 0,
    Level1Proven = 1,
    Level2Trusted = 2,
    Level3Partner = 3,
}

pub struct SovereigntyGate {
    pub confidence_threshold: f64,
    pub current_trust: TrustLevel,
}

impl SovereigntyGate {
    pub fn new(confidence_threshold: f64, initial_trust: TrustLevel) -> Self {
        Self {
            confidence_threshold,
            current_trust: initial_trust,
        }
    }

    /// Evaluates if an action with a given confidence score is authorized.
    /// Returns true if autonomous execution is allowed, false if it requires interactive escalation.
    pub fn evaluate_action(&self, confidence: f64, required_trust: TrustLevel) -> bool {
        if self.current_trust < required_trust {
            warn!(
                "Action denied: current trust level {:?} is below required level {:?}",
                self.current_trust, required_trust
            );
            return false;
        }

        if confidence < self.confidence_threshold {
            info!(
                "Confidence score {:.2} is below threshold {:.2}. Triggering gating escalation.",
                confidence, self.confidence_threshold
            );
            return false;
        }

        info!("Action authorized autonomously.");
        true
    }

    /// Promotes trust level if a signed challenge is successfully verified.
    pub fn attempt_transition_escalation(
        &mut self,
        target_level: TrustLevel,
        challenge_payload: &[u8],
        signature: &[u8; 64],
        public_key: &PublicKey,
    ) -> Result<bool, Box<dyn std::error::Error>> {
        info!("Sovereignty Gate: Attempting trust level escalation to {:?}", target_level);
        
        // Verify biometric challenge signature derived from TPM identity keys
        match verify_message_signature(challenge_payload, signature, public_key) {
            Ok(_) => {
                self.current_trust = target_level;
                info!("Transition successful. Trust level elevated to {:?}", target_level);
                Ok(true)
            }
            Err(e) => {
                warn!("Escalation challenge verification failed: {}", e);
                // Degrade trust on failed authentication challenge
                self.degrade_trust();
                Ok(false)
            }
        }
    }

    /// Degrades the active trust level to level 0 on authentication failure.
    pub fn degrade_trust(&mut self) {
        warn!("Sovereignty Gate: Active trust level degraded to Level0Untrusted.");
        self.current_trust = TrustLevel::Level0Untrusted;
    }
}

#[cfg(test)]
mod tests {
    use super::*;
    use ed25519_dalek::{Keypair, Signer};
    use rand::rngs::OsRng;

    #[test]
    fn test_trust_transitions() -> Result<(), Box<dyn std::error::Error>> {
        let mut csprng = OsRng {};
        let keypair = Keypair::generate(&mut csprng);

        let mut gate = SovereigntyGate::new(0.90, TrustLevel::Level1Proven);

        // Test 1: Action requires Level 1 (should pass)
        assert!(gate.evaluate_action(0.95, TrustLevel::Level1Proven));

        // Test 2: Action requires Level 2 (should fail due to trust tier)
        assert!(!gate.evaluate_action(0.95, TrustLevel::Level2Trusted));

        // Test 3: Action has low confidence (should fail due to confidence gating)
        assert!(!gate.evaluate_action(0.85, TrustLevel::Level1Proven));

        // Test 4: Authenticated escalation challenge to Level 3
        let mut challenge = Vec::new();
        challenge.extend_from_slice(b"SOLo");
        challenge.extend_from_slice(&2u64.to_le_bytes()); // counter
        challenge.extend_from_slice(b"escalate-to-tier-3");

        let signature = keypair.sign(&challenge[12..]);
        let success = gate.attempt_transition_escalation(
            TrustLevel::Level3Partner,
            &challenge,
            signature.as_bytes(),
            &keypair.public,
        )?;
        
        assert!(success);
        assert_eq!(gate.current_trust, TrustLevel::Level3Partner);

        // Test 5: Failed signature challenge degrades to Level 0
        let bad_signature = [0u8; 64];
        let success = gate.attempt_transition_escalation(
            TrustLevel::Level3Partner,
            &challenge,
            &bad_signature,
            &keypair.public,
        )?;
        
        assert!(!success);
        assert_eq!(gate.current_trust, TrustLevel::Level0Untrusted);

        Ok(())
    }
}
