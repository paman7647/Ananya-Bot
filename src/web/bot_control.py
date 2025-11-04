import asyncio
import logging
import os
import sys
from pathlib import Path

import psutil

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class BotController:
    def __init__(self):
        self.process = None
        self.status = "unknown"
        self.main_script_path = str(Path(__file__).parent.parent / "bot" / "main.py")
        self.workspace_path = str(Path(__file__).parent.parent.parent)

        # Set up environment variables
        self.env = os.environ.copy()
        self.env["PYTHONPATH"] = self.workspace_path
        self.env["PYTHONUNBUFFERED"] = "1"  # Ensure output is not buffered

        # Configure Python interpreter - use virtual environment if available
        venv_python = Path(self.workspace_path) / ".venv" / "bin" / "python"
        if venv_python.exists():
            self.python_path = str(venv_python)
        else:
            # Fallback to system Python
            self.python_path = sys.executable

        logger.info(f"Bot controller initialized. Script path: {self.main_script_path}")
        logger.info(f"Using Python interpreter: {self.python_path}")
        logger.info(f"Workspace path: {self.workspace_path}")

        # Check for existing bot processes on initialization
        self._check_existing_processes()

    def _check_existing_processes(self):
        """Check if there are existing bot processes running"""
        try:
            script_name = "main.py"
            python_cmd = os.path.basename(self.python_path)

            for proc in psutil.process_iter(['pid', 'name', 'cmdline']):
                try:
                    if proc.info['name'] in [python_cmd, 'python', 'python3']:
                        cmdline = proc.info['cmdline']
                        if cmdline and len(cmdline) > 1:
                            # Check if this process is running our bot script
                            if script_name in ' '.join(cmdline) and self.workspace_path in ' '.join(cmdline):
                                logger.info(f"Found existing bot process: PID {proc.info['pid']}")
                                self.status = "running"
                                # Don't set self.process since we didn't start it
                                return
                except (psutil.NoSuchProcess, psutil.AccessDenied):
                    continue

            self.status = "stopped"
            logger.info("No existing bot processes found")

        except Exception as e:
            logger.error(f"Error checking existing processes: {e}")
            self.status = "unknown"

    async def start(self):
        """Start the bot process"""
        # First check if bot is already running
        if self._is_bot_running():
            logger.info("Bot is already running")
            self.status = "running"
            return True

        if self.process and not self.process.returncode:
            logger.warning("Bot process already exists and is running")
            return False

        try:
            logger.info("Starting bot process...")

            # Create the process
            self.process = await asyncio.create_subprocess_exec(
                self.python_path,
                self.main_script_path,
                env=self.env,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
                cwd=self.workspace_path
            )

            # Start output monitoring
            asyncio.create_task(self._monitor_output())
            asyncio.create_task(self._monitor_errors())
            asyncio.create_task(self._monitor_process())

            logger.info(f"Bot started with PID: {self.process.pid}")
            self.status = "running"
            return True

        except Exception as e:
            logger.error(f"Failed to start bot: {str(e)}")
            self.status = "error"
            return False

    async def stop(self):
        """Stop the bot process"""
        # First try to stop managed process
        if self.process:
            try:
                logger.info("Stopping managed bot process...")
                self.process.terminate()

                # Wait for the process to terminate
                try:
                    await asyncio.wait_for(self.process.wait(), timeout=5.0)
                except asyncio.TimeoutError:
                    logger.warning("Bot didn't terminate, forcing kill...")
                    self.process.kill()
                    await self.process.wait()

                self.process = None
                self.status = "stopped"
                logger.info("Managed bot stopped successfully")
                return True

            except Exception as e:
                logger.error(f"Error stopping managed bot: {str(e)}")

        # If no managed process, try to find and stop external bot processes
        return await self._stop_external_bot()

    async def _stop_external_bot(self):
        """Stop external bot processes"""
        try:
            script_name = "main.py"
            python_cmd = os.path.basename(self.python_path)
            stopped_count = 0

            for proc in psutil.process_iter(['pid', 'name', 'cmdline']):
                try:
                    if proc.info['name'] in [python_cmd, 'python', 'python3']:
                        cmdline = proc.info['cmdline']
                        if cmdline and len(cmdline) > 1:
                            # Check if this process is running our bot script
                            if script_name in ' '.join(cmdline) and self.workspace_path in ' '.join(cmdline):
                                logger.info(f"Stopping external bot process: PID {proc.info['pid']}")
                                proc.terminate()

                                # Wait for termination
                                try:
                                    proc.wait(timeout=5.0)
                                except psutil.TimeoutExpired:
                                    logger.warning(f"Force killing bot process: PID {proc.info['pid']}")
                                    proc.kill()

                                stopped_count += 1

                except (psutil.NoSuchProcess, psutil.AccessDenied):
                    continue

            if stopped_count > 0:
                self.status = "stopped"
                logger.info(f"Stopped {stopped_count} external bot processes")
                return True
            else:
                logger.warning("No bot processes found to stop")
                return False

        except Exception as e:
            logger.error(f"Error stopping external bot: {e}")
            self.status = "error"
            return False

    async def restart(self):
        """Restart the bot process"""
        logger.info("Restarting bot...")
        await self.stop()
        await asyncio.sleep(2)  # Wait for cleanup
        return await self.start()

    def _is_bot_running(self):
        """Check if bot is currently running"""
        try:
            script_name = "main.py"
            python_cmd = os.path.basename(self.python_path)

            for proc in psutil.process_iter(['pid', 'name', 'cmdline']):
                try:
                    if proc.info['name'] in [python_cmd, 'python', 'python3']:
                        cmdline = proc.info['cmdline']
                        if cmdline and len(cmdline) > 1:
                            # Check if this process is running our bot script
                            if script_name in ' '.join(cmdline) and self.workspace_path in ' '.join(cmdline):
                                return True
                except (psutil.NoSuchProcess, psutil.AccessDenied):
                    continue

            return False

        except Exception as e:
            logger.error(f"Error checking if bot is running: {e}")
            return False

    async def _monitor_output(self):
        """Monitor and log bot's stdout"""
        if not self.process:
            return

        while True:
            try:
                line = await self.process.stdout.readline()
                if not line:
                    break

                output = line.decode().strip()
                if output:
                    logger.info(f"Bot output: {output}")

            except Exception as e:
                logger.error(f"Error monitoring bot output: {str(e)}")
                break

    async def _monitor_errors(self):
        """Monitor and log bot's stderr"""
        if not self.process:
            return

        while True:
            try:
                line = await self.process.stderr.readline()
                if not line:
                    break

                error = line.decode().strip()
                if error:
                    logger.error(f"Bot error: {error}")

            except Exception as e:
                logger.error(f"Error monitoring bot errors: {str(e)}")
                break

    async def _monitor_process(self):
        """Monitor if the bot process is still alive"""
        if not self.process:
            return

        try:
            # Wait for the process to finish
            return_code = await self.process.wait()
            logger.warning(f"Bot process exited with code: {return_code}")
            self.status = "stopped"
            self.process = None
        except Exception as e:
            logger.error(f"Error monitoring bot process: {str(e)}")
            self.status = "error"
            self.process = None

    def get_status(self):
        """Get current bot status"""
        # Check if managed process is still running
        if self.process and self.process.returncode is None:
            self.status = "running"
        elif self.process and self.process.returncode is not None:
            self.status = "stopped"
            self.process = None
        else:
            # Check for external bot processes
            if self._is_bot_running():
                self.status = "running"
            else:
                self.status = "stopped"

        return {
            "status": self.status,
            "pid": self.process.pid if self.process and self.process.returncode is None else None,
            "external_process": self._is_bot_running() if not self.process else False
        }

# Create global instance
bot_controller = BotController()
