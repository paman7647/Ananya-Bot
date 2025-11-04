#!/usr/bin/env python3
"""
Ananya Bot Launcher
Ensures virtual environment is used before starting the bot
"""

import sys
import os
import subprocess
from pathlib import Path

def main():
    # Get project root directory
    project_root = Path(__file__).parent

    # Check if virtual environment exists
    venv_path = project_root / ".venv"
    if not venv_path.exists():
        print("❌ Virtual environment not found!")
        print("Please create it first:")
        print("  python3 -m venv .venv")
        print("  source .venv/bin/activate")
        print("  pip install -r requirements.txt")
        sys.exit(1)

    # Check if we're already in the virtual environment
    if sys.prefix == str(venv_path):
        # We're in the venv, start the bot directly
        print("✅ Virtual environment active, starting bot...")
        from src.bot.main import main as bot_main
        import asyncio
        asyncio.run(bot_main())
    else:
        # Not in venv, restart with venv
        print("🔄 Activating virtual environment and starting bot...")
        python_exe = venv_path / "bin" / "python"
        if not python_exe.exists():
            print(f"❌ Python executable not found in {python_exe}")
            sys.exit(1)

        # Restart with virtual environment
        os.execv(str(python_exe), [str(python_exe), __file__] + sys.argv[1:])

if __name__ == "__main__":
    main()