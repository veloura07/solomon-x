// Solomon X Ledger.
// Implements append-only transaction auditing and blockchain verification.

use serde::{Deserialize, Serialize};
use rusqlite::{params, Connection};
use sha2::{Digest, Sha256};
use std::path::Path;
use tracing::{info, warn, error};

#[derive(Serialize, Deserialize, Debug, Clone)]
pub struct LedgerBlock {
    pub timestamp: u64,
    pub proposing_agent_id: String,
    pub target_path: String,
    pub state_diff_signature: String,
    pub previous_hash: String,
}

pub struct Ledger {
    pub file_path: String,
}

impl Ledger {
    pub fn new(file_path: &str) -> Self {
        let ledger = Self {
            file_path: file_path.to_string(),
        };
        ledger.initialize_db().expect("Failed to initialize ledger database");
        ledger
    }

    fn initialize_db(&self) -> Result<(), Box<dyn std::error::Error>> {
        if let Some(parent) = Path::new(&self.file_path).parent() {
            std::fs::create_dir_all(parent)?;
        }

        let conn = Connection::open(&self.file_path)?;
        conn.execute(
            "CREATE TABLE IF NOT EXISTS ledger_blocks (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                timestamp INTEGER NOT NULL,
                proposing_agent_id TEXT NOT NULL,
                target_path TEXT NOT NULL,
                state_diff_signature TEXT NOT NULL,
                previous_hash TEXT NOT NULL,
                block_hash TEXT NOT NULL
            )",
            [],
        )?;
        Ok(())
    }

    /// Computes the SHA-256 hash of a block's fields.
    pub fn calculate_block_hash(&self, block: &LedgerBlock) -> String {
        let mut hasher = Sha256::new();
        hasher.update(block.timestamp.to_le_bytes());
        hasher.update(block.proposing_agent_id.as_bytes());
        hasher.update(block.target_path.as_bytes());
        hasher.update(block.state_diff_signature.as_bytes());
        hasher.update(block.previous_hash.as_bytes());
        
        let hash_bytes = hasher.finalize();
        let mut hash_str = String::new();
        for byte in hash_bytes {
            hash_str.push_str(&format!("{:02x}", byte));
        }
        hash_str
    }

    /// Retrieves the hash of the latest block in the chain.
    /// Returns "0" if the ledger is empty.
    pub fn get_latest_hash(&self) -> Result<String, Box<dyn std::error::Error>> {
        let conn = Connection::open(&self.file_path)?;
        let mut stmt = conn.prepare("SELECT block_hash FROM ledger_blocks ORDER BY id DESC LIMIT 1")?;
        let mut rows = stmt.query([])?;
        
        if let Some(row) = rows.next()? {
            let hash: String = row.get(0)?;
            Ok(hash)
        } else {
            // Genesis block previous hash placeholder
            Ok("0000000000000000000000000000000000000000000000000000000000000000".to_string())
        }
    }

    /// Appends a new block to the ledger, verifying the previous hash link.
    pub fn append(&self, block: &LedgerBlock) -> Result<(), Box<dyn std::error::Error>> {
        info!("Ledger: Appending transaction block for target '{}'", block.target_path);

        let latest_hash = self.get_latest_hash()?;
        if block.previous_hash != latest_hash {
            let err_msg = format!(
                "Chain verification failed: block previous_hash '{}' does not match latest hash in ledger '{}'",
                block.previous_hash, latest_hash
            );
            error!("{}", err_msg);
            return Err(err_msg.into());
        }

        let block_hash = self.calculate_block_hash(block);
        let conn = Connection::open(&self.file_path)?;
        conn.execute(
            "INSERT INTO ledger_blocks (timestamp, proposing_agent_id, target_path, state_diff_signature, previous_hash, block_hash)
             VALUES (?, ?, ?, ?, ?, ?)",
            params![
                block.timestamp,
                block.proposing_agent_id,
                block.target_path,
                block.state_diff_signature,
                block.previous_hash,
                block_hash
            ],
        )?;

        info!("Ledger: Successfully appended block. Hash: {}", block_hash);
        Ok(())
    }

    /// Walks the blockchain database and validates block hashes and block linkages.
    pub fn verify_integrity(&self) -> bool {
        info!("Ledger: Running audit verification checks...");
        let conn = match Connection::open(&self.file_path) {
            Ok(c) => c,
            Err(e) => {
                error!("Failed to open ledger db for integrity check: {}", e);
                return false;
            }
        };

        let mut stmt = match conn.prepare("SELECT timestamp, proposing_agent_id, target_path, state_diff_signature, previous_hash, block_hash FROM ledger_blocks ORDER BY id ASC") {
            Ok(s) => s,
            Err(e) => {
                error!("Failed to prepare query: {}", e);
                return false;
            }
        };

        let rows = match stmt.query_map([], |row| {
            Ok((
                LedgerBlock {
                    timestamp: row.get(0)?,
                    proposing_agent_id: row.get(1)?,
                    target_path: row.get(2)?,
                    state_diff_signature: row.get(3)?,
                    previous_hash: row.get(4)?,
                },
                row.get::<_, String>(5)?,
            ))
        }) {
            Ok(r) => r,
            Err(e) => {
                error!("Failed to fetch rows: {}", e);
                return false;
            }
        };

        let mut expected_previous_hash = "0000000000000000000000000000000000000000000000000000000000000000".to_string();

        for row_result in rows {
            let (block, saved_hash) = match row_result {
                Ok(r) => r,
                Err(e) => {
                    error!("Error parsing ledger block row: {}", e);
                    return false;
                }
            };

            // 1. Verify previous hash link matches
            if block.previous_hash != expected_previous_hash {
                warn!(
                    "Ledger corruption: Block link broken. Expected prev hash '{}', got '{}'",
                    expected_previous_hash, block.previous_hash
                );
                return false;
            }

            // 2. Re-calculate hash and verify consistency
            let calculated_hash = self.calculate_block_hash(&block);
            if calculated_hash != saved_hash {
                warn!(
                    "Ledger corruption: Block hash recalculation mismatch. Saved: '{}', Calculated: '{}'",
                    saved_hash, calculated_hash
                );
                return false;
            }

            expected_previous_hash = saved_hash;
        }

        info!("Ledger: Verification completed. Integrity checks PASSED.");
        true
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_ledger_append_and_verification() -> Result<(), Box<dyn std::error::Error>> {
        let test_db_path = "data/test_audit_ledger.db";
        // Clean up any old files
        let _ = std::fs::remove_file(test_db_path);

        // 1. Create Ledger
        let ledger = Ledger::new(test_db_path);
        assert!(ledger.verify_integrity());

        // 2. Append Genesis Block
        let genesis_prev = ledger.get_latest_hash()?;
        let block1 = LedgerBlock {
            timestamp: 1625000000,
            proposing_agent_id: "guardian_core".to_string(),
            target_path: "data/config.json".to_string(),
            state_diff_signature: "sig_genesis_block".to_string(),
            previous_hash: genesis_prev,
        };
        ledger.append(&block1)?;
        assert!(ledger.verify_integrity());

        // 3. Append Block 2
        let block1_hash = ledger.get_latest_hash()?;
        let block2 = LedgerBlock {
            timestamp: 1625000100,
            proposing_agent_id: "engineer_spec".to_string(),
            target_path: "src/lib.rs".to_string(),
            state_diff_signature: "sig_block_two".to_string(),
            previous_hash: block1_hash,
        };
        ledger.append(&block2)?;
        assert!(ledger.verify_integrity());

        // 4. Test invalid previous hash append rejection
        let bad_block = LedgerBlock {
            timestamp: 1625000200,
            proposing_agent_id: "strategist_core".to_string(),
            target_path: "readme.md".to_string(),
            state_diff_signature: "sig_bad_block".to_string(),
            previous_hash: "invalid_prev_hash".to_string(),
        };
        assert!(ledger.append(&bad_block).is_err());

        // Clean up
        let _ = std::fs::remove_file(test_db_path);
        Ok(())
    }
}
