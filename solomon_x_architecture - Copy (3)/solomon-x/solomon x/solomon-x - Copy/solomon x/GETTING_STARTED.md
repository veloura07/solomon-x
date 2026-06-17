# Getting Started with Solomon X

This guide will help you get Solomon X running on your RTX 4060 laptop.

## Prerequisites

- Windows 11 (22H2+)
- Rust toolchain (stable)
- Node.js 18+
- Python 3.9+
- Administrator privileges (for TPM operations)

## Step 1: Generate Bootstrap Token

Run the bootstrap script as Administrator to generate the TPM-sealed boot token and identity keypair:

```powershell
# Open PowerShell as Administrator
cd C:\Users\namir\solomon x
.\scripts\bootstrap_token.ps1
```

This will:
1. Generate a random token seed
2. (Simulate) sealing it to TPM (for MVP)
3. Derive an Ed25519 identity keypair
4. Save configuration files to `C:\ProgramData\solomon\`

## Step 2: Build the Rust Daemon

```powershell
cargo build --release
```

The compiled daemon will be at:
`target\release\solomon-daemon.exe`

## Step 3: Set Up the UI

```powershell
cd ui
npm install
npm run dev
```

The UI will be available at `http://localhost:5173` (or as indicated by Vite).

## Step 4: Run the System

In separate terminals:

Terminal 1 (Daemon):
```powershell
.\target\release\solomon-daemon.exe
```

Terminal 2 (UI):
```powershell
cd ui
npm run dev
```

Terminal 3 (Optional: Test Cognitive Twin):
```powershell
cd python\cognitive_twin
python tracker.py
```

Terminal 4 (Optional: Test Memory Search):
```powershell
cd python\memory
python search.py
```

## Step 5: Verify End-to-End Latency

Run the latency test to verify the <50ms perception-action loop:

```powershell
.\tests\e2e_latency_test.bat
```

## Architecture Overview

Solomon X is structured around three innovating layers:

1. **TrustOS**: TPM-sealed bootstrapping + biometric-bound sovereignty gates
2. **MemoryOS**: Adaptive 3-tier store (SQLite/LanceDB/Parquet) + anticipatory memory
3. **Cognitive Twin**: Measurable performance modeling (focus/load/momentum from laptop I/O)

All other layers use proven, free/open-source infrastructure:
- Communication: AF_UNIX + shared memory (Windows named pipes simulation)
- Execution: Trust-tiered sandboxing (Windows Sandbox + WSL2)
- UI: Electron + WebGPU/Three.js avatar
- AI: Phi-3-mini (4-bit GGUF) running locally on CPU

## Key Features

- ✅ **Zero cloud dependencies** - 100% local processing
- ✅ **<50ms perception-action loop** - voice input → avatar response
- ✅ **$0/month cost** - uses built-in TPM, Windows Hello, open-source models
- ✅ **Defensibility through user-specific data** - accumulates irreplaceable value over time
- ✅ **Laptop-optimized** - runs on RTX 4060, 16GB RAM, no exotic hardware

## Next Steps

After getting the basic system running:

1. **Week 1**: Implement basic agent specialization (Engineer for code scaffolding)
2. **Week 2**: Add monthly IdentityOS reflection prompts
3. **Week 3**: Implement dream-engine-inspired LanceDB index rebuilds (off-hours)
4. **Month 1**: Validate defensibility - system knows *you* better than generic AI

## Troubleshooting

- **TPM errors**: Ensure TPM 2.0 is enabled in BIOS and you're running as Administrator
- **Missing dependencies**: Install Rust (`rustup install stable`), Node.js, Python
- **UI not showing**: Check that Node.js and npm are installed correctly
- **Daemon fails to start**: Check logs in `%TEMP%\solomon-x.log`

## Support

For issues, check the logs or contact the development team.

Happy building! 🚀

--- 
*Solomon X: Your personal cognitive infrastructure platform*