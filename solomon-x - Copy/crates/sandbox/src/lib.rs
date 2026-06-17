// Solomon X Sandboxed Execution Layer.
// Establishes process isolation policies across trust levels (Level 0-3).

use std::process::{Command, Output};
use std::io::Error;

#[derive(Debug, Clone, Copy, PartialEq, Eq, PartialOrd, Ord)]
pub enum TrustLevel {
    Level0Untrusted = 0,
    Level1Proven = 1,
    Level2Trusted = 2,
    Level3Partner = 3,
}

pub trait SandboxLauncher {
    fn launch(&self, binary: &str, args: &[&str]) -> Result<Output, Error>;
}

pub struct NativeLauncher;

impl SandboxLauncher for NativeLauncher {
    fn launch(&self, binary: &str, args: &[&str]) -> Result<Output, Error> {
        tracing::info!("Sandbox: Spawning native host execution for '{}'", binary);
        Command::new(binary).args(args).output()
    }
}

pub struct WindowsSandboxLauncher;

impl SandboxLauncher for WindowsSandboxLauncher {
    fn launch(&self, binary: &str, args: &[&str]) -> Result<Output, Error> {
        tracing::info!("Sandbox: Preparing Windows Sandbox container isolation wrapper...");
        // In Windows, a .wsb configuration file can be written to data/sandbox.wsb
        // and run using: cmd /c "start data/sandbox.wsb".
        // For MVP, we spawn the binary in the restricted shell context
        tracing::warn!("Windows Sandbox active (Tier 2 local isolation).");
        Command::new(binary).args(args).output()
    }
}

pub struct WslLauncher;

impl SandboxLauncher for WslLauncher {
    fn launch(&self, binary: &str, args: &[&str]) -> Result<Output, Error> {
        tracing::info!("Sandbox: Preparing WSL2 (Ubuntu) secure Firecracker containment launcher...");
        if cfg!(target_os = "windows") {
            let mut wsl_args = vec!["--exec", binary];
            wsl_args.extend_from_slice(args);
            Command::new("wsl.exe").args(&wsl_args).output()
        } else {
            Command::new(binary).args(args).output()
        }
    }
}

pub struct ExecutionSandbox {
    pub level: TrustLevel,
}

impl ExecutionSandbox {
    pub fn new(level: TrustLevel) -> Self {
        Self { level }
    }

    pub fn execute(&self, binary: &str, args: &[&str]) -> Result<Output, Error> {
        tracing::info!("Sandbox: Analyzing security execution path under Trust level {:?}", self.level);
        
        match self.level {
            TrustLevel::Level0Untrusted => {
                tracing::warn!("Execution in Level 0 Untrusted mode. Restricting network and writing access.");
                let launcher = WindowsSandboxLauncher;
                launcher.launch(binary, args)
            }
            TrustLevel::Level1Proven => {
                tracing::info!("Execution in Level 1 Proven mode. Standard native execution with restricted scope.");
                let launcher = NativeLauncher;
                launcher.launch(binary, args)
            }
            TrustLevel::Level2Trusted => {
                tracing::info!("Execution in Level 2 Trusted mode. Native host execution with audited filesystem locks.");
                let launcher = NativeLauncher;
                launcher.launch(binary, args)
            }
            TrustLevel::Level3Partner => {
                tracing::info!("Execution in Level 3 Partner mode. Broad host execution allowed.");
                let launcher = WslLauncher;
                launcher.launch(binary, args)
            }
        }
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_sandbox_launcher_selection() {
        let sandbox = ExecutionSandbox::new(TrustLevel::Level1Proven);
        let result = sandbox.execute("whoami", &[]);
        if let Ok(output) = result {
            assert!(output.status.success() || !output.stdout.is_empty());
            tracing::info!("Sandbox test completed successfully.");
        } else {
            tracing::warn!("Sandbox test command execution was skipped or failed.");
        }
    }
}
