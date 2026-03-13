# wifi_test.py 改良版
import network, time, socket

SSID = "aterm-16b7fa-g"
PASSWORD = "20e22d9813303"

wlan = network.WLAN(network.STA_IF)
wlan.active(True)
if not wlan.isconnected():
    wlan.connect(SSID, PASSWORD)

timeout = 20
while timeout > 0:
    if wlan.isconnected():
        break
    print("...waiting for Wi-Fi ({}/{})".format(20 - timeout + 1, 20))
    time.sleep(1)
    timeout -= 1

if wlan.isconnected():
    print("✅ Wi-Fi connected:", wlan.ifconfig())
    # DNS 解決を試す
    try:
        res = socket.getaddrinfo("google.com", 80)
        print("✅ DNS resolved google.com:", res[0][4][0])
    except Exception as e:
        print("❌ DNS resolution failed:", e)
        # DNS が使えないか切り分けるため TCP 接続テスト
        for ip, port in [("8.8.8.8", 53), ("1.1.1.1", 443)]:
            try:
                s = socket.socket()
                s.settimeout(5)
                s.connect((ip, port))
                s.close()
                print("✅ TCP connect ok", ip, port)
            except Exception as e2:
                print("❌ TCP connect failed", ip, port, e2)
else:
    print("❌ Wi-Fi connection failed")