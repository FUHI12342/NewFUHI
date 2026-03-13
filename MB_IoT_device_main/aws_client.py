# aws_client.py
import aws_test  # 既存の aws_test.py をそのまま利用する想定
import config, time, json
import publisher  # publisher を直接呼ぶため

def apply_config():
    try:
        aws_test.apply_config_to_aws_test()
    except Exception as e:
        print("apply_config error:", e)

def ensure_connected():
    try:
        if hasattr(aws_test, "ensure_client_connected"):
            return aws_test.ensure_client_connected()
    except Exception as e:
        print("ensure_connected error:", e)
    return aws_test.check_connection()

def publish(topic, message, qos=0, retain=False):
    """汎用 publish。publisher に委譲"""
    try:
        return publisher.publish(topic, message, qos=qos, retain=retain)
    except Exception as e:
        print("publish error:", e)

def publish_json(topic, data, qos=0, retain=False):
    """JSON publish。publisher に委譲"""
    try:
        return publisher.publish_json(topic, data, qos=qos, retain=retain)
    except Exception as e:
        print("publish_json error:", e)
        # フォールバック: 文字列化して送信
        try:
            return publisher.publish(topic, str(data), qos=qos, retain=retain)
        except Exception as e2:
            print("fallback publish error:", e2)