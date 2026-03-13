# boot.py - runs before code.py
# Disables autoreload as early as possible to prevent interruptions during file operations

import supervisor

# Method 1: Official property (CircuitPython 10.0+)
try:
    supervisor.runtime.autoreload = False
    print("[BOOT] AutoReload disabled via supervisor.runtime.autoreload")
except Exception as e:
    print(f"[BOOT] Could not set supervisor.runtime.autoreload: {e}")

# Method 2: Backward compatibility (older CircuitPython)
try:
    supervisor.disable_autoreload()
    print("[BOOT] AutoReload disabled via supervisor.disable_autoreload()")
except Exception as e:
    print(f"[BOOT] Could not call supervisor.disable_autoreload(): {e}")

print("[BOOT] Boot sequence complete")
