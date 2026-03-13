# 例: 他のピンの組み合わせも試す簡易スキャン
import time, board, busio

candidates = [
    ("GP7/GP6", board.GP7, board.GP6),
    ("GP5/GP4", board.GP5, board.GP4),
    ("GP3/GP2", board.GP3, board.GP2),
    ("GP1/GP0", board.GP1, board.GP0),
]

for name, scl, sda in candidates:
    print("=== scan on", name, "===")
    try:
        i2c = busio.I2C(scl, sda)
        print("  waiting for lock...")
        while not i2c.try_lock():
            pass
        addrs = i2c.scan()
        print("  result:", [hex(a) for a in addrs])
        i2c.unlock()
    except Exception as e:
        print("  error:", e)

print("done.")
while True:
    time.sleep(1)